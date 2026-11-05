"""Read test and coverage reports; never infer measured results from source counts."""
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

root = Path("artifacts")
tests = list(ET.parse(root / "tests.xml").getroot().iter("testcase"))
failures = sum(any(case.find(tag) is not None for tag in ["failure", "error"]) for case in tests)
skipped = sum(case.find("skipped") is not None for case in tests)
coverage = ET.parse(root / "coverage.xml").getroot()
covered, valid = int(coverage.attrib["lines-covered"]), int(coverage.attrib["lines-valid"])
assert len(tests) >= 40 and failures == 0 and skipped == 0
assert covered / valid >= 0.85
pipeline = json.loads((root / "pipeline-proof.json").read_text())
visual = json.loads((root / "visual-proof.json").read_text())
assert pipeline["all_five_commands_passed"] and visual["browser_errors"] == []
run = f'https://github.com/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{os.environ["GITHUB_RUN_ID"]}'
metrics = {"tests": len(tests), "failures": failures, "skipped": skipped, "line_coverage_percent": round(100 * covered / valid, 2),
    "covered_lines": covered, "measured_lines": valid, "synthetic_counts": pipeline["counts"], "pdf_pages": visual["pdf_pages"],
    "commit": os.environ["GITHUB_SHA"], "run_url": run}
(root / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
table = f'| Metric | Measured in CI |\n| --- | ---: |\n| pytest cases | {len(tests)} |\n| Line coverage | {metrics["line_coverage_percent"]:.2f}% ({covered}/{valid}) |\n| Failures / skipped | {failures} / {skipped} |\n'
(root / "metrics.md").write_text(table)
print(json.dumps(metrics, indent=2))
with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
    summary.write(table)
for name in subprocess.run(["git", "ls-files", "-z"], check=True, capture_output=True, text=True).stdout.split("\0"):
    if name and Path(name).suffix not in {".png", ".pdf", ".xlsx"}:
        assert chr(0x2014) not in Path(name).read_text(encoding="utf-8"), name
