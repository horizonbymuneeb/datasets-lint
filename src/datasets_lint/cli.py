"""Command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from datasets_lint import __version__
from datasets_lint.baseline import diff_lines, load_baseline
from datasets_lint.checks import ALL_CHECKS
from datasets_lint.config import Config, load_config
from datasets_lint.dataset import DatasetError, load_dataset
from datasets_lint.engine import UnknownCheck, build_report, resolve_checks, run_checks
from datasets_lint.report import write_html, write_json
from datasets_lint.result import Report, Severity

ICON = {"ok": "\u2713", "warn": "\u26a0", "error": "\u2717"}
EXIT_OK, EXIT_BREACH, EXIT_USAGE = 0, 1, 2


def _csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="datasets-lint",
        description="Audit a dataset for duplicates, PII and distribution problems.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="audit one or more dataset files")
    run.add_argument("paths", nargs="+", help=".jsonl / .json / .csv / .parquet files")
    run.add_argument("--checks", default=None, help="comma separated ids (default: all)")
    run.add_argument("--exclude", default=None, help="comma separated ids to skip")
    run.add_argument("--sample", type=int, default=None, help="max rows to audit")
    run.add_argument("--seed", type=int, default=None, help="sampling seed")
    run.add_argument("--text-column", default=None)
    run.add_argument("--label-column", default=None)
    run.add_argument("--config", default=None, help="path to datasets-lint.toml")
    run.add_argument(
        "--profile",
        choices=["default", "strict", "ci", "dev"],
        default=None,
        help="threshold preset: strict (blocks on warnings), ci, dev (never fails)",
    )
    run.add_argument("--sarif", default=None, help="write SARIF 2.1.0 for GitHub code scanning")
    run.add_argument("--junit", default=None, help="write JUnit XML for CI dashboards")
    run.add_argument("--no-plugins", action="store_true", help="ignore third-party check plugins")
    run.add_argument("--report", default=None, help="write a single-file HTML report")
    run.add_argument("--json-out", default=None, help="write the JSON report")
    run.add_argument("--baseline", default=None, help="previous JSON report to diff against")
    run.add_argument(
        "--fix", default=None, metavar="OUT", help="write a repaired copy of the dataset"
    )
    run.add_argument(
        "--fix-only",
        default=None,
        help="comma separated fixers to run: dup,stats,pii,contamination",
    )
    run.add_argument(
        "--fix-keep",
        choices=["first", "last"],
        default="first",
        help="which row of a duplicate cluster to keep (default: first)",
    )
    run.add_argument(
        "--fix-pii",
        choices=["redact", "drop"],
        default="redact",
        help="redact PII in place or drop the rows (default: redact)",
    )
    run.add_argument(
        "--fix-drop-contaminated",
        action="store_true",
        help="also drop rows that overlap an eval set",
    )
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="with --fix: plan and report changes without writing the file",
    )
    run.add_argument(
        "--fail-on",
        choices=["none", "warn", "error"],
        default=None,
        help="exit non-zero when a check reaches this severity (default: error)",
    )
    run.add_argument("--quiet", action="store_true", help="only print the verdict line")

    sub.add_parser("checks", help="list available checks")
    return parser


def _print_results(report: Report, quiet: bool) -> None:
    if not quiet:
        print(
            f"datasets-lint {report.version}  ·  {', '.join(report.dataset_paths)}\n"
            f"  {report.audited_rows:,} rows audited "
            f"(of {report.total_rows:,}, seed {report.seed})  ·  "
            f"text={report.text_column or '—'}  label={report.label_column or '—'}\n"
        )
        for result in report.results:
            print(
                f"  {ICON[result.severity.value]} {result.check_id:<14}"
                f"{result.duration_s:>6.2f}s   {result.summary}"
            )
        print()
    counts = report.counts()
    print(
        f"  verdict: {report.worst.value} — {counts['error']} error, "
        f"{counts['warn']} warning, {counts['ok']} ok "
        f"· {sum(r.duration_s for r in report.results):.2f}s"
    )


def _exit_code(report: Report, fail_on: str) -> int:
    if fail_on == "none":
        return EXIT_OK
    threshold = Severity.WARN if fail_on == "warn" else Severity.ERROR
    return EXIT_BREACH if report.worst.rank >= threshold.rank else EXIT_OK


def _print_fixes(fixes: dict) -> None:
    dropped = fixes.get("dropped_rows", 0)
    by = fixes.get("dropped_by_fixer", {})
    parts = " · ".join(f"{k} {v:,}" for k, v in by.items())
    redactions = fixes.get("redactions", {})
    red = " · ".join(f"{k} {v:,}" for k, v in redactions.items())
    line = f"  fixes: {dropped:,} rows dropped" + (f" ({parts})" if parts else "")
    if red:
        line += f" · {sum(redactions.values()):,} redactions ({red})"
    print(line)
    if fixes.get("dry_run"):
        print("  dry run — nothing written")
    elif fixes.get("output"):
        print(f"  fixed → {fixes['output']}")


def _run_fixes(args: argparse.Namespace, dataset, cfg: Config) -> dict | None:
    from datasets_lint.checks.base import Context
    from datasets_lint.fixers import apply_fixes, plan_fixes, write_dataset

    if not (args.fix or args.dry_run):
        return None
    plan = plan_fixes(
        dataset,
        Context(config=cfg, seed=cfg.seed),
        only=_csv(args.fix_only),
        keep=args.fix_keep,
        pii_action=args.fix_pii,
        drop_contaminated=args.fix_drop_contaminated,
    )
    outcome = apply_fixes(dataset, plan)
    stats = outcome.stats
    if args.fix and not args.dry_run:
        stats["output"] = str(write_dataset(outcome.rows, args.fix, dataset.columns))
    else:
        stats["dry_run"] = True
    return stats


def _cmd_run(args: argparse.Namespace) -> int:
    cfg: Config = load_config(args.config, profile=args.profile)
    if args.sample is not None:
        cfg.sample = args.sample
    if args.seed is not None:
        cfg.seed = args.seed
    if args.text_column is not None:
        cfg.text_column = args.text_column
    if args.label_column is not None:
        cfg.label_column = args.label_column
    if args.fail_on is not None:
        cfg.fail_on = args.fail_on

    try:
        checks = resolve_checks(
            _csv(args.checks), _csv(args.exclude), include_plugins=not args.no_plugins
        )
    except UnknownCheck as exc:
        print(f"datasets-lint: {exc}", file=sys.stderr)
        return EXIT_USAGE

    try:
        dataset = load_dataset(
            args.paths,
            sample=cfg.sample,
            seed=cfg.seed,
            text_column=cfg.text_column,
            label_column=cfg.label_column,
        )
    except DatasetError as exc:
        print(f"datasets-lint: {exc}", file=sys.stderr)
        return EXIT_USAGE

    results = run_checks(dataset, cfg, checks)
    try:
        fixes = _run_fixes(args, dataset, cfg)
    except (ValueError, OSError) as exc:
        print(f"datasets-lint: fix error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    report = build_report(dataset, cfg, results, fixes=fixes)

    _print_results(report, args.quiet)
    if fixes:
        _print_fixes(fixes)

    if args.baseline:
        try:
            baseline = load_baseline(args.baseline)
        except (OSError, ValueError) as exc:
            print(f"datasets-lint: baseline error: {exc}", file=sys.stderr)
            return EXIT_USAGE
        print("\n  vs baseline:")
        for line in diff_lines(report, baseline):
            print(f"    {line}")

    if args.json_out:
        write_json(report, args.json_out)
        if not args.quiet:
            print(f"\n  json → {Path(args.json_out)}")
    if args.sarif:
        from datasets_lint.report.sarif import write_sarif

        path = write_sarif(report, args.sarif)
        if not args.quiet:
            print(f"  sarif → {path}")
    if args.junit:
        from datasets_lint.report.junit import write_junit

        path = write_junit(report, args.junit)
        if not args.quiet:
            print(f"  junit → {path}")
    if args.report:
        path = write_html(report, args.report)
        if not args.quiet:
            print(f"  report → {path}")

    return _exit_code(report, cfg.fail_on)


def _cmd_checks() -> int:
    print("available checks:\n")
    for check in ALL_CHECKS:
        print(f"  {check.id:<9} {check.title}")
        print(f"            {check.description}\n")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "checks":
            return _cmd_checks()
        return _cmd_run(args)
    except KeyboardInterrupt:  # pragma: no cover
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
