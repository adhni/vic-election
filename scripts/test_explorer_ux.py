#!/usr/bin/env python3
"""Browser regression checks for search, result panels, summaries and charts.

Install once: pip install playwright && playwright install chromium
Run: python scripts/test_explorer_ux.py
Optional: --base-url http://127.0.0.1:8000 --screenshots tmp/explorer-ux
Without --base-url, a temporary local server serves this checkout.
"""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from threading import Thread

from playwright.sync_api import expect, sync_playwright


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def visit(page, base_url, year="2022"):
    page.goto(f"{base_url}/app/?year={year}", wait_until="networkidle")
    expect(page.locator("#electionYear")).to_have_value(year)
    expect(page.locator("#explorerGrid")).to_have_attribute("aria-busy", "false")
    expect(page.locator("#districtSummary h2")).to_be_visible()


def check_search(page, base_url):
    visit(page, base_url)
    search = page.get_by_role("combobox", name="Search", exact=True)
    matches = page.get_by_role("listbox", name="Matching areas")
    search.fill("rich")
    expect(matches.get_by_role("option")).to_have_count(1)
    matches.get_by_role("option", name=re.compile("Richmond")).tap()
    expect(page.locator("#districtSummary h2")).to_have_text("Richmond")
    expect(page.locator("#districtSummary")).to_be_focused()
    expect(page.locator("#districtSummary")).to_be_in_viewport()
    expect(search).to_have_attribute("aria-expanded", "false")

    page.locator("#filterTools > summary").click()
    page.get_by_role("button", name="Clear all filters").click()
    expect(page.locator("#districtSummary h2")).to_have_text("Richmond")
    expect(search).to_have_value("")

    search.fill("park")
    assert matches.get_by_role("option").count() > 1
    search.press("ArrowDown")
    search.press("ArrowDown")
    selected = matches.locator('[aria-selected="true"] strong').inner_text()
    search.press("Enter")
    expect(page.locator("#districtSummary h2")).to_have_text(selected)
    expect(page.locator("#districtSummary")).to_be_focused()

    search.fill("nonexistent-area-xyz")
    expect(page.locator("#districtSearchStatus")).to_contain_text("No matches")
    expect(matches.get_by_role("option")).to_have_count(0)
    search.press("Escape")
    expect(search).to_have_attribute("aria-expanded", "false")
    expect(search).to_have_value("nonexistent-area-xyz")
    search.fill("")
    expect(page.locator("#districtSummary h2")).to_have_text("Albert Park")
    expect(search).to_have_attribute("aria-expanded", "false")
    print("PASS: touch and keyboard search, no matches, Escape, clear filters", flush=True)


def check_charts(page):
    for chart_id in ("geographyHistoryChart", "geographyProfileChart"):
        chart = page.locator(f"#{chart_id}")
        expect(chart.locator("svg")).to_be_visible()
        assert chart.evaluate("el => el.scrollWidth <= el.clientWidth + 1"), chart_id
        assert chart.locator("svg").evaluate("""svg => {
            const bounds = svg.getBoundingClientRect();
            return [...svg.querySelectorAll('text')].every(text => {
                const rect = text.getBoundingClientRect();
                return rect.left >= bounds.left - 1 && rect.right <= bounds.right + 1;
            });
        }"""), f"Clipped chart label: {chart_id}"
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")


def check_results_and_layout(browser, base_url, screenshots, errors):
    cases = (
        ("2022", True),
        ("uk-2024", False),
        ("us-president-2024", False),
        ("nz-2023", True),
        ("germany-bundestag-2025", True),
        ("tas-2025", True),
        ("mexico-president-2024", False),
        ("poland-president-2025-round-2", False),
    )
    for width in (320, 390, 768, 1440):
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.on("pageerror", lambda error: errors.append(str(error)))
        for year, has_second_chart in cases:
            visit(page, base_url, year)
            if has_second_chart:
                expect(page.locator("#finalVotePanel")).to_be_visible()
                assert page.locator("#finalBars .bar-row").count() > 0
            else:
                expect(page.locator("#finalVotePanel")).to_be_hidden()
            if page.locator("#geographyAnalysis").is_visible():
                check_charts(page)
            if year == "poland-president-2025-round-2":
                expect(page.locator("#geographyHistoryChart svg")).to_contain_text("2025 R2")
            summary = page.locator("#stateSummary").inner_text()
            if width <= 720 and year == "uk-2024":
                assert all(party in summary for party in ("Labour", "Conservative", "Liberal Democrat")), summary
                assert "England" not in summary, summary
            if width <= 720 and year == "us-president-2024":
                assert "Donald Trump" in summary and "Kamala Harris" in summary, summary
            if width <= 720 and year == "nz-2023":
                assert "National" in summary and "Labour" in summary, summary
            if screenshots and width in (390, 1440) and year in ("2022", "uk-2024"):
                page.screenshot(path=str(screenshots / f"{year}-{width}.png"), full_page=True)
            print(f"PASS: {year} at {width}px", flush=True)
        page.close()


def check_resize(page, base_url):
    visit(page, base_url)
    page.get_by_text("View history values", exact=True).click()
    expect(page.locator("#geographyHistoryChart table")).to_contain_text("2022")
    for width in (1440, 320, 768, 390):
        page.set_viewport_size({"width": width, "height": 900})
        page.wait_for_function("""() => {
            const chart = document.getElementById('geographyHistoryChart');
            return Math.abs(chart.clientWidth - chart.querySelector('svg').viewBox.baseVal.width) < 2;
        }""")
        expect(page.locator("#geographyHistoryChart .chart-data")).to_have_attribute("open", "")
        # The expanded values table can scroll, while both charts must fit.
        page.get_by_text("View history values", exact=True).click()
        check_charts(page)
        page.get_by_text("View history values", exact=True).click()
    print("PASS: responsive charts and accessible values survive resize", flush=True)


def check_long_chart_labels(browser, base_url):
    page = browser.new_page(viewport={"width": 320, "height": 900})
    visit(page, base_url, "mexico-president-2024")
    # A wider generic font reproduces the CI clipping on macOS as well as Linux.
    page.locator("#geographyProfileChart").evaluate("el => el.style.fontFamily = 'monospace'")
    page.evaluate("renderGeographyAnalysis()")
    check_charts(page)
    label = page.locator("#geographyProfileChart .chart-axis-label").first
    expect(label).to_have_text("Sheinbaum / governing coalition")
    assert label.locator("tspan").count() > 1
    assert page.locator("#geographyProfileChart svg").evaluate("""svg => {
        const labels = [...svg.querySelectorAll('.chart-axis-label')];
        const markers = [...svg.querySelectorAll('.chart-dot')];
        return labels.every((label, index) => {
            const bounds = label.getBoundingClientRect();
            return bounds.bottom < markers[index].getBoundingClientRect().top
                && (!index || bounds.top > markers[index - 1].getBoundingClientRect().bottom);
        });
    }"""), "Wrapped chart labels overlap vote markers"
    page.close()
    print("PASS: long chart labels wrap without clipping or overlapping vote markers", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url")
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    server = None
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    base_url = args.base_url
    if not base_url:
        root = Path(__file__).resolve().parents[1]
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root)))
        Thread(target=server.serve_forever, daemon=True).start()
        base_url = f"http://127.0.0.1:{server.server_port}"
    errors = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            mobile = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
            mobile.on("pageerror", lambda error: errors.append(str(error)))
            check_search(mobile, base_url)
            check_resize(mobile, base_url)
            mobile.close()
            check_long_chart_labels(browser, base_url)
            check_results_and_layout(browser, base_url, args.screenshots, errors)
            browser.close()
        assert not errors, errors
        print("All explorer UX checks passed; no browser runtime errors.")
    finally:
        if server:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
