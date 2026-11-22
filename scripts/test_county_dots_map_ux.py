#!/usr/bin/env python3
"""Verify linked county polygons and dots share assignments and selection."""
import json
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright
from test_state_clusters_ux import QuietHandler, expected_color
from test_political_bands_ux import expected_model

ROOT = Path(__file__).resolve().parents[1]


def check_map(page, data, k, method="similarity", region="all", group="all", query=""):
    if method == "bands":
        assignments, groups = expected_model(data, k)
    else:
        model = data["models"][str(k)]
        assignments = {name: assignment["group"] for name, assignment in model["assignments"].items()}
        groups = model["groups"]
    areas = {name for name, record in data["counties"].items() if region == "all" or record["state"] == region}
    matching = {name for name in areas if (group == "all" or assignments[name] == int(group)) and query.lower() in name.lower()}
    actual = page.locator(".county-map-shape").evaluate_all("els => Object.fromEntries(els.map(el => [el.dataset.county,{color:el.getAttribute('fill'),disabled:el.getAttribute('aria-disabled')}]))")
    assert set(actual) == areas
    colors = page.locator("#dotColors").input_value()
    for name in areas:
        if name in matching:
            assert actual[name]["color"] == expected_color(groups[assignments[name] - 1], colors)
            assert actual[name]["disabled"] == "false"
        else:
            assert actual[name]["color"] == "#e8e8e5" and actual[name]["disabled"] == "true"
    dots = page.locator(".county-dot").evaluate_all("els => Object.fromEntries(els.map(el => [el.dataset.county,el.getAttribute('fill')]))")
    assert set(dots) == matching
    assert all(dots[name] == actual[name]["color"] for name in matching)
    assert page.locator(".county-map-shape").evaluate_all("els => els.every(el => {const box=el.getBBox();return !/NaN|Infinity/.test(el.getAttribute('d')) && box.x >= -1 && box.y >= -1 && box.x+box.width <= 961 && box.y+box.height <= 591})")


def main():
    data = json.loads((ROOT / "data/us_county_presidential_clusters.json").read_text())
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
    Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    screenshots = ROOT / "tmp/county-dots-map"
    screenshots.mkdir(parents=True, exist_ok=True)
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1550, "height": 1100})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"{base}/app/county-dots.html", wait_until="networkidle")
            expect(page.locator("#dotCountyMap")).to_be_visible()
            for method in ["similarity", "bands"]:
                page.locator("#dotMethod").select_option(method)
                for k in [2, 3, 4, 5, 7]:
                    page.locator("#dotGroupCount").select_option(str(k))
                    for colors in ["groups", "party"]:
                        page.locator("#dotColors").select_option(colors)
                        check_map(page, data, k, method)
            page.locator(".county-map-panel").screenshot(path=str(screenshots / "national-map.png"))
            page.locator("#dotGroupCount").select_option("5")
            page.locator("#dotState").select_option("Michigan")
            check_map(page, data, 5, "bands", "Michigan")
            name = "Washtenaw County, Michigan"
            polygon = page.locator(f'.county-map-shape[data-county="{name}"]')
            polygon.hover()
            expect(page.locator("#dotTooltip")).to_contain_text(name)
            polygon.click()
            expect(page.locator("#storyName")).to_have_text(name)
            expect(page.locator(".county-dot.is-selected")).to_have_attribute("data-county", name)
            expect(page.locator(".county-map-shape.is-selected")).to_have_attribute("data-county", name)
            expect(page.locator("#dotCounty")).to_have_value(name)
            name = "Wayne County, Michigan"
            page.locator(f'.county-dot[data-county="{name}"]').click()
            expect(page.locator(".county-map-shape.is-selected")).to_have_attribute("data-county", name)
            polygon = page.locator(f'.county-map-shape[data-county="{name}"]')
            polygon.focus()
            polygon.press("ArrowLeft")
            selected = page.locator("#dotCounty").input_value()
            assert selected != name
            expect(page.locator(".county-map-shape:focus")).to_have_attribute("data-county", selected)
            expect(page.locator(".county-dot.is-selected")).to_have_attribute("data-county", selected)
            page.locator("#dotSearch").fill("Washtenaw")
            expect(page.locator(".county-dot")).to_have_count(1)
            check_map(page, data, 5, "bands", "Michigan", query="Washtenaw")
            page.locator("#dotSearch").fill("no county like this")
            expect(page.locator("#dotEmpty")).to_be_visible()
            expect(page.locator(".county-map-shape:not(.is-filtered)")).to_have_count(0)
            expect(page.locator(".county-map-shape.is-selected")).to_have_count(0)
            page.locator("#dotReset").click()
            page.locator("#dotState").select_option("Hawaii")
            check_map(page, data, 5, region="Hawaii")
            page.locator("#viewPatterns").click()
            check_map(page, data, 5, region="Hawaii")
            page.reload(wait_until="networkidle")
            check_map(page, data, 5, region="Hawaii")
            page.locator("#dotReset").click()
            page.locator("#dotMethod").select_option("bands")
            page.locator('#countyMapLegend [data-filter="3"]').click()
            check_map(page, data, 5, "bands", group="3")
            expect(page.locator('#dotLegend [data-filter="3"]')).to_have_attribute("aria-pressed", "true")
            page.go_back(wait_until="networkidle")
            check_map(page, data, 5, "bands")
            print("PASS every map polygon and dot agrees for both methods, 2–5 and 7 groups and both palettes; map/dot clicks, keyboard, tooltip, search/empty filters, Hawaii, scatter, reload/history and map legend", flush=True)
            for width in [320, 390, 768]:
                mobile = browser.new_page(viewport={"width": width, "height": 900}, is_mobile=True, has_touch=True)
                mobile.on("pageerror", lambda error: errors.append(str(error)))
                mobile.goto(f"{base}/app/county-dots.html?method=bands&region=Michigan", wait_until="networkidle")
                check_map(mobile, data, 5, "bands", "Michigan")
                assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                mobile.locator('.county-map-shape[data-county="Washtenaw County, Michigan"]').tap()
                expect(mobile.locator("#storyName")).to_have_text("Washtenaw County, Michigan")
                mobile.locator(".county-map-panel").screenshot(path=str(screenshots / f"mobile-map-{width}.png"))
                mobile.close()
            browser.close()
        assert not errors, errors
        print("PASS linked county map on 320/390/768px layouts and touch selection", flush=True)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
