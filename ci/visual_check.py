"""Capture the actual static dashboard and render every PDF page on the runner."""
import json
from pathlib import Path

import fitz
from openpyxl import load_workbook
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

root = Path("artifacts")
reports = root / "reports"
previews = root / "previews"
previews.mkdir(exist_ok=True)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
    errors, external = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.on("request", lambda request: external.append(request.url) if request.url.startswith(("http:", "https:")) else None)
    page.goto((reports / "dashboard.html").resolve().as_uri())
    assert page.title() == "Department portfolio | 2026-Q3"
    assert page.locator("h1").inner_text() == "Department portfolio"
    assert page.locator("#overview tbody tr").count() == 12
    assert page.locator("svg").count() == 3
    for anchor in ["overview", "timeline", "workload", "risks", "decisions"]:
        assert page.locator(f"#{anchor}").count() == 1
    page.screenshot(path=str(reports / "dashboard.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(reports / "dashboard-mobile.png"), full_page=True)
    assert errors == [], errors
    assert external == [], external
    browser.close()

page_counts = {}
for source, label in [(reports / "quarterly-review.pdf", "review"), (previews / "portfolio.pdf", "workbook")]:
    document = fitz.open(source)
    page_counts[label] = len(document)
    complete_text = "\n".join(page.get_text() for page in document)
    assert "#REF!" not in complete_text and "#VALUE!" not in complete_text
    if label == "workbook":
        book = load_workbook(reports / "portfolio.xlsx")
        for sheet in book:
            assert sheet["A2"].value in complete_text, f"Sheet missing from native PDF: {sheet.title}"
    else:
        assert "Recommendations for management" in complete_text
    thumbnails = []
    for index, page in enumerate(document):
        # Catch text outside the physical page, including content below the footer.
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    box = fitz.Rect(span["bbox"])
                    assert box.x0 >= -1 and box.y0 >= -1 and box.x1 <= page.rect.width + 1 and box.y1 <= page.rect.height + 1, (label, index, span["text"])
        image_path = previews / f"{label}-{index + 1:02}.png"
        page.get_pixmap(matrix=fitz.Matrix(1.1, 1.1)).save(image_path)
        thumbnail = Image.open(image_path).convert("RGB")
        thumbnail.thumbnail((470, 670))
        tile = Image.new("RGB", (490, 700), "#e7edf4")
        tile.paste(thumbnail, ((490 - thumbnail.width) // 2, 25))
        ImageDraw.Draw(tile).text((12, 6), f"{label} page {index + 1}", fill="black")
        thumbnails.append(tile)
    for start in range(0, len(thumbnails), 6):
        batch = thumbnails[start:start + 6]
        montage = Image.new("RGB", (490 * 3, 700 * ((len(batch) + 2) // 3)), "white")
        for position, tile in enumerate(batch):
            montage.paste(tile, ((position % 3) * 490, (position // 3) * 700))
        montage.save(previews / f"{label}-contact-{start // 6 + 1:02}.png")
    document.close()
(root / "visual-proof.json").write_text(json.dumps({"browser_errors": errors, "external_requests": external,
    "dashboard_project_rows": 12, "svg_charts": 3, "mobile_overflow": False, "pdf_pages": page_counts,
    "workbook_native_rendered": True, "all_pdf_text_within_page": True}, indent=2) + "\n")
