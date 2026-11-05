from copy import deepcopy

import pytest

from portfolio_tracker.generate import generate
from portfolio_tracker.schema import iso_date, links, number
from portfolio_tracker.validation import validate


def codes(portfolio):
    return {finding.code for finding in validate(portfolio)}


def test_hand_made_valid_model(mini):
    assert validate(mini) == []


def test_synthetic_generator_size_determinism_and_validity():
    one = generate(2829)
    assert len(one["projects"]) == 12
    assert len(one["issues"]) == 150
    assert len(one["members"]) == 8
    assert len(one["milestones"]) == 24
    assert len(one["updates"]) > 100
    assert validate(one) == []
    assert one == generate(2829)
    assert one != generate(2830)


@pytest.mark.parametrize("table,field", [("projects", "Project lead"), ("issues", "Assignee"), ("risks", "Owner"), ("actions", "Owner"), ("workload", "Assignee")])
def test_missing_owners_each_entity(mini, table, field):
    mini[table][0][field] = ""
    findings = validate(mini)
    assert any(row.table == table and row.code == "missing-owner" and field in row.message for row in findings)


@pytest.mark.parametrize("table,field", [("projects", "Start date"), ("projects", "Due date"), ("issues", "Due date"), ("milestones", "Target date"), ("risks", "Due date"), ("actions", "Due date"), ("updates", "Week")])
def test_invalid_dates_report_table_field_and_key(mini, table, field):
    mini[table][0][field] = "2026-02-30"
    finding = next(row for row in validate(mini) if row.table == table and row.code == "invalid-date")
    assert field in finding.message
    assert finding.element
    assert "invalid-date" in str(finding)


def test_non_monday_week(mini):
    mini["updates"][0]["Week"] = "2026-07-07"
    assert "invalid-week" in codes(mini)


def test_reversed_dates(mini):
    mini["issues"][0]["Start date"] = "2026-08-01"
    assert "date-order" in codes(mini)


@pytest.mark.parametrize("table,field,value", [("members", "Weekly capacity hours", "0"), ("members", "Weekly capacity hours", "169"),
    ("issues", "Original estimate (h)", "-1"), ("issues", "Remaining estimate (h)", "nan"), ("workload", "Planned hours", "inf"),
    ("risks", "Probability", "1.1"), ("risks", "Impact", "0"), ("risks", "Impact", "n/a")])
def test_invalid_number_bounds_and_finiteness(mini, table, field, value):
    mini[table][0][field] = value
    assert "invalid-number" in codes(mini)


@pytest.mark.parametrize("table", ["issues", "risks", "actions", "updates"])
def test_unknown_status_each_entity(mini, table):
    mini[table][0]["Status"] = "maybe"
    assert "invalid-status" in codes(mini)


def test_multiple_problems_are_all_reported(mini):
    mini["issues"][0]["Assignee"] = "missing"
    mini["issues"][1]["Dependencies"] = "P99-77;P99-78"
    mini["risks"][0]["Due date"] = "yesterday"
    mini["actions"][0]["Owner"] = "unknown"
    findings = validate(mini)
    assert len([row for row in findings if row.code == "broken-dependency"]) == 2
    assert {"missing-owner", "broken-dependency", "invalid-date"} <= {row.code for row in findings}


def test_cycle_finding_includes_affected_keys(mini):
    mini["issues"][0]["Dependencies"] = "P01-4"
    finding = next(row for row in validate(mini) if row.code == "dependency-cycle")
    assert "P01-1" in finding.element and "P01-4" in finding.element


def test_duplicate_id_and_composite_id(mini):
    mini["issues"].append(deepcopy(mini["issues"][0]))
    mini["workload"].append(deepcopy(mini["workload"][0]))
    mini["updates"].append(deepcopy(mini["updates"][0]))
    assert {row.table for row in validate(mini) if row.code == "duplicate-key"} == {"issues", "workload", "updates"}


def test_missing_column_does_not_stop_other_findings(mini):
    del mini["issues"][0]["Summary"]
    mini["issues"][1]["Priority"] = "Urgent"
    assert {"missing-column", "invalid-priority"} <= codes(mini)


def test_broken_project_milestone_and_workload_references(mini):
    mini["issues"][0]["Project key"] = "missing"
    mini["issues"][0]["Milestone"] = "missing"
    mini["milestones"][0]["Issue keys"] = "missing"
    mini["workload"][0]["Issue key"] = "missing"
    assert {"unknown-project", "unknown-milestone", "broken-milestone-link", "unknown-issue"} <= codes(mini)


def test_remaining_estimate_constraints(mini):
    mini["issues"][0]["Remaining estimate (h)"] = "20"
    assert {"estimate-order", "done-remaining"} <= codes(mini)


def test_iso_dates_strict_and_links_trimmed():
    assert iso_date("2024-02-29").day == 29
    for value in ["2026-2-01", "2026-02-29", "2026-07-01T12:00", None]:
        with pytest.raises(ValueError):
            iso_date(value)
    assert links(" A ; ; B ") == ["A", "B"]
    with pytest.raises(ValueError):
        number("inf")
