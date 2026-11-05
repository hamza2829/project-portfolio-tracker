"""Readable, typed Excel snapshots with bounded conditional formatting."""
from datetime import date

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .schema import iso_date, number


def safe_value(value):
    # Treat imported text as text. No external export may introduce an Excel formula.
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def sheet(book, name, title, headers, rows, widths, as_of):
    page = book.create_sheet(name)
    page.sheet_view.showGridLines = False
    page.sheet_properties.pageSetUpPr.fitToPage = True
    page.page_setup.orientation = "landscape"
    page.page_setup.paperSize = page.PAPERSIZE_A3
    page.page_setup.fitToWidth = 1
    page.page_setup.fitToHeight = 0
    page.print_title_rows = "1:5"
    page["A2"] = title
    page["A2"].font = Font(name="Arial", size=15, bold=True, color="172A46")
    page["A3"] = f"Synthetic data | snapshot {as_of} | static report"
    page["A3"].font = Font(name="Arial", size=10, italic=True, color="53657C")
    for index, header in enumerate(headers, 1):
        cell = page.cell(5, index, header)
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="243C59")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(right=Side(style="thin", color="FFFFFF"))
    for row_number, values in enumerate(rows, 6):
        for column, value in enumerate(values, 1):
            cell = page.cell(row_number, column, safe_value(value))
            cell.font = Font(name="Arial", size=10, color="172A46")
            cell.alignment = Alignment(horizontal="right" if isinstance(value, (int, float)) else "left", vertical="top", wrap_text=True)
            if isinstance(value, (int, float)):
                cell.number_format = "0.0;[Red](0.0);0"
            if isinstance(value, date):
                cell.number_format = "yyyy-mm-dd"
            if row_number % 2 == 0:
                cell.fill = PatternFill("solid", fgColor="F1F5FA")
        page.row_dimensions[row_number].height = max(32, 14 * max((len(str(value)) // max(1, widths[index] - 3) + 1) for index, value in enumerate(values)))
    page.row_dimensions[5].height = 32
    for column, width in enumerate(widths, 1):
        page.column_dimensions[get_column_letter(column)].width = width
    end = max(5, page.max_row)
    page.auto_filter.ref = f"A5:{get_column_letter(len(headers))}{end}"
    page.freeze_panes = "C6"
    page.print_options.horizontalCentered = True
    page.sheet_properties.tabColor = "243C59" if name == "Overview" else "8AA2BC"
    return page


def warning(page, column):
    if page.max_row >= 6:
        page.conditional_formatting.add(f"{column}6:{column}{page.max_row}", CellIsRule(operator="greaterThan", formula=["0"],
            fill=PatternFill("solid", fgColor="FCE4E4"), font=Font(color="9F2727", bold=True)))


def write_workbook(portfolio, metrics, path):
    book = Workbook()
    book.remove(book.active)
    overview = sheet(book, "Overview", "Department portfolio", ["Project", "Plan", "Lead", "Progress %", "Status", "Delay days", "Risk score", "Blocked tasks"],
        [[row["Project key"], row["Project name"], row["Project lead"], row["Progress percent"], row["Status"], row["Milestone delay days"], row["Risk exposure"], row["Blocked tasks"]] for row in metrics["projects"]],
        [13, 32, 12, 15, 18, 15, 15, 16], metrics["as_of"])
    if overview.max_row >= 6:
        overview.conditional_formatting.add(f"D6:D{overview.max_row}", DataBarRule(start_type="num", start_value=0, end_type="num", end_value=100, color="338F91", showValue=True))
    warning(overview, "F")
    for project in metrics["projects"]:
        tasks = [row for row in portfolio["issues"] if row["Project key"] == project["Project key"]]
        page = sheet(book, project["Project key"], project["Project name"],
            ["Issue", "Summary", "Owner", "Status", "Start", "Due", "Original h", "Remaining h", "Dependencies", "CPM slack days"],
            [[row["Issue key"], row["Summary"], row["Assignee"], row["Status"], iso_date(row["Start date"]), iso_date(row["Due date"]),
              number(row["Original estimate (h)"]), number(row["Remaining estimate (h)"]), row["Dependencies"], metrics["critical_path"]["slack_days"][row["Issue key"]]] for row in tasks],
            [14, 35, 12, 16, 15, 15, 13, 15, 20, 16], metrics["as_of"])
        if page.max_row >= 6:
            page.conditional_formatting.add(f"J6:J{page.max_row}", CellIsRule(operator="equal", formula=["0"],
                fill=PatternFill("solid", fgColor="DAE7F3")))
    risk_page = sheet(book, "Risks", "Open risks", ["Risk", "Project", "Risk description", "Owner", "Due", "Probability", "Impact", "Exposure", "Overdue"],
        [[row["Risk key"], row["Project key"], row["Summary"], row["Owner"], iso_date(row["Due date"]), number(row["Probability"]), number(row["Impact"]), row["Exposure"], "Yes" if row["Overdue"] else "No"] for row in metrics["risks"]],
        [13, 12, 55, 12, 15, 15, 12, 14, 13], metrics["as_of"])
    if risk_page.max_row >= 6:
        risk_page.conditional_formatting.add(f"H6:H{risk_page.max_row}", ColorScaleRule(start_type="num", start_value=0, start_color="F3F6FA", end_type="num", end_value=5, end_color="EEA5A5"))
    load_page = sheet(book, "Workload", "Planned weekly workload", ["Person", "Name", "Week", "Planned h", "Capacity h", "Excess h", "Utilization", "Projects", "Priorities"],
        [[iso_date(row[field]) if field == "Week" else row[field] for field in ["Assignee", "Display name", "Week", "Planned hours", "Capacity hours", "Overload hours", "Utilization", "Projects", "Priorities"]] for row in metrics["workload"]],
        [12, 23, 15, 15, 15, 15, 15, 37, 28], metrics["as_of"])
    for cell in load_page["G"][5:]:
        cell.number_format = "0%"
    warning(load_page, "F")
    sheet(book, "Actions", "Open actions", ["Action", "Project", "Agreed action", "Owner", "Due", "Source"],
        [[row["Action key"], row["Project key"], row["Summary"], row["Owner"], iso_date(row["Due date"]), row["Source"]] for row in metrics["actions"]],
        [25, 12, 55, 12, 15, 30], metrics["as_of"])
    book.save(path)
