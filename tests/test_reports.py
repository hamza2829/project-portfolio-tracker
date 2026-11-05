from datetime import datetime
import json

from openpyxl import load_workbook
from pypdf import PdfReader
import pytest

from portfolio_tracker.calculations import analyze
from portfolio_tracker.dashboard import dashboard
from portfolio_tracker.reports import write_reports
from portfolio_tracker.review import markdown_review, write_pdf
from portfolio_tracker.schema import empty
from portfolio_tracker.workbook import safe_value


def test_report_outputs_share_same_measured_snapshot(mini, metrics, tmp_path):
    paths = write_reports(mini, metrics, tmp_path)
    assert {path.name for path in paths} == {"portfolio.xlsx", "dashboard.html", "quarterly-review.md", "quarterly-review.pdf", "analysis.json"}
    assert all(path.stat().st_size > 50 for path in paths)
    assert json.loads((tmp_path / "analysis.json").read_text())["projects"][0]["Progress percent"] == 43.75
    assert "43.8%" in (tmp_path / "quarterly-review.md").read_text()
    assert "43.8%" in (tmp_path / "dashboard.html").read_text()


def test_excel_typed_values_tabs_filters_and_conditional_formatting(mini, metrics, tmp_path):
    write_reports(mini, metrics, tmp_path)
    book = load_workbook(tmp_path / "portfolio.xlsx")
    assert book.sheetnames == ["Overview", "P01", "P02", "Risks", "Workload", "Actions"]
    assert book["Overview"]["D6"].value == 43.75
    assert book["Overview"]["F6"].value == 17
    assert len(book["Overview"].conditional_formatting) == 2
    assert len(book["Risks"].conditional_formatting) == 1
    assert len(book["Workload"].conditional_formatting) == 1
    assert book["Workload"]["D6"].value == 48
    assert book["Workload"]["F6"].value == 8
    assert book["Workload"]["G6"].number_format == "0%"
    assert isinstance(book["P01"]["E6"].value, datetime)
    assert isinstance(book["Workload"]["C6"].value, datetime)
    assert book["P01"].max_row == 9
    for page in book:
        assert page.freeze_panes == "C6"
        assert page.auto_filter.ref.startswith("A5:")
        assert not page.sheet_view.showGridLines


@pytest.mark.parametrize("text", ["=1+1", "+SUM(A1:A3)", "-1+1", "@SUM(A1)"])
def test_untrusted_text_cannot_become_excel_formula(text):
    assert safe_value(text) == "'" + text
    assert safe_value(42) == 42


def test_html_is_offline_escaped_and_has_three_svg_charts(mini, metrics):
    metrics["projects"][0]["Project name"] = '<script>alert("bad")</script>'
    text = dashboard(mini, metrics)
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "http://" not in text and "https://" not in text
    assert text.count('<svg ') == 3
    assert 'id="workload"' in text and 'id="timeline"' in text
    assert "48" in text and "Mira Fenn (40h)" in text


def test_review_contains_actual_plans_gaps_conflicts_and_recommendations(metrics):
    text = markdown_review(metrics)
    for heading in ["Consolidated plans", "Plan commitments", "Gaps in status evidence", "Conflicting priorities", "Timeline and dependency risks", "Open risks and overdue actions", "Recommendations for management"]:
        assert heading in text
    assert "Confirm acceptance evidence" in text
    assert "8 business days" in text
    assert "P01-1 > P01-2 > P01-4 > P02-1" in text
    assert "| Mira Fenn (m01) | 2026-07-06 | 48 | 40 | 8 |" in text
    assert text.rstrip().endswith(metrics["recommendations"][-1])


def test_pdf_text_matches_narrative_not_placeholder(metrics, tmp_path):
    path = tmp_path / "review.pdf"
    write_pdf(markdown_review(metrics), path)
    reader = PdfReader(path)
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert len(reader.pages) >= 2
    for phrase in ["2026-Q3", "P01", "P02", "43.8%", "8 business days", "Recommendations for management", "overloaded person-weeks"]:
        assert phrase in text
    assert text.rstrip().endswith(f"Page {len(reader.pages)}") or "Page 1" in text


def test_empty_reports_and_no_stale_gap_message(tmp_path):
    from datetime import date
    p = empty()
    metrics = analyze(p, date(2026, 7, 27), "2026-Q3")
    write_reports(p, metrics, tmp_path)
    assert "No stale or missing" in (tmp_path / "quarterly-review.md").read_text()
    assert load_workbook(tmp_path / "portfolio.xlsx").sheetnames == ["Overview", "Risks", "Workload", "Actions"]


def test_risk_description_cannot_add_markdown_columns(metrics):
    metrics["risks"][0]["Summary"] = "one | two\nthree"
    assert "one / two three" in markdown_review(metrics)
