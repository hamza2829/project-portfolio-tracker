"""CSV/JSON boundary, validation gate, and atomic SQLite replacement."""
import json
from pathlib import Path
import sqlite3

import pandas as pd

from .schema import DataError, Portfolio, SCHEMA


def read_exports(directory, kind="csv"):
    if kind not in {"csv", "json"}:
        raise DataError(f"Unsupported export format: {kind}")
    tables = {}
    for name, columns in SCHEMA.items():
        path = Path(directory) / f"{name}.{kind}"
        if not path.is_file():
            raise DataError(f"Missing export file: {path}")
        try:
            if kind == "csv":
                frame = pd.read_csv(path, dtype=str, keep_default_na=False)
                records = frame.to_dict("records")
                headers = list(frame.columns)
            else:
                records = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
                    raise ValueError("JSON must be an array of objects")
                headers = list(records[0]) if records else columns
            if set(headers) != set(columns):
                raise ValueError(f"Expected columns {columns}; received {headers}")
            normalized = []
            for index, row in enumerate(records, 1):
                if set(row) != set(columns) or any(not isinstance(v, (str, int, float)) for v in row.values()):
                    raise ValueError(f"Row {index}: inconsistent columns or non-scalar value")
                normalized.append({key: str(row[key]) for key in columns})
            tables[name] = normalized
        except (ValueError, pd.errors.ParserError) as error:
            raise DataError(f"{path}: {error}") from error
    return Portfolio(tables)


def write_exports(portfolio, directory):
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    for name, columns in SCHEMA.items():
        pd.DataFrame(portfolio[name], columns=columns).to_csv(target / f"{name}.csv", index=False)
        (target / f"{name}.json").write_text(json.dumps(portfolio[name], indent=2) + "\n", encoding="utf-8")
    (target / "manifest.json").write_text(json.dumps({"synthetic_only": True, "schema_version": 1,
        "counts": {name: len(portfolio[name]) for name in SCHEMA}}, indent=2) + "\n", encoding="utf-8")


def save_database(portfolio, path):
    from .validation import validate

    findings = validate(portfolio)
    if findings:
        raise DataError("Import refused:\n" + "\n".join(map(str, findings)))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        for name, columns in SCHEMA.items():
            connection.execute(f'DROP TABLE IF EXISTS "{name}"')
            definition = ",".join(f'"{column}" TEXT NOT NULL' for column in columns)
            connection.execute(f'CREATE TABLE "{name}" ({definition})')
            placeholders = ",".join("?" for _ in columns)
            connection.executemany(f'INSERT INTO "{name}" VALUES ({placeholders})',
                [tuple(row[column] for column in columns) for row in portfolio[name]])


def read_database(path):
    path = Path(path)
    if not path.is_file():
        raise DataError(f"Database does not exist: {path}. Run validate first.")
    try:
        with sqlite3.connect(path) as connection:
            tables = {name: pd.read_sql_query(f'SELECT * FROM "{name}"', connection).to_dict("records") for name in SCHEMA}
    except (sqlite3.DatabaseError, pd.errors.DatabaseError) as error:
        raise DataError(f"Cannot read portfolio database {path}: {error}") from error
    portfolio = Portfolio(tables)
    from .validation import validate
    findings = validate(portfolio)
    if findings:
        raise DataError("Stored data is invalid:\n" + "\n".join(map(str, findings)))
    return portfolio
