"""Repeatable fictional Jira-style records with real planning tensions."""
from datetime import date, timedelta
import random

from .schema import SCHEMA, Portfolio


def generate(seed=2829):
    rng = random.Random(seed)
    rows = {name: [] for name in SCHEMA}
    people = ["Mira Fenn", "Nolan Voss", "Tessa Lark", "Arin Vale", "Lina Kest", "Oren Pike", "Sora Wren", "Elian Moss"]
    for index, name in enumerate(people, 1):
        rows["members"].append(dict(zip(SCHEMA["members"], [f"m{index:02}", name, "32" if index == 1 else "40"], strict=True)))
    titles = ["Atlas route planner", "Birch data catalog", "Cedar quality monitor", "Delta dispatch desk", "Ember access review", "Fjord forecast engine", "Grove workflow kit", "Harbor migration", "Indigo test platform", "Juniper insight hub", "Kestrel event store", "Lumen service portal"]
    start = date(2026, 7, 6)

    def append(table, values):
        rows[table].append({key: str(value) for key, value in zip(SCHEMA[table], values, strict=True)})

    for project_index, title in enumerate(titles):
        key = f"P{project_index + 1:02}"
        owner = f"m{project_index % 8 + 1:02}"
        priority = ["High", "Medium", "Low"][project_index % 3]
        project_start = start + timedelta(days=project_index * 2)
        project_end = project_start + timedelta(days=70 + project_index * 2)
        append("projects", [key, title, owner, project_start, project_end, priority, f"Deliver the fictional {title.lower()} with documented acceptance checks."])
        count = 13 if project_index < 6 else 12
        issue_keys = [f"{key}-{index + 1}" for index in range(count)]
        for index, issue in enumerate(issue_keys):
            task_start = project_start + timedelta(days=index * 5)
            task_end = task_start + timedelta(days=rng.choice([3, 4, 7, 9]))
            estimate = rng.choice([8, 16, 24, 32, 40])
            status = "Done" if index < 4 else "Blocked" if index == 6 else "In Progress" if index < 9 else "To Do"
            remaining = 0 if status == "Done" else estimate / 2 if status == "In Progress" else estimate
            assignee = f"m{(project_index + index) % 8 + 1:02}"
            dependency = issue_keys[index - 1] if index > 0 else ""
            if project_index == 1 and index == 0:
                dependency = "P01-3"  # An explicit cross-project predecessor.
            milestone = f"{key}-M{1 if index < 6 else 2}"
            append("issues", [issue, key, f"{['Design', 'Build', 'Verify'][index % 3]} synthetic component {index + 1}", "Task", status, assignee,
                task_start, task_end, estimate, remaining, priority, dependency, milestone])
            week = task_start - timedelta(days=task_start.weekday())
            append("workload", [issue, assignee, week, estimate])
        for index in [1, 2]:
            linked = issue_keys[:6] if index == 1 else issue_keys[6:]
            append("milestones", [f"{key}-M{index}", key, "Prototype acceptance" if index == 1 else "Service readiness",
                project_start + timedelta(days=25 if index == 1 else 60), "", ";".join(linked)])
        for risk_index in range(1 if project_index < 6 else 2):
            append("risks", [f"R{project_index + 1:02}-{risk_index + 1}", key,
                ["Synthetic acceptance benchmark may be missed", "Migration rehearsal may need another iteration"][risk_index], owner,
                date(2026, 9, 14) + timedelta(days=project_index * 3), ["0.3", "0.6", "0.8"][project_index % 3],
                2 + project_index % 4, "Done" if project_index == 11 else "Open"])
        for week_index in range(13 if project_index % 4 else 9):
            append("updates", [key, start + timedelta(weeks=week_index), ["Green", "Amber", "Red"][project_index % 3],
                "Synthetic weekly status: acceptance evidence is being consolidated.", "Confirm the next milestone and ownership."])
        append("actions", [f"A{project_index + 1:02}", key, "Agree the next acceptance decision", owner,
            date(2026, 9, 18) + timedelta(days=project_index * 2), "Done" if project_index == 10 else "Open", "synthetic planning export"])
    # Deliberately conflicting priorities for one person in one week, with unique allocation keys.
    for project in ["P01", "P02", "P03"]:
        append("workload", [f"{project}-12", "m01", "2026-09-21", "24"])
    return Portfolio(rows)
