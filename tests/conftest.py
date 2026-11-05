from datetime import date

import pytest

from portfolio_tracker.calculations import analyze
from portfolio_tracker.schema import SCHEMA, empty


def record(table, **values):
    return {column: str(values.get(column, "")) for column in SCHEMA[table]}


@pytest.fixture
def mini():
    p = empty()
    p["members"].extend([record("members", **{"Account id": "m01", "Display name": "Mira Fenn", "Weekly capacity hours": 40}),
        record("members", **{"Account id": "m02", "Display name": "Nolan Voss", "Weekly capacity hours": 32})])
    for key, lead in [("P01", "m01"), ("P02", "m02")]:
        p["projects"].append(record("projects", **{"Project key": key, "Project name": "Synthetic " + key, "Project lead": lead,
            "Start date": "2026-07-06", "Due date": "2026-07-31", "Priority": "High", "Goal": "Confirm acceptance evidence"}))
    specs = [("P01-1", "P01", "2026-07-06", "2026-07-07", "Done", "", 16, 0, "m01"),
        ("P01-2", "P01", "2026-07-08", "2026-07-10", "In Progress", "P01-1", 24, 12, "m01"),
        ("P01-3", "P01", "2026-07-08", "2026-07-08", "To Do", "P01-1", 8, 8, "m02"),
        ("P01-4", "P01", "2026-07-13", "2026-07-14", "To Do", "P01-2;P01-3", 16, 16, "m02"),
        ("P02-1", "P02", "2026-07-06", "2026-07-06", "To Do", "P01-4", 8, 8, "m01")]
    for key, project, start, due, status, dependencies, estimate, remaining, owner in specs:
        p["issues"].append(record("issues", **{"Issue key": key, "Project key": project, "Summary": "Synthetic task " + key,
            "Issue Type": "Task", "Status": status, "Assignee": owner, "Start date": start, "Due date": due,
            "Original estimate (h)": estimate, "Remaining estimate (h)": remaining, "Priority": "High" if project == "P01" else "Low",
            "Dependencies": dependencies, "Milestone": project + "-M1"}))
        p["workload"].append(record("workload", **{"Issue key": key, "Assignee": owner, "Week": "2026-07-06", "Planned hours": estimate}))
    p["milestones"].extend([record("milestones", **{"Milestone key": "P01-M1", "Project key": "P01", "Summary": "Acceptance",
        "Target date": "2026-07-10", "Issue keys": "P01-2;P01-4"}), record("milestones", **{"Milestone key": "P02-M1", "Project key": "P02",
        "Summary": "Readiness", "Target date": "2026-07-30", "Completed date": "2026-07-28", "Issue keys": "P02-1"})])
    for key, project, probability, impact, status in [("R1", "P01", 0.5, 4, "Open"), ("R2", "P01", 0.9, 5, "Done"), ("R3", "P02", 0, 3, "Open")]:
        p["risks"].append(record("risks", **{"Risk key": key, "Project key": project, "Summary": "Synthetic acceptance risk", "Owner": "m01",
            "Due date": "2026-07-10", "Probability": probability, "Impact": impact, "Status": status}))
    for project, week in [("P01", "2026-07-06"), ("P02", "2026-07-20")]:
        p["updates"].append(record("updates", **{"Project key": project, "Week": week, "Status": "Amber", "Summary": "Synthetic weekly evidence", "Next steps": "Confirm decision"}))
    for key, status, due in [("A1", "Open", "2026-07-20"), ("A2", "Done", "2026-07-01"), ("A3", "Open", "2026-07-27")]:
        p["actions"].append(record("actions", **{"Action key": key, "Project key": "P01", "Summary": "Confirm the acceptance threshold", "Owner": "m01", "Due date": due, "Status": status, "Source": "synthetic fixture"}))
    return p


@pytest.fixture
def metrics(mini):
    return analyze(mini, date(2026, 7, 27), "2026-Q3")
