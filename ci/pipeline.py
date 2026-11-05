"""Exercise all five CLI commands in real subprocesses and verify persistence."""
import json
from pathlib import Path
import subprocess
import sys

from portfolio_tracker.storage import read_database, read_exports

root = Path("artifacts")
root.mkdir(exist_ok=True)


def run(*arguments):
    print("COMMAND:", "portfolio", *arguments, flush=True)
    subprocess.run([sys.executable, "-m", "portfolio_tracker.cli", *arguments], check=True)


run("generate-data", "--out", "artifacts/exports")
run("validate", "--data", "artifacts/exports", "--db", "artifacts/portfolio.sqlite")
run("validate", "--data", "artifacts/exports", "--format", "json", "--db", "artifacts/json.sqlite")
csv = read_database(root / "portfolio.sqlite")
assert csv == read_database(root / "json.sqlite")
assert len(csv["projects"]) == 12 and len(csv["issues"]) == 150 and len(csv["members"]) == 8
if Path("data/issues.csv").exists():
    assert csv == read_exports("data"), "Committed synthetic CSV differs from the seeded generator"
    assert csv == read_exports("data", "json"), "Committed synthetic JSON differs from the seeded generator"
notes = root / "meeting-notes.md"
notes.write_text("# Agreed decisions\n\n- [ ] P01 | m01 | 2026-10-07 | Confirm the cross-project acceptance threshold\n", encoding="utf-8")
run("notes", "--db", "artifacts/portfolio.sqlite", "--file", str(notes))
run("notes", "--db", "artifacts/portfolio.sqlite", "--file", str(notes))
after = read_database(root / "portfolio.sqlite")
assert len(after["actions"]) == len(csv["actions"]) + 1
assert after["actions"][-1]["Owner"] == "m01"
assert after["actions"][-1]["Due date"] == "2026-10-07"
run("agenda", "--db", "artifacts/portfolio.sqlite", "--out", "artifacts/reports/agenda.md", "--as-of", "2026-09-30")
assert "Confirm the cross-project acceptance threshold" in (root / "reports/agenda.md").read_text()
run("report", "--db", "artifacts/portfolio.sqlite", "--out", "artifacts/reports", "--as-of", "2026-09-30", "--quarter", "2026-Q3")
(root / "pipeline-proof.json").write_text(json.dumps({"csv_json_equal": True, "counts": {name: len(rows) for name, rows in csv.tables.items()},
    "notes_added": 1, "notes_second_import_added": 0, "actions_after_notes": len(after["actions"]), "all_five_commands_passed": True}, indent=2) + "\n")
