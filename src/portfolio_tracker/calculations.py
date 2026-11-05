"""Explainable snapshot metrics; no resource leveling or probabilistic forecast."""
from datetime import date, timedelta
import re

import pandas as pd

from .schema import iso_date, links, number


def business_days(start, end):
    first, last = iso_date(start), iso_date(end)
    if last < first:
        raise ValueError("End precedes start")
    return sum((first + timedelta(days=offset)).weekday() < 5 for offset in range((last - first).days + 1))


def critical_path(issues):
    """Finish-to-start CPM, inclusive weekday durations, zero lag, unlimited resources."""
    graph = {row["Issue key"]: row for row in issues}
    if len(graph) != len(issues):
        raise ValueError("Duplicate issue key in critical path")
    predecessors = {key: links(row["Dependencies"]) for key, row in graph.items()}
    if any(dep not in graph for deps in predecessors.values() for dep in deps):
        raise ValueError("Broken dependency in critical path")
    duration = {key: business_days(row["Start date"], row["Due date"]) for key, row in graph.items()}
    finish, begin, chain, order = {}, {}, {}, []
    pending = set(graph)
    while pending:
        ready = sorted(key for key in pending if all(dep in finish for dep in predecessors[key]))
        if not ready:
            raise ValueError("Dependency cycle prevents critical path calculation")
        for key in ready:
            previous = max(predecessors[key], key=lambda dep: (finish[dep], dep), default=None)
            begin[key] = finish[previous] if previous else 0
            finish[key] = begin[key] + duration[key]
            chain[key] = chain[previous] + [key] if previous else [key]
            order.append(key)
        pending.difference_update(ready)
    last = max(finish, key=lambda key: (finish[key], key), default=None)
    total = finish[last] if last else 0
    successors = {key: [] for key in graph}
    for key, deps in predecessors.items():
        for dep in deps:
            successors[dep].append(key)
    latest, slack = {}, {}
    for key in reversed(order):
        latest[key] = min((latest[child] for child in successors[key]), default=total) - duration[key]
        slack[key] = latest[key] - begin[key]
    return {"duration_days": total, "path": chain[last] if last else [], "earliest_start": begin, "earliest_finish": finish, "slack_days": slack}


def progress(issues):
    if not issues:
        return 0.0
    original = sum(number(row["Original estimate (h)"]) for row in issues)
    remaining = sum(number(row["Remaining estimate (h)"]) for row in issues)
    if original == 0:
        return round(100 * sum(row["Status"] == "Done" for row in issues) / len(issues), 2)
    return round(100 * (original - remaining) / original, 2)


def blocked_tasks(issues):
    states = {row["Issue key"]: row["Status"] for row in issues}
    return [{**row, "Unfinished predecessors": [dep for dep in links(row["Dependencies"]) if states.get(dep) != "Done"]}
        for row in issues if row["Status"] != "Done" and (row["Status"] == "Blocked" or any(states.get(dep) != "Done" for dep in links(row["Dependencies"])))]


def milestone_delay(milestone, issues, as_of):
    target = iso_date(milestone["Target date"])
    if milestone["Completed date"]:
        forecast = iso_date(milestone["Completed date"])
    else:
        keys = set(links(milestone["Issue keys"]))
        selected = [row for row in issues if row["Issue key"] in keys]
        forecast = max((iso_date(row["Due date"]) for row in selected), default=target)
        if any(row["Status"] != "Done" for row in selected):
            forecast = max(forecast, as_of)
    return {**milestone, "Forecast date": forecast.isoformat(), "Delay days": max(0, (forecast - target).days)}


def quarter_bounds(quarter):
    if not re.fullmatch(r"\d{4}-Q[1-4]", quarter):
        raise ValueError("Quarter must have format YYYY-Q1 through YYYY-Q4")
    year, part = int(quarter[:4]), int(quarter[-1])
    first = date(year, (part - 1) * 3 + 1, 1)
    following = date(year + 1, 1, 1) if part == 4 else date(year, part * 3 + 1, 1)
    return first, following - timedelta(days=1)


def workload(portfolio):
    if not portfolio["workload"]:
        return []
    frame = pd.DataFrame(portfolio["workload"])
    frame["Planned hours"] = pd.to_numeric(frame["Planned hours"])
    tasks = {row["Issue key"]: row for row in portfolio["issues"]}
    members = {row["Account id"]: row for row in portfolio["members"]}
    result = []
    for (owner, week), group in frame.groupby(["Assignee", "Week"], sort=True):
        hours = float(group["Planned hours"].sum())
        capacity = number(members[owner]["Weekly capacity hours"])
        projects = sorted({tasks[key]["Project key"] for key in group["Issue key"]})
        priorities = sorted({tasks[key]["Priority"] for key in group["Issue key"]})
        result.append({"Assignee": owner, "Display name": members[owner]["Display name"], "Week": week, "Planned hours": hours,
            "Capacity hours": capacity, "Overload hours": max(0, hours - capacity), "Utilization": hours / capacity,
            "Projects": ";".join(projects), "Priorities": ";".join(priorities)})
    return result


def analyze(portfolio, as_of, quarter):
    first, last = quarter_bounds(quarter)
    if not first <= as_of <= last:
        raise ValueError("As-of date must be inside the selected review quarter")
    network = critical_path(portfolio["issues"])
    blocked = blocked_tasks(portfolio["issues"])
    milestones = [milestone_delay(row, portfolio["issues"], as_of) for row in portfolio["milestones"]]
    loads = [row for row in workload(portfolio) if first <= iso_date(row["Week"]) <= as_of]
    risks = [{**row, "Exposure": round(number(row["Probability"]) * number(row["Impact"]), 3),
        "Overdue": iso_date(row["Due date"]) < as_of} for row in portfolio["risks"] if row["Status"] == "Open"]
    actions = [row for row in portfolio["actions"] if row["Status"] != "Done"]
    overdue = [row for row in actions if iso_date(row["Due date"]) < as_of]
    projects, gaps = [], []
    for project in portfolio["projects"]:
        key = project["Project key"]
        tasks = [row for row in portfolio["issues"] if row["Project key"] == key]
        updates = [row for row in portfolio["updates"] if row["Project key"] == key and first <= iso_date(row["Week"]) <= as_of]
        latest = max(updates, key=lambda row: row["Week"], default=None)
        if not latest or (as_of - iso_date(latest["Week"])).days > 14:
            gaps.append({"Project key": key, "Message": "Missing a status update within 14 days of the review date.", "Owner": project["Project lead"]})
        delay = max((row["Delay days"] for row in milestones if row["Project key"] == key), default=0)
        exposure = round(sum(row["Exposure"] for row in risks if row["Project key"] == key), 3)
        blocked_count = sum(row["Project key"] == key for row in blocked)
        status = "Off track" if delay > 7 else "At risk" if delay or blocked_count or exposure >= 2 else "On track"
        completion = max((network["earliest_finish"][row["Issue key"]] for row in tasks), default=0)
        projects.append({**project, "Progress percent": progress(tasks), "Status": status, "Milestone delay days": delay,
            "Risk exposure": exposure, "Blocked tasks": blocked_count, "Network finish day": completion,
            "Reported status": latest["Status"] if latest else "Missing"})
    conflicts = sorted([row for row in loads if row["Overload hours"] > 0], key=lambda row: (-row["Overload hours"], row["Assignee"], row["Week"]))
    recommendations = [f"Rebalance {len(conflicts)} overloaded person-weeks before accepting new commitments.",
        f"Confirm recovery plans for {sum(row['Delay days'] > 0 for row in milestones)} delayed milestones; assign one decision owner per plan.",
        f"Close or replan {len(overdue)} overdue actions and review {sum(row['Overdue'] for row in risks)} overdue open risks.",
        f"Request current evidence from the leads of {len(gaps)} projects with stale status updates.",
        "Review the dependency critical path before changing milestone dates. Resource conflicts are not included in CPM duration."]
    return {"as_of": as_of.isoformat(), "quarter": quarter, "projects": projects, "milestones": milestones, "critical_path": network,
        "blocked": blocked, "risks": sorted(risks, key=lambda row: (-row["Exposure"], row["Risk key"])), "risk_exposure": round(sum(row["Exposure"] for row in risks), 3),
        "workload": loads, "conflicts": conflicts, "actions": actions, "overdue_actions": overdue, "gaps": gaps, "recommendations": recommendations,
        "counts": {name: len(rows) for name, rows in portfolio.tables.items()}}
