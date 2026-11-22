#!/usr/bin/env python3
"""Population unit toggle: exact dot budget, proportional groups and linked map."""
import json
from collections import Counter
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright
from test_state_clusters_ux import QuietHandler, expected_color
from test_political_bands_ux import expected_model

ROOT = Path(__file__).resolve().parents[1]


def apportion(weights, budget):
    total = sum(weights.values())
    if not total or not budget:
        return {key: 0 for key in weights}
    result = {key: value * budget // total for key, value in weights.items()}
    ranked = sorted(weights, key=lambda key: (-(weights[key] * budget % total), str(key)))
    for key in ranked[:budget - sum(result.values())]:
        result[key] += 1
    return result


def expected(data, population, method, k):
    residents = {name: population["population_by_code"][county["constituency_code"]] for name, county in data["counties"].items()}
    if method == "bands":
        assignments, groups = expected_model(data, k)
    else:
        groups = [{**group, "members": group["counties"]} for group in data["models"][str(k)]["groups"]]
        assignments = {name: item["group"] for name, item in data["models"][str(k)]["assignments"].items()}
    totals = {i+1: sum(residents[name] for name in group["members"]) for i, group in enumerate(groups)}
    group_dots = apportion(totals, 3103)
    counts = {}
    for i, group in enumerate(groups):
        counts.update(apportion({name: residents[name] for name in group["members"]}, group_dots[i+1]))
    return residents, assignments, groups, counts, totals


def check_population(page, data, population, method, k, region="all", group="all", query=""):
    residents, assignments, groups, counts, totals = expected(data, population, method, k)
    names = {name for name, record in data["counties"].items() if (region == "all" or record["state"] == region) and (group == "all" or assignments[name] == int(group)) and query.lower() in name.lower()}
    actual = page.locator(".population-dot").evaluate_all("els => els.map(el => ({name:el.dataset.county,color:el.getAttribute('fill'),r:el.getAttribute('r')}))")
    assert Counter(row["name"] for row in actual) == Counter({name: counts[name] for name in names if counts[name]})
    assert len(actual) == sum(counts[name] for name in names)
    expect(page.locator(".county-dot")).to_have_count(0)
    assert {row["r"] for row in actual} <= {"3"}
    colors = page.locator("#dotColors").input_value()
    for row in actual:
        assert row["color"] == expected_color(groups[assignments[row["name"]]-1], colors)
    for i, item in enumerate(groups):
        shown = [name for name in names if assignments[name] == i+1]
        lane = page.locator(f'.dot-lane[data-group="{i+1}"]')
        if group != "all" and str(i+1) != group:
            continue
        expect(lane.locator(".population-dot")).to_have_count(sum(counts[name] for name in shown))
        expect(lane.locator(".lane-count")).to_contain_text(f"{sum(residents[name] for name in shown):,}")
    expect(page.locator("#dotCounty option")).to_have_count(len(names))
    expect(page.locator("#populationDotNote")).to_contain_text("106,310 residents")
    expect(page.locator("#viewPatterns")).to_be_disabled()
    return names, counts


def main():
    data = json.loads((ROOT / "data/us_county_presidential_clusters.json").read_text())
    population = json.loads((ROOT / "data/us_county_cluster_population.json").read_text())
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
    Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    screenshots = ROOT / "tmp/population-dots"
    screenshots.mkdir(parents=True, exist_ok=True)
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1550, "height": 1100})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"{base}/app/county-dots.html", wait_until="networkidle")
            expect(page.locator(".county-dot")).to_have_count(3103)
            page.locator("#viewPatterns").click()
            page.locator("#countPopulation").click()
            expect(page.locator("#viewGroups")).to_have_attribute("aria-pressed", "true")
            for method in ["similarity", "bands"]:
                page.locator("#dotMethod").select_option(method)
                for k in [2, 3, 4, 5, 7]:
                    page.locator("#dotGroupCount").select_option(str(k))
                    for colors in ["groups", "party"]:
                        page.locator("#dotColors").select_option(colors)
                        check_population(page, data, population, method, k)
                    expect(page.locator(".county-map-shape")).to_have_count(3103)
            page.locator(".dots-panel").screenshot(path=str(screenshots / "population-groups.png"))
            page.locator("#dotGroupCount").select_option("5")
            page.locator("#dotCounty").select_option("Los Angeles County, California")
            count = page.locator('.population-dot[data-county="Los Angeles County, California"]').count()
            assert count > 1
            expect(page.locator(".population-dot.is-selected")).to_have_count(count)
            expect(page.locator(".county-map-shape.is-selected")).to_have_attribute("data-county", "Los Angeles County, California")
            mark = page.locator('.population-dot[data-county="Los Angeles County, California"]').first
            mark.hover()
            expect(page.locator("#dotTooltip")).to_contain_text("Population dot")
            mark.focus()
            mark.press("ArrowRight")
            assert page.locator("#storyName").inner_text() != "Los Angeles County, California"
            assert page.locator(".population-dot:focus").count() == 1
            page.locator("#dotSearch").fill("Loving County, Texas")
            expect(page.locator("#dotCounty option")).to_have_count(1)
            check_population(page, data, population, "bands", 5, query="Loving County, Texas")
            expect(page.locator("#dotEmpty")).to_contain_text("too small for a whole population dot")
            expect(page.locator(".county-map-shape.is-selected")).to_have_attribute("data-county", "Loving County, Texas")
            expect(page.locator("#storyPopulation")).to_contain_text("Too small")
            page.locator("#dotSearch").fill("")
            expect(page.locator("#dotCounty option")).to_have_count(3103)
            page.locator("#dotState").select_option("Michigan")
            check_population(page, data, population, "bands", 5, region="Michigan")
            page.reload(wait_until="networkidle")
            expect(page.locator("#countPopulation")).to_have_attribute("aria-pressed", "true")
            check_population(page, data, population, "bands", 5, region="Michigan")
            page.locator('#dotLegend [data-filter="3"]').click()
            check_population(page, data, population, "bands", 5, region="Michigan", group="3")
            page.locator("#countCounties").click()
            expect(page.locator("#viewPatterns")).to_be_enabled()
            expect(page.locator(".population-dot")).to_have_count(0)
            page.go_back(wait_until="networkidle")
            expect(page.locator("#countPopulation")).to_have_attribute("aria-pressed", "true")
            page.locator("#dotReset").click()
            expect(page.locator(".county-dot")).to_have_count(3103)
            expect(page.locator("#countCounties")).to_have_attribute("aria-pressed", "true")
            print("PASS exact 3,103 population dots across both methods, 2–5 and 7 groups and both palettes; resident totals, equal dot sizes, filter scale, selection/map/keyboard, small counties, reload/back/reset and county toggle", flush=True)
            for width in [320, 390, 768]:
                mobile = browser.new_page(viewport={"width": width, "height": 900}, is_mobile=True, has_touch=True)
                mobile.on("pageerror", lambda error: errors.append(str(error)))
                mobile.goto(f"{base}/app/county-dots.html?method=bands&measure=population", wait_until="networkidle")
                expect(mobile.locator("#dotContent")).to_be_visible()
                check_population(mobile, data, population, "bands", 5)
                assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                mobile.locator("#dotState").select_option("Michigan")
                check_population(mobile, data, population, "bands", 5, region="Michigan")
                mobile.locator(".dots-panel").screenshot(path=str(screenshots / f"population-{width}.png"))
                mobile.locator("#countCounties").tap()
                expect(mobile.locator(".county-dot")).to_have_count(83)
                mobile.close()
            browser.close()
        assert not errors, errors
        print("PASS population dots and touch toggle on 320/390/768px layouts", flush=True)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
