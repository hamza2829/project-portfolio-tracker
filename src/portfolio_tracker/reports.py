"""Generate every format from one measured analysis snapshot."""
import json
from pathlib import Path

from .dashboard import dashboard
from .review import markdown_review, write_pdf
from .workbook import write_workbook


def write_reports(portfolio, metrics, directory):
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    narrative = markdown_review(metrics)
    (target / "quarterly-review.md").write_text(narrative, encoding="utf-8")
    write_pdf(narrative, target / "quarterly-review.pdf")
    write_workbook(portfolio, metrics, target / "portfolio.xlsx")
    (target / "dashboard.html").write_text(dashboard(portfolio, metrics), encoding="utf-8")
    (target / "analysis.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return [target / name for name in ["portfolio.xlsx", "dashboard.html", "quarterly-review.md", "quarterly-review.pdf", "analysis.json"]]
