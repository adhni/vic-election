#!/usr/bin/env python3
"""Verify demographic scatter coordinates, choices, links and small screens."""
import json
import math
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright
from test_state_clusters_ux import QuietHandler, expected_color
from test_political_bands_ux import expected_model

ROOT = Path(__file__).resolve().parents[1]


def nice_max(value):
    if value <= 0:
        return 1
    power = 10 ** math.floor(math.log10(value))
    return next(step for step in [1, 2, 5, 10] if value / power <= step) * power


def check_chart(page, data, demographics, metric, outcome="2024", party="democratic", method="bands", k=7, region="all", query=""):
    index = demographics["metric_keys"].index(metric)
    values = {name: demographics["values_by_code"][record["constituency_code"]][index] for name, record in data["counties"].items()}
    valid = {name for name, record in data["counties"].items() if (region == "all" or record["state"] == region) and query.lower() in name.lower()}
    expected = {name for name in valid if values[name] is not None}
    marks = page.locator("#demographicChart .county-dot").evaluate_all("els => els.map(el => ({name:el.dataset.county,x:Number(el.getAttribute('cx')),y:Number(el.getAttribute('cy')),color:el.getAttribute('fill')}))")
    assert len(marks) == len(expected) and {mark["name"] for mark in marks} == expected
    expect(page.locator("#dotCounty option")).to_have_count(len(valid))
    geometry = page.locator("#demographicChart").evaluate("el => ({w:el.viewBox.baseVal.width,h:el.viewBox.baseVal.height})")
    maximum = 100 if demographics["metrics"][metric]["unit"] == "percent" else nice_max(max(value for value in values.values() if value is not None))

    def voting(name):
        history = data["counties"][name]["democratic_share"]
        if outcome.startswith("change-"):
            _, start, end = outcome.split("-")
            value = history[data["years"].index(int(end))] - history[data["years"].index(int(start))]
            return -value if party == "republican" else value
        value = sum(history) / len(history) if outcome == "average" else history[data["years"].index(int(outcome))]
        return 100 - value if party == "republican" else value

    swing = outcome.startswith("change-")
    extent = max(5, math.ceil(max(abs(voting(name)) for name in data["counties"]) / 5) * 5) if swing else 100
    if method == "bands":
        assignments, groups = expected_model(data, k)
    else:
        groups = data["models"][str(k)]["groups"]
        assignments = {name: item["group"] for name, item in data["models"][str(k)]["assignments"].items()}
    colors = page.locator("#dotColors").input_value()
    for mark in marks:
        name = mark["name"]
        x = 60 + values[name] / maximum * (geometry["w"] - 28 - 60)
        y = geometry["h"] - 90 - (voting(name) + (extent if swing else 0)) / (2 * extent if swing else 100) * (geometry["h"] - 90 - 42)
        assert abs(mark["x"] - x) <= .0051 and abs(mark["y"] - y) <= .0051
        assert mark["color"] == expected_color(groups[assignments[name] - 1], colors)
    return valid, expected


def main():
    data = json.loads((ROOT / "data/us_county_presidential_clusters.json").read_text())
    demographics = json.loads((ROOT / "data/us_county_cluster_demographics.json").read_text())
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
    Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    screenshots = ROOT / "tmp/county-demographic-scatter"
    screenshots.mkdir(parents=True, exist_ok=True)
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1550, "height": 1100})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"{base}/app/county-dots.html?view=demographics&method=bands&k=7#demographicControls", wait_until="networkidle")
            expect(page.locator("#demographicControls")).to_be_visible()
            expect(page.locator("#demographicMetric option")).to_have_count(42)
            expect(page.locator("#demographicOutcome option")).to_have_count(11)
            expect(page.locator("#demographicMetric")).to_have_value("bachelors_plus_pct")
            for metric in demographics["metric_keys"]:
                page.locator("#demographicMetric").select_option(metric)
                check_chart(page, data, demographics, metric)
            page.locator("#demographicMetric").select_option("bachelors_plus_pct")
            for outcome in ["2008", "2012", "2016", "2020", "2024", "average", "change-2008-2012", "change-2012-2016", "change-2016-2020", "change-2020-2024", "change-2008-2024"]:
                page.locator("#demographicOutcome").select_option(outcome)
                for party in ["democratic", "republican"]:
                    page.locator("#demographicParty").select_option(party)
                    check_chart(page, data, demographics, "bachelors_plus_pct", outcome, party)
            page.locator("#demographicOutcome").select_option("2024")
            page.locator("#demographicParty").select_option("democratic")
            page.locator(".dots-panel").screenshot(path=str(screenshots / "college-voting.png"))
            page.locator("#dotState").select_option("Michigan")
            check_chart(page, data, demographics, "bachelors_plus_pct", region="Michigan")
            name = "Washtenaw County, Michigan"
            page.locator(f'.county-map-shape[data-county="{name}"]').click()
            expect(page.locator(".county-dot.is-selected")).to_have_attribute("data-county", name)
            page.locator(".county-dot.is-selected").hover()
            expect(page.locator("#dotTooltip")).to_contain_text("College graduates")
            expect(page.locator("#storyDemographic")).to_contain_text("College graduates")
            mark = page.locator(".county-dot.is-selected")
            mark.focus()
            mark.press("ArrowLeft")
            assert page.locator("#storyName").inner_text() != name
            page.reload(wait_until="networkidle")
            expect(page.locator("#viewDemographics")).to_have_attribute("aria-pressed", "true")
            expect(page.locator("#dotState")).to_have_value("Michigan")
            page.locator("#dotMethod").select_option("similarity")
            page.locator("#dotColors").select_option("groups")
            check_chart(page, data, demographics, "bachelors_plus_pct", method="similarity", region="Michigan")
            page.locator("#dotReset").click()
            page.locator("#viewDemographics").click()
            page.locator("#demographicMetric").select_option("median_household_income")
            index = demographics["metric_keys"].index("median_household_income")
            missing = next(name for name, record in data["counties"].items() if demographics["values_by_code"][record["constituency_code"]][index] is None)
            page.locator("#dotSearch").fill(missing)
            expect(page.locator("#dotCounty option")).to_have_count(1)
            expect(page.locator("#demographicChart .county-dot")).to_have_count(0)
            expect(page.locator("#dotEmpty")).to_contain_text("No estimates")
            expect(page.locator("#storyDemographic")).to_contain_text("Not available")
            expect(page.locator(".county-map-shape.is-selected")).to_have_attribute("data-county", missing)
            page.locator("#demographicMetric").select_option("bachelors_plus_pct")
            expect(page.locator("#demographicChart .county-dot")).to_have_count(1)
            page.go_back(wait_until="networkidle")
            expect(page.locator("#demographicMetric")).to_have_value("median_household_income")
            page.locator("#countPopulation").click()
            expect(page.locator("#viewGroups")).to_have_attribute("aria-pressed", "true")
            page.locator("#viewDemographics").click()
            expect(page.locator("#countCounties")).to_have_attribute("aria-pressed", "true")
            page.goto(f"{base}/app/county-dots.html?view=demographics&metric=bogus&outcome=bogus&party=bogus&measure=population", wait_until="networkidle")
            expect(page.locator("#demographicMetric")).to_have_value("bachelors_plus_pct")
            expect(page.locator("#demographicOutcome")).to_have_value("2024")
            expect(page.locator("#demographicParty")).to_have_value("democratic")
            expect(page.locator(".population-dot")).to_have_count(0)
            print("PASS all 42 demographic coordinates and 11 voting outcomes for both parties, exact colours, map/tooltip/sidebar/keyboard, missing data, source units, method switching, URL/history and unit toggle", flush=True)
            for width in [320, 390, 768]:
                mobile = browser.new_page(viewport={"width": width, "height": 900}, is_mobile=True, has_touch=True)
                mobile.on("pageerror", lambda error: errors.append(str(error)))
                mobile.goto(f"{base}/app/county-dots.html?view=demographics&method=bands&k=7&region=Michigan#demographicControls", wait_until="networkidle")
                check_chart(mobile, data, demographics, "bachelors_plus_pct", region="Michigan")
                assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                mobile.locator("#demographicMetric").select_option("median_household_income")
                mobile.locator("#demographicOutcome").select_option("change-2020-2024")
                check_chart(mobile, data, demographics, "median_household_income", "change-2020-2024", region="Michigan")
                assert mobile.locator("#demographicChart").evaluate("el => el.viewBox.baseVal.width <= el.clientWidth + 1")
                mobile.locator(".dots-panel").screenshot(path=str(screenshots / f"mobile-{width}.png"))
                mobile.close()
            browser.close()
        assert not errors, errors
        print("PASS demographic scatter on 320/390/768px layouts", flush=True)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
