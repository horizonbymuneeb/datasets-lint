"""Duplicate detection: exact hashing plus MinHash/LSH near-duplicates.

Design note: MinHash *estimates* Jaccard, and on short rows (instruction-style
data) a 64-permutation sketch has enough variance to miss an obvious duplicate.
So LSH is used only to generate candidate pairs (with a deliberately loose
threshold) and every candidate is then verified with an exact Jaccard on the
shingle sets. Result: no false negatives from sketch noise, no O(n^2) scan.
"""

from __future__ import annotations

import hashlib
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from datasketch import MinHash, MinHashLSH

from datasets_lint.checks.base import Check, Context
from datasets_lint.dataset import Dataset, normalize
from datasets_lint.result import CheckResult, Finding, Severity


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra

    def clusters(self) -> dict[int, list[int]]:
        groups: dict[int, list[int]] = defaultdict(list)
        for x in self.parent:
            groups[self.find(x)].append(x)
        return groups


def _shingles(text: str, size: int) -> frozenset[str]:
    words = text.split()
    if not words:
        return frozenset()
    if len(words) <= size:
        return frozenset({" ".join(words)})
    # interning keeps memory flat: corpora repeat the same shingles constantly
    return frozenset(
        sys.intern(" ".join(words[i : i + size])) for i in range(len(words) - size + 1)
    )


@dataclass
class DupSettings:
    threshold: float = 0.7
    num_perm: int = 64
    shingle_size: int = 3
    max_chars: int = 300
    max_near_dup_pct: float = 2.0

    @classmethod
    def from_context(cls, ctx: Context) -> DupSettings:
        return cls(
            threshold=float(ctx.threshold("dup", "threshold", 0.7)),
            num_perm=int(ctx.threshold("dup", "num_perm", 64)),
            shingle_size=int(ctx.threshold("dup", "shingle_size", 3)),
            max_chars=int(ctx.threshold("dup", "max_chars", 300)),
            max_near_dup_pct=float(ctx.threshold("dup", "max_near_dup_pct", 2.0)),
        )


@dataclass
class DupAnalysis:
    clusters: list[list[int]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def duplicate_rows(self) -> list[int]:
        """Every row that is not the first member of its cluster."""
        return sorted(row for members in self.clusters for row in sorted(members)[1:])


def find_clusters(ds: Dataset, ctx: Context) -> DupAnalysis:
    """Compute near-duplicate clusters. Shared by the check and the `dup` codemod."""
    settings = DupSettings.from_context(ctx)
    suppressed = ctx.suppressed_rows("dup")
    total = ds.audited_rows - len(suppressed)
    metrics: dict[str, Any] = {
        "threshold": settings.threshold,
        "shingle_size": settings.shingle_size,
        "max_chars": settings.max_chars,
    }
    if total == 0:
        return DupAnalysis(metrics=metrics)

    # Long documents are truncated: the opening characters already carry enough
    # signal, and it keeps the sketch and the exact sets small.
    texts = [(i, normalize(t)[: settings.max_chars]) for i, t in ds.texts() if i not in suppressed]

    exact: dict[str, list[int]] = defaultdict(list)
    for i, norm in texts:
        if norm:
            exact[hashlib.sha1(norm.encode()).hexdigest()].append(i)
    exact_groups = {k: v for k, v in exact.items() if len(v) > 1}
    exact_rows = sum(len(v) for v in exact_groups.values())
    metrics["exact_dup_rows"] = exact_rows
    metrics["exact_dup_pct"] = round(100.0 * exact_rows / total, 3)
    metrics["exact_dup_groups"] = len(exact_groups)

    sets: dict[int, frozenset[str]] = {}
    sketches: dict[int, MinHash] = {}
    lsh = MinHashLSH(threshold=max(0.05, settings.threshold - 0.15), num_perm=settings.num_perm)
    for i, norm in texts:
        grams = _shingles(norm, settings.shingle_size)
        if not grams:
            continue
        sets[i] = grams
        mh = MinHash(num_perm=settings.num_perm)
        for sh in grams:
            mh.update(sh.encode())
        sketches[i] = mh
        lsh.insert(str(i), mh)

    uf = _UnionFind()
    candidate_pairs = 0
    verified_pairs = 0
    for i, grams in sets.items():
        for other in lsh.query(sketches[i]):
            j = int(other)
            if j <= i:
                continue
            candidate_pairs += 1
            other_grams = sets[j]
            inter = len(grams & other_grams)
            if inter == 0:
                continue
            if inter / len(grams | other_grams) >= settings.threshold:
                verified_pairs += 1
                uf.union(i, j)

    clusters = [sorted(v) for v in uf.clusters().values() if len(v) > 1]
    clusters.sort(key=len, reverse=True)
    near_rows = sum(len(c) for c in clusters)
    metrics["near_dup_rows"] = near_rows
    metrics["near_dup_pct"] = round(100.0 * near_rows / total, 3)
    metrics["near_dup_clusters"] = len(clusters)
    metrics["candidate_pairs"] = candidate_pairs
    metrics["verified_pairs"] = verified_pairs
    if clusters:
        metrics["largest_cluster"] = len(clusters[0])

    if len(ds.sources) > 1:
        cross_source_rows = sum(
            len(c) for c in clusters if len({ds.source_of(ds.rows[m]) for m in c}) > 1
        )
        metrics["cross_source_dup_rows"] = cross_source_rows
        metrics["cross_source_dup_pct"] = round(100.0 * cross_source_rows / total, 3)

    return DupAnalysis(clusters=clusters, metrics=metrics)


class DupCheck(Check):
    id = "dup"
    title = "Duplicates"
    description = "Exact and near-duplicate rows (MinHash/LSH), plus cross-split overlap."

    def run(self, ds: Dataset, ctx: Context) -> CheckResult:
        analysis = find_clusters(ds, ctx)
        metrics = analysis.metrics
        if ds.audited_rows == 0:
            return CheckResult(
                check_id=self.id,
                title=self.title,
                severity=Severity.OK,
                summary="no rows to check",
                metrics=metrics,
            )

        findings: list[Finding] = []
        for members in analysis.clusters[:25]:
            srcs = sorted({ds.source_of(ds.rows[m]) for m in members})
            sample = normalize(ds.text(ds.rows[members[0]]))[:120]
            findings.append(
                Finding(
                    message=f"{len(members)} near-duplicate rows"
                    + (f" across {', '.join(srcs)}" if len(srcs) > 1 else "")
                    + f': "{sample}…"',
                    row=members[0],
                    detail={"size": len(members), "sources": srcs, "sample_rows": members[:5]},
                )
            )

        max_pct = DupSettings.from_context(ctx).max_near_dup_pct
        severity = Severity.OK
        if metrics["near_dup_pct"] > max_pct:
            severity = Severity.ERROR
        elif metrics["near_dup_pct"] > max_pct / 2:
            severity = Severity.WARN

        summary = (
            f"{metrics['near_dup_pct']:.2f}% near-duplicate "
            f"({len(analysis.clusters):,} clusters), {metrics['exact_dup_pct']:.2f}% exact"
        )
        if "cross_source_dup_pct" in metrics:
            summary += f" · {metrics['cross_source_dup_pct']:.2f}% cross-file"

        return CheckResult(
            check_id=self.id,
            title=self.title,
            severity=severity,
            summary=summary,
            metrics=metrics,
            findings=findings,
        )
