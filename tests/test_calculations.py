from datetime import date

import pytest

from portfolio_tracker.calculations import analyze, blocked_tasks, business_days, critical_path, milestone_delay, progress, quarter_bounds, workload
from portfolio_tracker.schema import empty


def test_hand_checked_diamond_and_cross_project_path(mini):
    result = critical_path(mini["issues"])
    assert result["duration_days"] == 8  # 2 + 3 + 2 + 1, not the shorter parallel branch.
    assert result["path"] == ["P01-1", "P01-2", "P01-4", "P02-1"]
    assert result["earliest_start"]["P02-1"] == 7


def test_cpm_slack_uses_backward_pass(mini):
    result = critical_path(mini["issues"])
    assert result["slack_days"]["P01-3"] == 2
    assert all(result["slack_days"][key] == 0 for key in result["path"])


def test_disconnected_path_uses_longest_duration(mini):
    mini["issues"][-1]["Dependencies"] = ""
    assert critical_path(mini["issues"])["duration_days"] == 7


def test_cycle_is_not_silently_scheduled(mini):
    mini["issues"][0]["Dependencies"] = "P02-1"
    with pytest.raises(ValueError, match="cycle"):
        critical_path(mini["issues"])


def test_missing_predecessor_rejected_by_cpm(mini):
    mini["issues"][0]["Dependencies"] = "missing"
    with pytest.raises(ValueError, match="Broken dependency"):
        critical_path(mini["issues"])


def test_duplicate_keys_rejected_by_cpm(mini):
    with pytest.raises(ValueError, match="Duplicate"):
        critical_path(mini["issues"] + [mini["issues"][0]])


def test_empty_cpm():
    assert critical_path([])["path"] == []
    assert critical_path([])["duration_days"] == 0


@pytest.mark.parametrize("start,end,expected", [("2026-07-03", "2026-07-06", 2), ("2026-07-04", "2026-07-05", 0), ("2026-07-06", "2026-07-06", 1)])
def test_inclusive_business_duration(start, end, expected):
    assert business_days(start, end) == expected


def test_reverse_duration_rejected():
    with pytest.raises(ValueError, match="precedes"):
        business_days("2026-07-07", "2026-07-06")


def test_estimate_weighted_progress(mini):
    assert progress(mini["issues"][:4]) == 43.75  # (64 - 36) / 64, not one done task / four.


def test_zero_estimate_progress_and_empty(mini):
    for row in mini["issues"]:
        row["Original estimate (h)"] = row["Remaining estimate (h)"] = "0"
    assert progress(mini["issues"]) == 20
    assert progress([]) == 0


def test_blocked_includes_implicit_and_explicit_not_done(mini):
    mini["issues"][1]["Status"] = "Blocked"
    result = blocked_tasks(mini["issues"])
    assert {row["Issue key"] for row in result} == {"P01-2", "P01-4", "P02-1"}
    assert result[1]["Unfinished predecessors"] == ["P01-2", "P01-3"]


def test_milestone_calendar_delay_and_overdue_floor(mini):
    result = milestone_delay(mini["milestones"][0], mini["issues"], date(2026, 7, 20))
    assert result["Forecast date"] == "2026-07-20"
    assert result["Delay days"] == 10


def test_completed_milestone_uses_actual_date_and_clamps_early(mini):
    row = mini["milestones"][1]
    assert milestone_delay(row, mini["issues"], date(2026, 7, 29))["Delay days"] == 0
    row["Completed date"] = "2026-08-02"
    assert milestone_delay(row, mini["issues"], date(2026, 8, 3))["Delay days"] == 3


def test_empty_milestone_has_target_forecast(mini):
    mini["milestones"][0]["Issue keys"] = ""
    assert milestone_delay(mini["milestones"][0], [], date(2026, 7, 20))["Forecast date"] == "2026-07-10"


def test_workload_joins_projects_and_priorities(mini):
    result = workload(mini)
    first = result[0]
    assert first["Planned hours"] == 48
    assert first["Capacity hours"] == 40
    assert first["Overload hours"] == 8
    assert first["Utilization"] == 1.2
    assert first["Projects"] == "P01;P02"
    assert first["Priorities"] == "High;Low"
    assert result[1]["Overload hours"] == 0


def test_capacity_boundary_not_overload(mini):
    mini["members"][0]["Weekly capacity hours"] = "48"
    assert workload(mini)[0]["Overload hours"] == 0
    assert workload(empty()) == []


def test_review_real_risk_overdue_staleness_and_status(metrics):
    assert metrics["risk_exposure"] == 2
    assert len(metrics["risks"]) == 2
    assert [row["Action key"] for row in metrics["overdue_actions"]] == ["A1"]
    assert [row["Project key"] for row in metrics["gaps"]] == ["P01"]
    assert metrics["projects"][0]["Status"] == "Off track"
    assert metrics["projects"][1]["Status"] == "At risk"
    assert metrics["projects"][1]["Network finish day"] == 8
    assert metrics["conflicts"][0]["Overload hours"] == 8


def test_review_on_track_and_missing_update(mini):
    for row in mini["issues"]:
        row["Status"] = "Done"
        row["Remaining estimate (h)"] = "0"
    for row in mini["milestones"]:
        row["Completed date"] = row["Target date"]
    mini.tables["risks"] = []
    mini.tables["updates"] = []
    result = analyze(mini, date(2026, 7, 27), "2026-Q3")
    assert all(row["Status"] == "On track" for row in result["projects"])
    assert len(result["gaps"]) == 2
    assert result["projects"][0]["Reported status"] == "Missing"


@pytest.mark.parametrize("quarter,expected", [("2026-Q1", ("2026-01-01", "2026-03-31")), ("2024-Q1", ("2024-01-01", "2024-03-31")), ("2026-Q4", ("2026-10-01", "2026-12-31"))])
def test_quarter_bounds(quarter, expected):
    assert tuple(day.isoformat() for day in quarter_bounds(quarter)) == expected


def test_quarter_and_snapshot_rejected(mini):
    with pytest.raises(ValueError, match="Quarter"):
        quarter_bounds("Q3-2026")
    with pytest.raises(ValueError, match="inside"):
        analyze(mini, date(2026, 10, 1), "2026-Q3")


def test_review_filters_future_allocations_and_updates(mini):
    mini["workload"][0]["Week"] = "2026-10-05"
    mini["updates"][0]["Week"] = "2026-08-03"
    result = analyze(mini, date(2026, 7, 27), "2026-Q3")
    assert all(row["Week"] <= "2026-07-27" for row in result["workload"])
    assert result["projects"][0]["Reported status"] == "Missing"


def test_empty_portfolio_review():
    result = analyze(empty(), date(2026, 7, 27), "2026-Q3")
    assert result["projects"] == []
    assert result["risk_exposure"] == 0
