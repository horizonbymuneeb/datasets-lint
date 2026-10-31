from pathlib import Path
from xml.etree import ElementTree as ET

from datasets_lint.cli import main
from datasets_lint.report.junit import to_junit, write_junit
from datasets_lint.result import CheckResult, Report, Severity

FIXTURES = Path(__file__).parent / "fixtures"
DIRTY = str(FIXTURES / "dirty.jsonl")


def _report() -> Report:
    return Report(
        dataset_paths=["data/input.jsonl"],
        total_rows=3,
        audited_rows=3,
        sample_size=3,
        seed=42,
        text_column="text",
        label_column=None,
        columns=["text"],
        results=[
            CheckResult("broken", "Broken", Severity.ERROR, "bad <data> & labels", duration_s=0.1),
            CheckResult("warning", "Warning", Severity.WARN, "review this", duration_s=0.2),
            CheckResult("clean", "Clean", Severity.OK, "all good", duration_s=0.3),
        ],
    )


def test_junit_xml_is_parseable_and_preserves_result_semantics(tmp_path):
    report = _report()
    root = ET.fromstring(to_junit(report))

    assert root.attrib == {
        "name": "datasets-lint",
        "tests": "3",
        "failures": "1",
        "skipped": "1",
        "time": "0.600",
    }
    cases = {case.attrib["name"]: case for case in root.findall("testcase")}
    assert cases["broken"].find("failure") is not None
    assert cases["warning"].find("failure") is None
    assert cases["warning"].find("skipped") is None
    assert cases["clean"].find("skipped") is not None
    assert cases["warning"].attrib["time"] == "0.200"

    out = tmp_path / "nested" / "report.xml"
    assert write_junit(report, out) == out
    assert ET.parse(out).getroot().attrib["tests"] == "3"


def test_cli_writes_junit(tmp_path, capsys):
    out = tmp_path / "report.xml"

    assert main(
        [
            "run",
            DIRTY,
            "--no-plugins",
            "--fail-on",
            "none",
            "--junit",
            str(out),
        ]
    ) == 0

    root = ET.parse(out).getroot()
    assert root.attrib["name"] == "datasets-lint"
    assert "junit →" in capsys.readouterr().out
