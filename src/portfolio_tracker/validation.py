"""Collect every structural, ownership, date and reference problem in one pass."""
from dataclasses import dataclass

from .schema import KEYS, PRIORITIES, SCHEMA, STATUSES, iso_date, links, number


@dataclass(frozen=True)
class Finding:
    table: str
    element: str
    code: str
    message: str

    def __str__(self):
        return f"{self.table} [{self.element}] {self.code}: {self.message}"


def validate(portfolio):
    findings = []

    def add(table, key, code, message):
        findings.append(Finding(table, str(key), code, message))

    for name, columns in SCHEMA.items():
        seen = set()
        for index, row in enumerate(portfolio[name], 1):
            key = row.get(KEYS[name], f"row {index}")
            for column in columns:
                if column not in row:
                    add(name, key, "missing-column", f"Missing column {column}.")
            identity = tuple(row.get(c, "") for c in ({"updates": ["Project key", "Week"], "workload": ["Issue key", "Assignee", "Week"]}.get(name, [KEYS[name]])))
            if identity in seen:
                add(name, key, "duplicate-key", f"Duplicate identity {identity}.")
            seen.add(identity)
            for column in columns:
                if column not in row:
                    continue
                value = row[column]
                optional = column in {"Completed date", "Dependencies", "Milestone", "Next steps"}
                if not value.strip() and not optional:
                    add(name, key, "missing-value", f"{column} is required.")
                if column.endswith("date") or column == "Week":
                    if not value and optional:
                        continue
                    try:
                        parsed = iso_date(value)
                        if column == "Week" and parsed.weekday() != 0:
                            add(name, key, "invalid-week", f"Week {value} must be a Monday.")
                    except ValueError:
                        add(name, key, "invalid-date", f"{column}: {value!r} is not a valid ISO date.")
            if all(row.get(field) for field in ("Start date", "Due date")):
                try:
                    if iso_date(row["Start date"]) > iso_date(row["Due date"]):
                        add(name, key, "date-order", "Start date is after Due date.")
                except ValueError:
                    pass
            for column, minimum, maximum in [("Weekly capacity hours", 0.01, 168), ("Original estimate (h)", 0, float("inf")),
                    ("Remaining estimate (h)", 0, float("inf")), ("Planned hours", 0, 168), ("Probability", 0, 1), ("Impact", 1, 5)]:
                if column in row:
                    try:
                        if not minimum <= number(row[column]) <= maximum:
                            raise ValueError
                    except ValueError:
                        add(name, key, "invalid-number", f"{column} must be finite and between {minimum} and {maximum}.")
            if "Priority" in row and row["Priority"] not in PRIORITIES:
                add(name, key, "invalid-priority", f"Unknown priority {row['Priority']!r}.")
            allowed = STATUSES if name == "issues" else {"Open", "Done"} if name in {"actions", "risks"} else {"Green", "Amber", "Red"} if name == "updates" else None
            if allowed and row.get("Status") not in allowed:
                add(name, key, "invalid-status", f"Status must be one of {sorted(allowed)}.")

    # Incomplete rows were reported above. Do not hide other rows' reference problems.
    indexes = {name: {row.get(KEYS[name], "") for row in portfolio[name]} for name in SCHEMA}
    people_fields = {"projects": "Project lead", "issues": "Assignee", "risks": "Owner", "actions": "Owner", "workload": "Assignee"}
    for name, rows in portfolio.tables.items():
        for row in rows:
            key = row.get(KEYS[name], "unknown")
            if name != "projects" and "Project key" in row and row["Project key"] not in indexes["projects"]:
                add(name, key, "unknown-project", f"Unknown project {row['Project key']!r}.")
            person = people_fields.get(name)
            if person and row.get(person, "") not in indexes["members"]:
                add(name, key, "missing-owner", f"{person} {row.get(person, '')!r} is not a known member.")
            if name == "issues":
                for dependency in links(row.get("Dependencies", "")):
                    if dependency not in indexes["issues"]:
                        add(name, key, "broken-dependency", f"Predecessor {dependency!r} does not exist.")
                milestone = row.get("Milestone", "")
                if milestone and milestone not in indexes["milestones"]:
                    add(name, key, "unknown-milestone", f"Milestone {milestone!r} does not exist.")
                try:
                    if number(row.get("Remaining estimate (h)", "")) > number(row.get("Original estimate (h)", "")):
                        add(name, key, "estimate-order", "Remaining estimate exceeds original estimate.")
                    if row.get("Status") == "Done" and number(row.get("Remaining estimate (h)", "")) != 0:
                        add(name, key, "done-remaining", "Done task has remaining effort.")
                except ValueError:
                    pass
            if name == "milestones":
                for issue in links(row.get("Issue keys", "")):
                    if issue not in indexes["issues"]:
                        add(name, key, "broken-milestone-link", f"Linked issue {issue!r} does not exist.")
            if name == "workload" and row.get("Issue key") not in indexes["issues"]:
                add(name, key, "unknown-issue", f"Workload issue {key!r} does not exist.")

    graph = {row.get("Issue key", ""): links(row.get("Dependencies", "")) for row in portfolio["issues"]}
    pending = set(graph)
    while pending:
        ready = {key for key in pending if not (set(graph[key]) & pending)}
        if not ready:
            add("issues", ", ".join(sorted(pending)), "dependency-cycle", "Cycle prevents scheduling these tasks or their downstream dependents.")
            break
        pending -= ready
    return findings
