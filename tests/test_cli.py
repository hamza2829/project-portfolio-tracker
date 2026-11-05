import json

import pytest

from portfolio_tracker.cli import main
from portfolio_tracker.storage import read_database, write_exports


def test_five_commands_full_pipeline(tmp_path, capsys):
    data, db, output = tmp_path / "exports", tmp_path / "tracker.sqlite", tmp_path / "reports"
    assert main(["generate-data", "--out", str(data)]) == 0
    counts = json.loads(capsys.readouterr().out)["counts"]
    assert counts["projects"] == 12 and counts["issues"] == 150 and counts["members"] == 8
    assert main(["validate", "--data", str(data), "--format", "json", "--db", str(db)]) == 0
    assert main(["report", "--db", str(db), "--out", str(output), "--as-of", "2026-09-30", "--quarter", "2026-Q3"]) == 0
    assert main(["agenda", "--db", str(db), "--out", str(output / "agenda.md"), "--as-of", "2026-09-30"]) == 0
    notes = tmp_path / "notes.md"
    notes.write_text("- [ ] P01 | m01 | 2026-10-07 | Confirm acceptance evidence\n")
    assert main(["notes", "--db", str(db), "--file", str(notes)]) == 0
    assert len(read_database(db)["actions"]) == 13
    assert (output / "agenda.md").is_file()
    assert (output / "portfolio.xlsx").is_file()


def test_validation_lists_findings_and_does_not_create_db(mini, tmp_path, capsys):
    mini["issues"][0]["Assignee"] = "missing"
    mini["issues"][1]["Dependencies"] = "missing"
    write_exports(mini, tmp_path / "exports")
    db = tmp_path / "not-created.sqlite"
    assert main(["validate", "--data", str(tmp_path / "exports"), "--db", str(db)]) == 1
    error = capsys.readouterr().err
    assert "missing-owner" in error and "broken-dependency" in error
    assert "Database was not changed" in error
    assert not db.exists()


def test_cli_readable_error_no_traceback(tmp_path, capsys):
    assert main(["report", "--db", str(tmp_path / "missing.sqlite"), "--out", str(tmp_path), "--as-of", "bad", "--quarter", "2026-Q3"]) == 1
    text = capsys.readouterr().err
    assert "ERROR:" in text and "does not exist" in text
    assert "Traceback" not in text


def test_cli_invalid_date_and_missing_notes(mini, tmp_path, capsys):
    from portfolio_tracker.storage import save_database
    db = tmp_path / "tracker.sqlite"
    save_database(mini, db)
    assert main(["agenda", "--db", str(db), "--out", str(tmp_path / "agenda.md"), "--as-of", "yesterday"]) == 1
    assert "Expected ISO date" in capsys.readouterr().err
    assert main(["notes", "--db", str(db), "--file", str(tmp_path / "missing.md")]) == 1


def test_argparse_requires_command_and_arguments():
    with pytest.raises(SystemExit) as error:
        main([])
    assert error.value.code == 2
