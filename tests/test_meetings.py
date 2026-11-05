from datetime import date

import pytest

from portfolio_tracker.meetings import agenda, clean, import_notes, parse_notes
from portfolio_tracker.schema import DataError
from portfolio_tracker.storage import read_database, save_database


def test_agenda_open_actions_risks_due_dates_and_owners(mini):
    text = agenda(mini, date(2026, 7, 27))
    assert "A1" in text and "A3" in text and "A2" not in text
    assert "R1" in text and "R3" in text and "R2" not in text
    assert "Mira Fenn" in text and "2026-07-20" in text
    assert "Overdue: close or replan" in text
    assert "Confirm next step" in text


def test_notes_parse_real_markdown(mini):
    text = "# Decisions\nWe discussed the benchmark.\n- [ ] P01 | m02 | 2026-08-04 | Record acceptance evidence\n- [x] already closed\n"
    actions = parse_notes(text, mini, "/safe/path/review.md")
    assert len(actions) == 1
    assert actions[0]["Owner"] == "m02"
    assert actions[0]["Due date"] == "2026-08-04"
    assert actions[0]["Summary"] == "Record acceptance evidence"
    assert actions[0]["Source"] == "review.md"
    assert actions[0]["Status"] == "Open"


@pytest.mark.parametrize("line,message", [("- [ ] only one field", "expected project"), ("- [ ] P99 | m01 | 2026-08-04 | Test", "unknown project"),
    ("- [ ] P01 | nobody | 2026-08-04 | Test", "unknown owner"), ("- [ ] P01 | m01 | 2026-02-30 | Test", "invalid due date"),
    ("- [ ] P01 | m01 | 2026-08-04 | ", "summary is required")])
def test_bad_agreements_have_line_numbers(mini, line, message):
    with pytest.raises(DataError, match="Line 2") as error:
        parse_notes("# Notes\n" + line, mini)
    assert message in str(error.value)


def test_all_note_errors_reported_and_no_partial_commit(mini, tmp_path):
    db, notes = tmp_path / "portfolio.sqlite", tmp_path / "notes.md"
    save_database(mini, db)
    notes.write_text("- [ ] P01 | m01 | 2026-08-04 | Valid\n- [ ] P99 | no | yesterday | Invalid\n")
    with pytest.raises(DataError) as error:
        import_notes(db, notes)
    assert "unknown project" in str(error.value) and "unknown owner" in str(error.value) and "invalid due date" in str(error.value)
    assert len(read_database(db)["actions"]) == 3


def test_note_import_is_idempotent_and_survives_reload(mini, tmp_path):
    db, notes = tmp_path / "portfolio.sqlite", tmp_path / "notes.md"
    save_database(mini, db)
    notes.write_text("- [ ] P01 | m01 | 2026-08-04 | Confirm the threshold\n" * 2)
    assert import_notes(db, notes) == 1
    assert import_notes(db, notes) == 0
    assert read_database(db)["actions"][-1]["Summary"] == "Confirm the threshold"
    notes.write_text("Discussion only.\n")
    assert import_notes(db, notes) == 0


def test_summary_is_stored_as_data_not_sql(mini, tmp_path):
    db, notes = tmp_path / "portfolio.sqlite", tmp_path / "notes.md"
    save_database(mini, db)
    notes.write_text("- [ ] P01 | m01 | 2026-08-04 | '); DROP TABLE issues; --\n")
    assert import_notes(db, notes) == 1
    assert len(read_database(db)["issues"]) == 5


def test_markdown_table_values_cannot_add_columns():
    assert clean("A|B\nC\rD") == "A/B C D"
