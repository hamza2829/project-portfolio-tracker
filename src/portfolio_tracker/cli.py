"""The five public commands. Errors have messages and nonzero status, no traceback."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

from .calculations import analyze
from .generate import generate
from .meetings import agenda, import_notes
from .reports import write_reports
from .schema import iso_date
from .storage import read_database, read_exports, save_database, write_exports
from .validation import validate


def parser():
    root = argparse.ArgumentParser(description="Synthetic project portfolio consolidation and reporting")
    commands = root.add_subparsers(dest="command", required=True)
    data = commands.add_parser("generate-data", help="Write synthetic CSV and JSON exports")
    data.add_argument("--out", type=Path, required=True)
    data.add_argument("--seed", type=int, default=2829)
    check = commands.add_parser("validate", help="Report all findings and import valid data atomically")
    check.add_argument("--data", type=Path, required=True)
    check.add_argument("--format", choices=["csv", "json"], default="csv")
    check.add_argument("--db", type=Path, default=Path("portfolio.sqlite"))
    report = commands.add_parser("report", help="Create Excel, static HTML, Markdown and PDF")
    report.add_argument("--db", type=Path, required=True)
    report.add_argument("--out", type=Path, required=True)
    report.add_argument("--as-of", required=True)
    report.add_argument("--quarter", required=True)
    meeting = commands.add_parser("agenda", help="Make a decision agenda from open actions and risks")
    meeting.add_argument("--db", type=Path, required=True)
    meeting.add_argument("--out", type=Path, required=True)
    meeting.add_argument("--as-of", required=True)
    notes = commands.add_parser("notes", help="Import unchecked Markdown agreements idempotently")
    notes.add_argument("--db", type=Path, required=True)
    notes.add_argument("--file", type=Path, required=True)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "generate-data":
            portfolio = generate(args.seed)
            write_exports(portfolio, args.out)
            print(json.dumps({"synthetic_only": True, "counts": {name: len(rows) for name, rows in portfolio.tables.items()}}))
        elif args.command == "validate":
            portfolio = read_exports(args.data, args.format)
            findings = validate(portfolio)
            if findings:
                for finding in findings:
                    print(finding, file=sys.stderr)
                print(f"Import refused: {len(findings)} finding(s). Database was not changed.", file=sys.stderr)
                return 1
            save_database(portfolio, args.db)
            print(f"Validation passed. Imported {len(portfolio['issues'])} tasks into {args.db}.")
        elif args.command == "report":
            portfolio = read_database(args.db)
            paths = write_reports(portfolio, analyze(portfolio, iso_date(args.as_of), args.quarter), args.out)
            print("Created reports:\n" + "\n".join(map(str, paths)))
        elif args.command == "agenda":
            text = agenda(read_database(args.db), iso_date(args.as_of))
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
            print(f"Created agenda: {args.out}")
        elif args.command == "notes":
            print(f"Imported {import_notes(args.db, args.file)} new action(s). Repeated agreements are not duplicated.")
    except (ValueError, OSError, sqlite3.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
