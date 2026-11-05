"""One narrative supplies both the Markdown and paginated PDF review."""
from html import escape
from pathlib import Path

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .meetings import clean


def markdown_review(metrics):
    lines = [f"# Quarterly portfolio review: {metrics['quarter']}", "", f"Snapshot: {metrics['as_of']}. Synthetic planning data only.", "",
        "## Consolidated plans", "", "Progress is estimate-weighted completion. Delay is calendar days beyond the target. Risk exposure is probability times impact on a 1 to 5 scale.", "",
        "| Project and plan | Lead | Progress | Delay days | Exposure | Status |", "| --- | --- | --- | --- | --- | --- |"]
    for row in metrics["projects"]:
        lines.append(f"| {row['Project key']}: {clean(row['Project name'])} | {row['Project lead']} | {row['Progress percent']:.1f}% | {row['Milestone delay days']} | {row['Risk exposure']:.2f} | {row['Status']} |")
    lines += ["", "### Plan commitments", ""]
    for row in metrics["projects"]:
        lines.append(f"- {row['Project key']}, {row['Start date']} to {row['Due date']}: {clean(row['Goal'])} Latest reported status: {row['Reported status']}.")
    lines += ["", "## Gaps in status evidence", ""]
    lines += [f"- {row['Project key']} (lead {row['Owner']}): {row['Message']}" for row in metrics["gaps"]] or ["No stale or missing weekly updates at this snapshot."]
    lines += ["", "## Conflicting priorities and workload", "", "Hours are planned allocations, not recorded timesheets. Capacity comes from each member's weekly capacity field.", "",
        "| Person | Week | Planned hours | Capacity | Excess hours | Projects / priorities |", "| --- | --- | --- | --- | --- | --- |"]
    for row in metrics["conflicts"]:
        lines.append(f"| {clean(row['Display name'])} ({row['Assignee']}) | {row['Week']} | {row['Planned hours']:g} | {row['Capacity hours']:g} | {row['Overload hours']:g} | {row['Projects']} / {row['Priorities']} |")
    lines += ["", "## Timeline and dependency risks", "", f"The department network has a planned critical path of {metrics['critical_path']['duration_days']} business days.",
        "Critical path: " + " > ".join(metrics["critical_path"]["path"]), "",
        "CPM uses inclusive Monday to Friday durations, finish-to-start dependencies, zero lag and unlimited resources. It includes cross-project links. Planned release dates and person capacity do not constrain CPM.", "",
        "| Milestone | Project | Target | Snapshot forecast | Delay days |", "| --- | --- | --- | --- | --- |"]
    for row in metrics["milestones"]:
        if row["Delay days"] > 0:
            lines.append(f"| {row['Milestone key']} | {row['Project key']} | {row['Target date']} | {row['Forecast date']} | {row['Delay days']} |")
    lines += ["", f"Blocked or waiting tasks: {len(metrics['blocked'])}. The machine-readable analysis lists their unfinished predecessors.", "",
        "## Open risks and overdue actions", "", f"Open risk exposure: {metrics['risk_exposure']:.2f} score points. This is a prioritization score, not a monetary loss estimate.", "",
        "| Risk | Project | Owner | Due | Exposure | Risk description |", "| --- | --- | --- | --- | --- | --- |"]
    for row in metrics["risks"]:
        lines.append(f"| {row['Risk key']} | {row['Project key']} | {row['Owner']} | {row['Due date']} | {row['Exposure']:.2f} | {clean(row['Summary'])} |")
    lines += ["", "| Overdue action | Project | Owner | Due | Agreed action |", "| --- | --- | --- | --- | --- |"]
    for row in metrics["overdue_actions"]:
        lines.append(f"| {row['Action key']} | {row['Project key']} | {row['Owner']} | {row['Due date']} | {clean(row['Summary'])} |")
    lines += ["", "## Recommendations for management", ""]
    lines += [f"- {recommendation}" for recommendation in metrics["recommendations"]]
    return "\n".join(lines) + "\n"


def write_pdf(markdown, path):
    fonts = Path(reportlab.__file__).parent / "fonts"
    for name, filename in [("LabSans", "Vera.ttf"), ("LabSansBold", "VeraBd.ttf")]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("LabBody", fontName="LabSans", fontSize=9, leading=14, spaceAfter=7, alignment=TA_LEFT))
    styles.add(ParagraphStyle("LabTitle", fontName="LabSansBold", fontSize=21, leading=26, textColor=colors.HexColor("#172a46"), spaceAfter=16))
    styles.add(ParagraphStyle("LabHeading", fontName="LabSansBold", fontSize=13, leading=17, textColor=colors.HexColor("#172a46"), spaceBefore=14, spaceAfter=8, keepWithNext=True))
    styles.add(ParagraphStyle("LabCell", fontName="LabSans", fontSize=8, leading=11))
    story, table_rows = [], []
    recommendation_start = None

    def flush_table():
        if not table_rows:
            return
        count = len(table_rows[0])
        # Give descriptions room, while retaining useful date and numeric columns.
        weights = {
            "Project and plan": [2.3, 0.7, 0.8, 0.8, 0.8, 1],
            "Person": [1.6, 1.1, 0.85, 0.75, 0.85, 1.65],
            "Milestone": [1, 0.7, 1.2, 1.2, 0.7],
            "Risk": [0.8, 0.7, 0.7, 1.05, 0.7, 2.4],
            "Overdue action": [1, 0.75, 0.7, 1.1, 2.6],
        }.get(table_rows[0][0], [1] * count)
        wrapped = [[Paragraph(escape(cell), styles["LabCell"]) for cell in row] for row in table_rows]
        table = Table(wrapped, colWidths=[(A4[0] - 80) * weight / sum(weights) for weight in weights], repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dfeaf5")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7fb")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story.append(table)
        story.append(Spacer(1, 8))
        table_rows.clear()

    for line in markdown.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if not all(set(cell) <= {"-", ":", " "} for cell in cells):
                table_rows.append(cells)
            continue
        flush_table()
        if not line.strip():
            continue
        if line == "## Recommendations for management":
            recommendation_start = len(story)
        style = "LabTitle" if line.startswith("# ") else "LabHeading" if line.startswith(("## ", "### ")) else "LabBody"
        text = line.removeprefix("### ").removeprefix("## ").removeprefix("# ")
        if text.startswith("- "):
            story.append(KeepTogether([Paragraph(escape(text[2:]), styles[style], bulletText="- ")]))
        else:
            story.append(Paragraph(escape(text), styles[style]))
    flush_table()
    if recommendation_start is not None:
        story[recommendation_start:] = [KeepTogether(story[recommendation_start:])]

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("LabSans", 8)
        canvas.setFillColor(colors.HexColor("#53657c"))
        canvas.drawString(40, 22, "Synthetic portfolio lab | planning snapshot")
        canvas.drawRightString(A4[0] - 40, 22, f"Page {document.page}")
        canvas.restoreState()

    SimpleDocTemplate(str(path), pagesize=A4, rightMargin=40, leftMargin=40, topMargin=38, bottomMargin=40,
        title="Quarterly portfolio review", author="Synthetic portfolio lab").build(story, onFirstPage=footer, onLaterPages=footer)
