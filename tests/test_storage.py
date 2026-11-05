import json
import sqlite3

import pytest

from portfolio_tracker.schema import DataError, empty
from portfolio_tracker.storage import read_database, read_exports, save_database, write_exports


def test_csv_json_and_sqlite_round_trip(mini, tmp_path):
    write_exports(mini, tmp_path / "exports")
    assert read_exports(tmp_path / "exports", "csv") == mini
    assert read_exports(tmp_path / "exports", "json") == mini
    db = tmp_path / "nested" / "portfolio.sqlite"
    save_database(mini, db)
    assert read_database(db) == mini
    manifest = json.loads((tmp_path / "exports" / "manifest.json").read_text())
    assert manifest["synthetic_only"] is True
    assert manifest["counts"]["issues"] == 5


def test_empty_export_headers_and_empty_database(tmp_path):
    write_exports(empty(), tmp_path / "exports")
    assert read_exports(tmp_path / "exports") == empty()
    assert read_exports(tmp_path / "exports", "json") == empty()
    save_database(empty(), tmp_path / "empty.sqlite")
    assert read_database(tmp_path / "empty.sqlite") == empty()


def test_missing_export_and_unsupported_format(tmp_path):
    with pytest.raises(DataError, match="members.csv"):
        read_exports(tmp_path)
    with pytest.raises(DataError, match="Unsupported"):
        read_exports(tmp_path, "xml")


@pytest.mark.parametrize("payload", ["{broken", "{}", '["not an object"]', '[{"wrong": "field"}]'])
def test_bad_json_has_filename(mini, tmp_path, payload):
    write_exports(mini, tmp_path)
    (tmp_path / "members.json").write_text(payload)
    with pytest.raises(DataError, match="members.json"):
        read_exports(tmp_path, "json")


def test_inconsistent_json_row_and_nested_value(mini, tmp_path):
    write_exports(mini, tmp_path)
    records = mini["members"] + [{"Account id": "m03"}]
    (tmp_path / "members.json").write_text(json.dumps(records))
    with pytest.raises(DataError, match="Row 3"):
        read_exports(tmp_path, "json")
    records = mini["members"]
    records[0]["Display name"] = ["nested"]
    (tmp_path / "members.json").write_text(json.dumps(records))
    with pytest.raises(DataError, match="non-scalar"):
        read_exports(tmp_path, "json")


def test_wrong_csv_headers(mini, tmp_path):
    write_exports(mini, tmp_path)
    (tmp_path / "members.csv").write_text("bad,header\na,b\n")
    with pytest.raises(DataError, match="Expected columns"):
        read_exports(tmp_path)


def test_invalid_import_does_not_replace_database(mini, tmp_path):
    db = tmp_path / "portfolio.sqlite"
    save_database(mini, db)
    before = db.read_bytes()
    mini["issues"][0]["Assignee"] = "missing"
    with pytest.raises(DataError, match="Import refused"):
        save_database(mini, db)
    assert db.read_bytes() == before


def test_missing_corrupt_and_incomplete_database(tmp_path):
    with pytest.raises(DataError, match="does not exist"):
        read_database(tmp_path / "missing.sqlite")
    db = tmp_path / "bad.sqlite"
    db.write_text("not sqlite")
    with pytest.raises(DataError, match="Cannot read"):
        read_database(db)
    db.unlink()
    with sqlite3.connect(db):
        pass
    with pytest.raises(DataError, match="Cannot read"):
        read_database(db)


def test_tampered_database_is_revalidated(mini, tmp_path):
    db = tmp_path / "portfolio.sqlite"
    save_database(mini, db)
    with sqlite3.connect(db) as connection:
        connection.execute('UPDATE issues SET "Assignee" = ?', ("missing",))
    with pytest.raises(DataError, match="Stored data is invalid"):
        read_database(db)
