"""Simple Markdown action capture with validation before any database change."""
import hashlib
from pathlib import Path
import re

from .schema import DataError, iso_date, number
from .storage import read_database, save_database


def agenda(portfolio, as_of):
    people = {row["Account id"]: row["Display name"] for row in portfolio["members"]}
    lines = ["# Portfolio decision meeting", "", f"Review date: {as_of.isoformat()}. Synthetic data only.", "",
        "## Open actions", "", "| Action | Project | Owner | Due | Discussion |", "| --- | --- | --- | --- | --- |"]
    for row in sorted(portfolio["actions"], key=lambda row: (row["Due date"], row["Action key"])):
        if row["Status"] != "Done":
            label = "Overdue: close or replan" if iso_date(row["Due date"]) < as_of else "Confirm next step"
            lines.append(f"| {row['Action key']} | {row['Project key']} | {people[row['Owner']]} | {row['Due date']} | {label}: {clean(row['Summary'])} |")
    lines += ["", "## Open risks", "", "| Risk | Project | Owner | Due | Exposure | Decision needed |", "| --- | --- | --- | --- | --- | --- |"]
    for row in sorted(portfolio["risks"], key=lambda row: -number(row["Probability"]) * number(row["Impact"])):
        if row["Status"] == "Open":
            lines.append(f"| {row['Risk key']} | {row['Project key']} | {people[row['Owner']]} | {row['Due date']} | {number(row['Probability']) * number(row['Impact']):.2f} | {clean(row['Summary'])} |")
    lines += ["", "## Capture agreed actions", "", "Use one unchecked Markdown item per agreement. Identify the project, member id, ISO due date and summary:", "",
        "```text", "- [ ] P01 | m01 | 2026-10-07 | Confirm the acceptance threshold", "```", ""]
    return "\n".join(lines)


def clean(value):
    return str(value).replace("|", "/").replace("\n", " ").replace("\r", " ")


def parse_notes(text, portfolio, source="meeting.md"):
    projects = {row["Project key"] for row in portfolio["projects"]}
    people = {row["Account id"] for row in portfolio["members"]}
    actions, errors = [], []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not re.match(r"\s*- \[ \]", line):
            continue
        parts = [part.strip() for part in re.sub(r"^\s*- \[ \]\s*", "", line).split("|")]
        if len(parts) != 4:
            errors.append(f"Line {line_number}: expected project | owner | YYYY-MM-DD | summary.")
            continue
        project, owner, due, summary = parts
        if project not in projects:
            errors.append(f"Line {line_number}: unknown project {project!r}.")
        if owner not in people:
            errors.append(f"Line {line_number}: unknown owner {owner!r}.")
        try:
            iso_date(due)
        except ValueError:
            errors.append(f"Line {line_number}: invalid due date {due!r}.")
        if not summary:
            errors.append(f"Line {line_number}: an action summary is required.")
        identity = hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
        actions.append({"Action key": f"N-{identity}", "Project key": project, "Summary": summary, "Owner": owner,
            "Due date": due, "Status": "Open", "Source": Path(source).name})
    if errors:
        raise DataError("Meeting notes were not imported:\n" + "\n".join(errors))
    return list({row["Action key"]: row for row in actions}.values())


def import_notes(database, path):
    portfolio = read_database(database)
    incoming = parse_notes(Path(path).read_text(encoding="utf-8"), portfolio, str(path))
    known = {row["Action key"] for row in portfolio["actions"]}
    added = [row for row in incoming if row["Action key"] not in known]
    portfolio["actions"].extend(added)
    if added:
        save_database(portfolio, database)
    return len(added)
