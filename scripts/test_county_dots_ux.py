#!/usr/bin/env python3
"""Browser audit: one dot per county, both layouts, exact data and interactions."""
import json
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright

from test_state_clusters_ux import QuietHandler, expected_color

ROOT = Path(__file__).resolve().parents[1]


def check_dots(page, data, k, region="all", group="all", query=""):
    model = data["models"][str(k)]
    expected = {name for name, record in data["counties"].items()
        if (region == "all" or record["state"] == region)
        and (group == "all" or model["assignments"][name]["group"] == int(group))
        and query.lower() in name.lower()}
    actual = page.locator(".county-dot").evaluate_all("els => els.map(el => ({name:el.dataset.county,color:el.getAttribute('fill'),x:Number(el.getAttribute('cx')),y:Number(el.getAttribute('cy'))}))")
    assert len(actual) == len(expected) and {r["name"] for r in actual} == expected
    mode = page.locator("#dotColors").input_value()
    for dot in actual:
        record = model["groups"][model["assignments"][dot["name"]]["group"] - 1]
        assert dot["color"] == expected_color(record, mode)
        assert dot["x"] >= 0 and dot["y"] >= 0
    expect(page.locator("#dotCounty option")).to_have_count(len(expected))
    return actual


def main():
    data = json.loads((ROOT / "data/us_county_presidential_clusters.json").read_text())
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
    Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    screenshots = ROOT / "tmp/county-dots"
    screenshots.mkdir(parents=True, exist_ok=True)
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1550, "height": 1100})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"{base}/app/county-dots.html", wait_until="networkidle")
            expect(page.locator("#dotContent")).to_be_visible()
            expect(page.locator("#dotGroupCount")).to_have_value("5")
            expect(page.locator("#storyName")).to_have_text("Wayne County, Michigan")
            for k in [2, 3, 4, 5, 7]:
                page.locator("#dotGroupCount").select_option(str(k))
                check_dots(page, data, k)
                for group in data["models"][str(k)]["groups"]:
                    expect(page.locator(f'.dot-lane[data-group="{group["id"]}"] .county-dot')).to_have_count(group["size"])
            page.locator("#dotGroupCount").select_option("5")
            assert page.locator(".county-dot").evaluate_all("els => new Set(els.map(el => el.getAttribute('r'))).size === 1")
            assert page.locator(".dot-lane svg").evaluate_all("els => els.every(svg => [...svg.querySelectorAll('circle')].every(dot => Number(dot.getAttribute('cx')) + 4 <= svg.viewBox.baseVal.width && Number(dot.getAttribute('cy')) + 4 <= svg.viewBox.baseVal.height))")
            page.screenshot(path=str(screenshots / "desktop-groups.png"), full_page=True)
            page.locator("#viewPatterns").click()
            dots = check_dots(page, data, 5)
            # Verify exact plotted positions, rather than merely counting dots.
            geometry = page.locator("#patternChart").evaluate("el => ({w:el.viewBox.baseVal.width,h:el.viewBox.baseVal.height})")
            import math
            extent = math.ceil(max(10, *(abs(c["democratic_share"][-1] - c["democratic_share"][0]) for c in data["counties"].values())) / 10) * 10
            for dot in dots:
                values = data["counties"][dot["name"]]["democratic_share"]
                x = 58 + sum(values) / 5 / 100 * (geometry["w"] - 24 - 58)
                y = geometry["h"] - 70 - (values[-1] - values[0] + extent) / (extent * 2) * (geometry["h"] - 70 - 38)
                assert abs(dot["x"] - x) <= .0051 and abs(dot["y"] - y) <= .0051
            page.screenshot(path=str(screenshots / "desktop-patterns.png"), full_page=True)
            page.locator("#dotColors").select_option("groups")
            check_dots(page, data, 5)
            page.locator("#dotState").select_option("Michigan")
            check_dots(page, data, 5, "Michigan")
            page.locator("#dotSearch").fill("Washtenaw")
            expect(page.locator(".county-dot")).to_have_count(1)
            check_dots(page, data, 5, "Michigan", query="Washtenaw")
            dot = page.locator(".county-dot")
            dot.hover()
            expect(page.locator("#dotTooltip")).to_contain_text("Washtenaw County, Michigan")
            dot.click()
            expect(page.locator("#storyName")).to_have_text("Washtenaw County, Michigan")
            for i, row in enumerate(page.locator("#storyHistory tr").all()):
                share = data["counties"]["Washtenaw County, Michigan"]["democratic_share"][i]
                expect(row.locator("td").first).to_have_text(f"{share:.1f}%")
                expect(row.locator("td").last).to_have_text(f"{100-share:.1f}%")
            page.reload(wait_until="networkidle")
            expect(page.locator("#dotState")).to_have_value("Michigan")
            expect(page.locator("#dotColors")).to_have_value("groups")
            expect(page.locator("#viewPatterns")).to_have_attribute("aria-pressed", "true")
            expect(page.locator(".county-dot")).to_have_count(1)
            assert "county=Washtenaw" in page.locator("#storyMapLink").get_attribute("href")
            page.locator("#dotSearch").fill("no such county")
            expect(page.locator("#dotEmpty")).to_be_visible()
            expect(page.locator(".county-dot")).to_have_count(0)
            expect(page.locator("#storyContent")).to_be_hidden()
            page.locator("#dotReset").click()
            check_dots(page, data, 5)
            selected = page.locator('.county-dot[tabindex="0"]')
            selected.focus()
            selected.press("ArrowLeft")
            assert page.locator("#storyName").inner_text() != "Wayne County, Michigan"
            page.locator("#dotCounty").select_option("Los Angeles County, California")
            expect(page.locator("#storyName")).to_have_text("Los Angeles County, California")
            page.locator('#dotLegend [data-filter="1"]').click()
            check_dots(page, data, 5, group="1")
            page.go_back(wait_until="networkidle")
            expect(page.locator("#dotGroup")).to_have_value("all")
            expect(page.locator("#storyName")).to_have_text("Los Angeles County, California")
            page.goto(f"{base}/app/county-dots.html?k=6&county=Atlantis&group=99&region=Alaska", wait_until="networkidle")
            expect(page.locator("#dotGroupCount")).to_have_value("5")
            expect(page.locator("#dotState")).to_have_value("all")
            check_dots(page, data, 5)
            print("PASS every county exactly once in all five models, exact colours and scatter positions, search, filters, votes, tooltip, click, keyboard, reload/history and empty/invalid inputs", flush=True)
            for width in [320, 390, 768]:
                mobile = browser.new_page(viewport={"width": width, "height": 900}, is_mobile=True, has_touch=True)
                mobile.on("pageerror", lambda error: errors.append(str(error)))
                mobile.goto(f"{base}/app/county-dots.html", wait_until="networkidle")
                expect(mobile.locator("#dotContent")).to_be_visible()
                check_dots(mobile, data, 5)
                assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                mobile.locator("#dotState").select_option("Michigan")
                check_dots(mobile, data, 5, "Michigan")
                mobile.screenshot(path=str(screenshots / f"mobile-{width}.png"), full_page=True)
                mobile.locator("#viewPatterns").click()
                check_dots(mobile, data, 5, "Michigan")
                assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                assert mobile.locator("#patternChart").evaluate("el => el.viewBox.baseVal.width <= el.clientWidth + 1")
                mobile.close()
            page.goto(f"{base}/app/county-clusters.html", wait_until="networkidle")
            expect(page.locator('a[href^="county-dots.html"]')).to_be_visible()
            browser.close()
        assert not errors, errors
        print("PASS desktop and 320/390/768px layouts, all county dots on mobile and map entry link", flush=True)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
