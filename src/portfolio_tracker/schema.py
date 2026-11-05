"""Jira-shaped tables and lossless string values at the import boundary."""
from dataclasses import dataclass
from datetime import date
import math
import re

SCHEMA = {
    "members": ["Account id", "Display name", "Weekly capacity hours"],
    "projects": ["Project key", "Project name", "Project lead", "Start date", "Due date", "Priority", "Goal"],
    "issues": ["Issue key", "Project key", "Summary", "Issue Type", "Status", "Assignee", "Start date", "Due date", "Original estimate (h)", "Remaining estimate (h)", "Priority", "Dependencies", "Milestone"],
    "milestones": ["Milestone key", "Project key", "Summary", "Target date", "Completed date", "Issue keys"],
    "risks": ["Risk key", "Project key", "Summary", "Owner", "Due date", "Probability", "Impact", "Status"],
    "updates": ["Project key", "Week", "Status", "Summary", "Next steps"],
    "workload": ["Issue key", "Assignee", "Week", "Planned hours"],
    "actions": ["Action key", "Project key", "Summary", "Owner", "Due date", "Status", "Source"],
}
KEYS = {name: columns[0] for name, columns in SCHEMA.items()}
STATUSES = {"To Do", "In Progress", "Blocked", "Done"}
PRIORITIES = {"High", "Medium", "Low"}


class DataError(ValueError):
    """Readable input error suitable for CLI output."""


@dataclass
class Portfolio:
    tables: dict[str, list[dict[str, str]]]

    def __getitem__(self, name):
        return self.tables[name]


def iso_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"Expected ISO date YYYY-MM-DD, got {value!r}")
    return date.fromisoformat(value)


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Expected a finite number, got {value!r}")
    return result


def links(value):
    return [key.strip() for key in value.split(";") if key.strip()]


def empty():
    return Portfolio({name: [] for name in SCHEMA})
