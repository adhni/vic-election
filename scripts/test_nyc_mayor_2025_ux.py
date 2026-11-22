#!/usr/bin/env python3
"""Exercise NYC mayor geography, precinct details, neutral results and mobile UI."""
from functools import partial
import csv
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from threading import Thread
from urllib.parse import quote

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def visit(page, base, district="", geo="", year=2025):
    page.goto(f"{base}/app/?year=nyc-mayor-{year}&district={quote(district)}&geo={geo}", wait_until="networkidle")
    expect(page.locator("#explorerGrid")).to_have_attribute("aria-busy", "false")
    expect(page.locator("#electionYear")).to_have_value(f"nyc-mayor-{year}")


def check_margin_shading(page, year, leader):
    rows = csv.DictReader((ROOT / f"data/nyc_{year}_mayor_ed_fpp.csv").open(encoding="utf-8"))
    leads = [r for r in rows if r["candidate"] == leader and r["elected_member"] == leader]
    leads.sort(key=lambda r: int(r["majority"]) / int(r["formal_votes"]))
    close, strong = leads[0], leads[-1]
    assert int(close["majority"]) / int(close["formal_votes"]) < .02
    assert int(strong["majority"]) / int(strong["formal_votes"]) > .20
    colors = []
    for area in (close, strong):
        element = page.locator(f'.district-shape[data-district={json.dumps(area["district"], ensure_ascii=False)}]')
        colors.append(element.evaluate("el => getComputedStyle(el).fill"))
    rgb = [list(map(float, re.findall(r"[\d.]+", color)))[:3] for color in colors]
    assert all(light > dark for light, dark in zip(*rgb)), (year, colors)
    expect(page.locator("#mapLegend")).to_contain_text("Darker means a larger lead")
    expect(page.locator("#mapLegend .margin-swatches").first.locator("i")).to_have_count(5)
    expect(page.locator("#mapModeSelect")).to_have_value("party")
    print(f"PASS {year}: close leads visibly lighter than strong leads for the same candidate", flush=True)


def check_history(page, base):
    for year, count, winner in [(2021, 5697, "Eric Adams"), (2017, 5720, "Bill de Blasio")]:
        visit(page, base, year=year)
        expect(page.locator(".district-shape")).to_have_count(count)
        check_margin_shading(page, year, winner)
        expect(page.locator("#electionHeading")).to_have_text(f"New York City Mayor {year}")
        expect(page.locator("#stateSummary")).to_contain_text(winner)
        expect(page.locator("#roundsTabButton")).to_be_hidden()
        assert "national" not in page.locator("#stateSummary").inner_text().lower()
        if year == 2017:
            expect(page.locator("#electionSnapshotNotice")).to_contain_text("does not record the original boundary release")
        rows = csv.DictReader((ROOT / f"data/nyc_{year}_mayor_ed_fpp.csv").open(encoding="utf-8"))
        tied_name = next(row["district"] for row in rows if row["contest_status"] == "tied-local")
        page.locator("#districtSearch").fill(tied_name)
        page.get_by_role("listbox", name="Matching areas").get_by_role("option").click()
        expect(page.locator("#districtSummary")).to_contain_text("Tied:")
        page.reload(wait_until="networkidle")
        expect(page.locator("#districtSummary h2")).to_have_text(tied_name)
        page.locator('[data-geography="assembly"]').click()
        expect(page.locator(".district-shape")).to_have_count(65)
        page.locator('[data-geography="borough"]').click()
        expect(page.locator(".district-shape")).to_have_count(5)
        manhattan = page.locator('.district-shape[data-district="Manhattan"]')
        manhattan.focus()
        manhattan.press("Enter")
        expect(page.locator("#districtSummary h2")).to_have_text("Manhattan")
        expect(page.locator("#districtSummary")).to_contain_text("New York City")
        print(f"PASS {year}: historical maps, candidate totals, precinct search, ties, shared links and geography switching", flush=True)
    visit(page, base, "Brooklyn · AD 46 ED 037", year=2017)
    expect(page.locator("#districtSummary")).to_contain_text("1 ballot(s), with no recorded mayoral vote")
    visit(page, base, "Brooklyn · AD 57 ED 057", year=2017)
    expect(page.locator("#districtSummary")).to_contain_text("Source counts inconsistent")
    expect(page.locator("#districtSummary")).to_contain_text("254 recorded mayoral votes against 253 ballots")
    print("PASS 2017: one-ballot zero-vote precinct and documented BOE accounting anomaly", flush=True)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
    Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    errors = []
    screenshots = ROOT / "tmp/nyc/preview"
    screenshots.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda error: errors.append(str(error)))
            visit(page, base)
            expect(page.locator(".district-shape")).to_have_count(4102)
            check_margin_shading(page, 2025, "Zohran Mamdani")
            expect(page.locator("#electionCountry")).to_have_value("United States")
            expect(page.locator("#electionHeading")).to_have_text("New York City Mayor 2025")
            expect(page.locator("#roundsTabButton")).to_be_hidden()
            expect(page.locator("#houseViewControls")).to_be_hidden()
            expect(page.locator("#electionSnapshotNotice")).to_contain_text("Certified general election")
            assert "national" not in page.locator("#stateSummary").inner_text().lower()
            expect(page.locator("#mapLegend")).to_contain_text("Tied local leaders")
            expect(page.locator("#mapLegend")).to_contain_text("No mayoral votes")
            page.screenshot(path=str(screenshots / "precincts-desktop.png"), full_page=True)
            print("PASS precinct map, candidate legend and certified summary", flush=True)

            # Search by AD/ED and choose a real precinct.
            page.locator("#districtSearch").fill("AD 65 ED 046")
            page.get_by_role("listbox", name="Matching areas").get_by_role("option").click()
            expect(page.locator("#districtSummary h2")).to_have_text("Manhattan · AD 65 ED 046")
            expect(page.locator("#districtSummary")).to_contain_text("Tied: Zohran Mamdani / Andrew Cuomo")
            expect(page.locator("#districtSummary")).to_contain_text("0 · tied local vote")
            tied = page.locator('.district-shape[data-district="Manhattan · AD 65 ED 046"]')
            expect(tied).to_have_attribute("fill", "rgba(139, 144, 152, 0.45)")
            expect(tied).to_have_attribute("aria-label", "Manhattan · AD 65 ED 046 · Tied local leaders · Zohran Mamdani / Andrew Cuomo")
            page.reload(wait_until="networkidle")
            expect(page.locator("#districtSummary h2")).to_have_text("Manhattan · AD 65 ED 046")

            visit(page, base, "Manhattan · AD 76 ED 059")
            expect(page.locator("#districtSummary")).to_contain_text("Joint BOE reporting area")
            expect(page.locator("#districtSummary")).to_contain_text("AD 37 ED 071")
            expect(page.locator("#districtSummary")).to_contain_text("Ballots cast")
            expect(page.locator("#districtSummary")).to_contain_text("Unrecorded mayoral votes")
            expect(page.locator("#districtSummary")).to_contain_text("Not available")

            visit(page, base, "Manhattan · AD 73 ED 072")
            expect(page.locator("#districtSummary")).to_contain_text("No mayoral votes")
            assert "Tied:" not in page.locator("#districtSummary").inner_text()
            zero = page.locator('.district-shape[data-district="Manhattan · AD 73 ED 072"]')
            expect(zero).to_have_attribute("aria-label", "Manhattan · AD 73 ED 072 · No mayoral votes")
            print("PASS precinct search, shared link, tie, joint-reporting and zero-vote details", flush=True)

            # Geography changes replace both totals and polygons.
            page.locator('[data-geography="assembly"]').click()
            expect(page.locator(".district-shape")).to_have_count(65)
            expect(page).to_have_url(re.compile("geo=assembly"))
            page.locator('[data-geography="borough"]').click()
            expect(page.locator(".district-shape")).to_have_count(5)
            manhattan = page.locator('.district-shape[data-district="Manhattan"]')
            manhattan.click(force=True)
            expect(page.locator("#districtSummary h2")).to_have_text("Manhattan")
            expect(page.locator("#districtSummary")).to_contain_text("New York City")
            expect(page.locator("#districtSummary")).to_contain_text("558,058")
            expect(page.locator("#districtSummary")).to_contain_text("562,878")
            page.locator("#filterTools > summary").click()
            page.locator("#partyFilter").select_option("Andrew Cuomo")
            expect(page.locator("#districtSelect option")).to_have_count(1)
            expect(page.locator("#districtSummary h2")).to_have_text("Staten Island")
            page.get_by_role("button", name="Clear all filters").click()
            page.screenshot(path=str(screenshots / "boroughs-desktop.png"), full_page=True)
            print("PASS geography changes, map selection, borough totals and candidate filter", flush=True)

            # An existing election still loads after leaving NYC.
            page.locator("#electionYear").select_option("us-president-2024")
            expect(page.locator(".district-shape")).to_have_count(51)
            expect(page.locator("#electionHeading")).to_have_text("United States Presidential 2024")
            check_history(page, base)
            page.close()
            for width in (320, 390):
                mobile = browser.new_page(viewport={"width": width, "height": 900}, is_mobile=True, has_touch=True)
                mobile.on("pageerror", lambda error: errors.append(str(error)))
                visit(mobile, base, "Manhattan · AD 65 ED 046")
                expect(mobile.locator(".district-shape")).to_have_count(4102)
                assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                mobile.locator('[data-geography="borough"]').tap()
                expect(mobile.locator(".district-shape")).to_have_count(5)
                assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                mobile.screenshot(path=str(screenshots / f"boroughs-mobile-{width}.png"), full_page=True)
                if width == 320:
                    for year, count in [(2021, 5697), (2017, 5720)]:
                        visit(mobile, base, year=year)
                        expect(mobile.locator(".district-shape")).to_have_count(count)
                        assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                        mobile.screenshot(path=str(screenshots / f"precincts-{year}-mobile.png"), full_page=True)
                mobile.close()
            browser.close()
        assert not errors, errors
        print("PASS NYC mayor 2025/2021/2017: precinct/Assembly/borough maps, search, shared links, joint reporting, source discrepancies, ties, zero votes, filters, mobile and election switching")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
