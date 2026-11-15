#!/usr/bin/env python3
"""Browser checks for the linked House demographic scatterplot and map."""

from __future__ import annotations

import argparse
import csv
import re
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright

from test_explorer_ux import QuietHandler, visit


ROOT = Path(__file__).resolve().parents[1]


def open_demographics(page, base_url):
    visit(page, base_url, "us-house-2024")
    page.get_by_role("button", name="Demographics", exact=True).click()
    expect(page.locator("#houseDemographicChart")).to_have_attribute("aria-busy", "false")
    expect(page.locator(".house-scatter-point")).to_have_count(397)


def check_links_and_statistics(page, base_url):
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    visit(page, base_url, "us-house-2024")
    expect(page.locator("#houseDemographicsPanel")).to_be_hidden()
    assert not any("us_2024_house_analysis" in url for url in requests), "Demographics should load only when opened"
    page.get_by_role("button", name="Demographics", exact=True).click()
    expect(page.locator(".house-scatter-point")).to_have_count(397)
    expect(page.locator('[data-statistic="pearson"]')).to_have_text("0.409")

    point = page.locator('.house-scatter-point[data-district="New York 14th"]')
    point.focus()
    point.press("Enter")
    expect(point).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#districtSummary h2")).to_have_text("New York 14th")
    expect(page.locator('.district-shape[data-district="New York 14th"]')).to_have_class(re.compile("active"))

    shape = page.locator('.district-shape[data-district="California 17th"]')
    shape.focus()
    shape.press("Enter")
    expect(page.locator("#houseDemographicDistrict")).to_have_value("California 17th")
    expect(page.locator('.house-scatter-point[data-district="California 17th"]')).to_have_attribute("aria-pressed", "true")

    page.locator("#houseDemographicUncertainty summary").click()
    expect(page.locator("#houseDemographicUncertaintyText")).to_contain_text("90% margin of error")
    page.get_by_role("button", name="View full district result").click()
    expect(page.locator("#districtSummary")).to_be_focused()

    # Audit every displayed correlation against the independently validated
    # Python artifact, in both samples.
    with (ROOT / "data/us_2024_house_analysis_correlations.csv").open() as handle:
        for row in csv.DictReader(handle):
            sample = "baseline" if row["sample"] == "both_major_parties" else "sensitivity"
            page.locator("#houseDemographicSample").select_option(sample)
            page.locator("#houseDemographicMetric").select_option(row["metric"])
            expect(page.locator(".house-scatter-point")).to_have_count(int(row["n"]))
            for field, attr in (("pearson_r", "pearson"), ("spearman_rho", "spearman"), ("within_state_pearson_r", "within-state")):
                expected = f"{float(row[field]):.3f}"
                expect(page.locator(f'[data-statistic="{attr}"]')).to_have_text(expected)

    page.locator("#houseDemographicSample").select_option("baseline")
    page.locator("#houseDemographicMetric").select_option("bachelors_plus_pct")
    marker = page.locator(".house-scatter-point").first
    marker.focus()
    marker.press("End")
    expect(page.locator('.house-scatter-point[data-index="396"]')).to_be_focused()
    page.locator('.house-scatter-point[data-index="396"]').press("Enter")
    expect(page.locator("#houseDemographicDistrict")).to_have_value("Wyoming at-large")
    print("PASS: lazy loading, map/scatter selection, keyboard navigation, uncertainty, all 20 correlation states", flush=True)


def check_missing_values_and_urls(page, base_url):
    open_demographics(page, base_url)
    page.locator("#houseDemographicMetric").select_option("english_only_pct")
    expect(page.locator(".house-scatter-point")).to_have_count(393)
    expect(page.locator("#houseDemographicStatus")).to_contain_text("4 missing")
    page.locator("#houseDemographicDistrict").select_option("Mississippi 2nd")
    expect(page.locator("#houseDemographicSelectedValues")).to_contain_text("Not published")
    expect(page.locator("#houseDemographicSelectedNote")).to_contain_text("not published")

    page.locator("#houseDemographicDistrict").select_option("Florida 20th")
    expect(page.locator("#houseDemographicSelectedValues")).to_contain_text("Not comparable")
    expect(page.locator("#houseDemographicSelectedNote")).to_contain_text("not reported")
    expect(page.locator('.house-scatter-point[aria-pressed="true"]')).to_have_count(0)

    page.locator("#houseDemographicMetric").select_option("median_household_income")
    page.locator("#houseDemographicSample").select_option("sensitivity")
    url = page.url
    assert "view=demographics" in url and "demographic=median_household_income" in url and "demographicSample=sensitivity" in url
    page.reload(wait_until="networkidle")
    expect(page.locator("#houseDemographicsPanel")).to_be_visible()
    expect(page.locator("#houseDemographicMetric")).to_have_value("median_household_income")
    expect(page.locator(".house-scatter-point")).to_have_count(389)
    expect(page.locator("#houseDemographicDistrict")).to_have_value("Florida 20th")
    page.get_by_role("button", name="Results", exact=True).click()
    expect(page.locator("#houseDemographicsPanel")).to_be_hidden()
    page.go_back(wait_until="networkidle")
    expect(page.locator("#houseDemographicsPanel")).to_be_visible()

    visit(page, base_url, "2022")
    expect(page.locator("#houseViewControls")).to_be_hidden()
    expect(page.locator("#houseDemographicsPanel")).to_be_hidden()
    visit(page, base_url, "us-house-2024")
    page.locator("#csvUpload").set_input_files(str(ROOT / "data/us_2024_house_fpp.csv"))
    expect(page.locator("#houseViewControls")).to_be_hidden()
    print("PASS: source gaps, excluded races, shareable URLs, history restoration and uploaded/election scope", flush=True)


def check_retry(browser, base_url):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.route("**/data/us_2024_house_analysis.csv", lambda route: route.fulfill(status=503, body="Unavailable"))
    visit(page, base_url, "us-house-2024")
    page.get_by_role("button", name="Demographics", exact=True).click()
    expect(page.get_by_role("button", name="Retry demographics")).to_be_visible()
    page.unroute("**/data/us_2024_house_analysis.csv")
    page.get_by_role("button", name="Retry demographics").click()
    expect(page.locator(".house-scatter-point")).to_have_count(397)
    page.close()
    print("PASS: recoverable demographic download error", flush=True)


def check_party_and_axis_ranges(browser, base_url, screenshots):
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    open_demographics(page, base_url)
    chart = page.locator("#houseDemographicChart svg")
    box = chart.bounding_box()
    assert box["width"] >= 740 and box["height"] >= 480, "Desktop scatterplot should have more space"
    assert box["width"] > page.locator("#explorerMap").bounding_box()["width"] * 1.5
    marker = page.locator('.house-scatter-point[data-district="Arizona 2nd"]')
    democratic_y = float(marker.get_attribute("cy"))
    page.locator("#houseDemographicParty").select_option("republican")
    expect(page.locator("#houseDemographicYLabel")).to_have_text("Republican two-party vote share (%)")
    expect(marker).to_have_attribute("aria-label", re.compile("Republican two-party vote share"))
    republican_y = float(marker.get_attribute("cy"))
    assert abs(democratic_y + republican_y - (float(chart.get_attribute("height")) - 30 + 12)) < 0.000001
    with (ROOT / "data/us_2024_house_analysis_correlations.csv").open() as handle:
        for row in csv.DictReader(handle):
            page.locator("#houseDemographicSample").select_option("baseline" if row["sample"] == "both_major_parties" else "sensitivity")
            page.locator("#houseDemographicMetric").select_option(row["metric"])
            for field, attr in (("pearson_r", "pearson"), ("spearman_rho", "spearman"), ("within_state_pearson_r", "within-state")):
                expect(page.locator(f'[data-statistic="{attr}"]')).to_have_text(f"{-float(row[field]):.3f}")

    page.locator("#houseDemographicSample").select_option("baseline")
    page.locator("#houseDemographicMetric").select_option("bachelors_plus_pct")
    page.locator("#houseDemographicDistrict").select_option("Arizona 2nd")
    expect(page.locator("#houseDemographicSelectedValues")).to_contain_text("Republican two-party vote share")
    before = page.locator("#houseDemographicStatistics").inner_text()
    for party in ("republican", "democratic"):
        page.locator("#houseDemographicParty").select_option(party)
        for metric in ("bachelors_plus_pct", "median_household_income", "median_age"):
            page.locator("#houseDemographicMetric").select_option(metric)
            unchanged_stats = page.locator("#houseDemographicStatistics").inner_text()
            for x_range, y_range in (("full", "full"), ("fit", "full"), ("full", "fit"), ("fit", "fit")):
                page.locator("#houseDemographicXRange").select_option(x_range)
                page.locator("#houseDemographicYRange").select_option(y_range)
                expect(page.locator(".house-scatter-point")).to_have_count(397)
                assert page.locator("#houseDemographicStatistics").inner_text() == unchanged_stats
                bounds = chart.evaluate("svg => ['x-min','x-max','y-min','y-max'].map(key => Number(svg.dataset[key.replace(/-([a-z])/g, (_, c) => c.toUpperCase())]))")
                if x_range == "full":
                    assert bounds[0] == 0
                    if metric.endswith("_pct"):
                        assert bounds[1] == 100
                else:
                    assert bounds[0] > 0, "Fitted X should omit empty zero range for these measures"
                if y_range == "full":
                    assert bounds[2:] == [0, 100]
                else:
                    assert bounds[3] - bounds[2] < 100
                assert chart.evaluate("""svg => [...svg.querySelectorAll('circle')].every(point => {
                    const x = point.cx.baseVal.value, y = point.cy.baseVal.value;
                    return Number.isFinite(x) && Number.isFinite(y) && x >= 38 - 0.001 && x <= Number(svg.getAttribute('width')) - 18 + 0.001
                        && y >= 12 - 0.001 && y <= Number(svg.getAttribute('height')) - 30 + 0.001;
                })"""), "An axis setting clipped a district"
    page.locator("#houseDemographicParty").select_option("republican")
    page.locator("#houseDemographicMetric").select_option("bachelors_plus_pct")
    assert page.locator("#houseDemographicStatistics").inner_text() == before
    assert all(key in page.url for key in ("demographicParty=republican", "demographicX=fit", "demographicY=fit"))
    page.reload(wait_until="networkidle")
    for selector, value in (("Party", "republican"), ("XRange", "fit"), ("YRange", "fit")):
        expect(page.locator(f"#houseDemographic{selector}")).to_have_value(value)
    expect(page.locator(".house-scatter-point")).to_have_count(397)
    expect(page.locator("#houseDemographicDistrict")).to_have_value("Arizona 2nd")
    page.locator("#houseDemographicYRange").select_option("full")
    page.go_back(wait_until="networkidle")
    expect(page.locator("#houseDemographicYRange")).to_have_value("fit")
    if screenshots:
        page.screenshot(path=str(screenshots / "demographics-republican-fit-1440.png"), full_page=True)
    page.close()
    print("PASS: larger chart, both parties, 20 mirrored correlations, independent axis ranges, no clipped dots and saved scale settings", flush=True)


def check_pending_election_switch(browser, base_url):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    pending = []
    page.route("**/data/us_2024_house_analysis.csv", lambda route: pending.append(route))
    visit(page, base_url, "us-house-2024")
    page.get_by_role("button", name="Demographics", exact=True).click()
    expect(page.locator("#houseDemographicStatus")).to_contain_text("Loading")
    with page.expect_event("requestfailed", predicate=lambda request: "us_2024_house_analysis.csv" in request.url):
        page.locator("#electionCountry").select_option("Australia")
    expect(page.locator("#electionCountry")).to_have_value("Australia")
    expect(page.locator("#explorerGrid")).to_have_attribute("aria-busy", "false")
    expect(page.locator("#houseDemographicsPanel")).to_be_hidden()
    for route in pending:
        route.continue_()
    page.unroute("**/data/us_2024_house_analysis.csv")
    page.go_back(wait_until="networkidle")
    expect(page.locator("#houseDemographicsPanel")).to_be_visible()
    expect(page.locator(".house-scatter-point")).to_have_count(397)
    page.close()
    print("PASS: pending requests abort on election switch and recover through browser history", flush=True)


def check_layout_and_touch(browser, base_url, screenshots):
    for width in (320, 390, 768, 1440):
        page = browser.new_page(viewport={"width": width, "height": 1050}, has_touch=True)
        open_demographics(page, base_url)
        page.locator("#houseDemographicMetric").select_option("household_income_under_50k_pct")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), f"Page overflow at {width}px"
        assert page.locator("#houseDemographicChart svg").evaluate("""svg => {
            const box = svg.getBoundingClientRect();
            return [...svg.querySelectorAll('text')].every(text => {
                const b = text.getBoundingClientRect();
                return b.left >= box.left - 1 && b.right <= box.right + 1;
            });
        }"""), f"Clipped axis labels at {width}px"
        # Choose an isolated point so this is a real touch hit, including on
        # mobile where many other observations overlap.
        isolated = page.locator("#houseDemographicChart svg").evaluate("""svg => {
            const circles = [...svg.querySelectorAll('circle')];
            return circles.find(c => circles.every(other => c === other || Math.hypot(c.cx.baseVal.value - other.cx.baseVal.value, c.cy.baseVal.value - other.cy.baseVal.value) > 12)).dataset.district;
        }""")
        page.locator(f'.house-scatter-point[data-district="{isolated}"]').tap()
        expect(page.locator("#houseDemographicDistrict")).to_have_value(isolated)
        if screenshots and width in (390, 1440):
            page.screenshot(path=str(screenshots / f"demographics-{width}.png"), full_page=True)
        page.set_viewport_size({"width": 390 if width == 1440 else 1440, "height": 1050})
        page.wait_for_function("""() => {
            const chart = document.getElementById('houseDemographicChart');
            return Math.abs(chart.clientWidth - chart.querySelector('svg').viewBox.baseVal.width) < 2;
        }""")
        expect(page.locator("#houseDemographicDistrict")).to_have_value(isolated)
        page.close()
        print(f"PASS: responsive chart, axis labels, real touch selection and resize at {width}px", flush=True)


def check_election_comparison(browser, base_url, screenshots):
    from build_us_house_analysis import pearson, average_ranks
    with (ROOT / "data/us_house_2022_2024_comparison.csv").open() as handle:
        comparisons = {row["district"]: row for row in csv.DictReader(handle)}
    with (ROOT / "data/us_2024_house_analysis.csv").open() as handle:
        demographics = {row["district"]: row for row in csv.DictReader(handle)}
    matched = [r for r in comparisons.values() if r["comparison_eligible"] == "true"]
    page = browser.new_page(viewport={"width": 1440, "height": 1050})
    open_demographics(page, base_url)
    prior_x = {}
    correlations = {}
    for party in ("democratic", "republican"):
        page.locator("#houseDemographicParty").select_option(party)
        for outcome in ("2022-matched", "2024-matched", "change"):
            page.locator("#houseDemographicOutcome").select_option(outcome)
            expect(page.locator(".house-scatter-point")).to_have_count(len(matched))
            expect(page.locator("#houseDemographicComparisonNote")).to_contain_text("2024 ACS demographics held fixed")
            field = "democratic_share_change_pp" if outcome == "change" else f"democratic_two_party_share_pct_{outcome[:4]}"
            x = [float(demographics[r["district"]]["bachelors_plus_pct"]) for r in matched]
            y = [float(r[field]) for r in matched]
            if party == "republican":
                y = [-v if outcome == "change" else 100 - v for v in y]
            expected = (pearson(x, y), pearson(average_ranks(x), average_ranks(y)))
            for attr, value in zip(("pearson", "spearman"), expected):
                expect(page.locator(f'[data-statistic="{attr}"]')).to_have_text(f"{value:.3f}")
            correlations[party, outcome] = expected[0]
            points = page.locator(".house-scatter-point").evaluate_all("els => Object.fromEntries(els.map(e => [e.dataset.district, Number(e.getAttribute('cx'))]))")
            if prior_x:
                assert points == prior_x, "Matched districts must keep identical X positions across outcomes and parties"
            prior_x = points
            expect(page.locator('.house-scatter-point[data-district="New York 14th"]')).to_have_count(0)
            expect(page.locator('.house-scatter-point[data-district="Maine 2nd"]')).to_have_count(0)
            page.locator("#houseDemographicDistrict").select_option(label="California 17th")
            expect(page.locator("#houseDemographicSelectedValues")).to_contain_text("2022:")
            expect(page.locator("#houseDemographicSelectedValues")).to_contain_text("Change:")
            if outcome == "change":
                expect(page.locator("#houseDemographicYLabel")).to_contain_text("2024 − 2022 (pp)")
                for axis in ("full", "fit"):
                    page.locator("#houseDemographicYRange").select_option(axis)
                    svg = page.locator("#houseDemographicChart svg")
                    low, high = float(svg.get_attribute("data-y-min")), float(svg.get_attribute("data-y-max"))
                    assert low < min(y) < 0 < max(y) < high
                    if axis == "full":
                        assert (low, high) == (-100, 100)
                    else:
                        assert high - low < 100
                    assert page.locator(".house-scatter-point").evaluate_all("els => els.every(e => Number(e.getAttribute('cy')) >= 12 && Number(e.getAttribute('cy')) <= Number(e.ownerSVGElement.getAttribute('height')) - 30)")
            page.locator("#houseDemographicYRange").select_option("full")
    for outcome in ("2022-matched", "2024-matched", "change"):
        assert abs(correlations["democratic", outcome] + correlations["republican", outcome]) < 1e-12
    page.locator("#houseDemographicDistrict").select_option(label="New York 14th")
    expect(page.locator("#houseDemographicSelectedNote")).to_contain_text("plan changed")
    expect(page.locator("#houseDemographicSelectedValues")).to_contain_text("Not comparable")
    page.locator("#houseDemographicSample").select_option("sensitivity")
    expect(page.locator(".house-scatter-point")).to_have_count(312)
    page.locator("#houseDemographicYRange").select_option("fit")
    page.locator("#houseDemographicXRange").select_option("fit")
    assert "demographicOutcome=change" in page.url
    page.reload()
    expect(page.locator(".house-scatter-point")).to_have_count(312)
    expect(page.locator("#houseDemographicOutcome")).to_have_value("change")
    expect(page.locator("#houseDemographicParty")).to_have_value("republican")
    page.locator("#houseDemographicOutcome").select_option("2022-matched")
    page.go_back()
    expect(page.locator("#houseDemographicOutcome")).to_have_value("change")
    if screenshots:
        page.screenshot(path=str(screenshots / "demographics-comparison-1440.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 1050})
    page.wait_for_function("() => Math.abs(document.querySelector('#houseDemographicChart svg').viewBox.baseVal.width - document.querySelector('#houseDemographicChart').clientWidth) < 2")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    assert page.locator("#houseDemographicChart svg").evaluate("svg => [...svg.querySelectorAll('text')].every(t => t.getBoundingClientRect().left >= svg.getBoundingClientRect().left - 1)")
    if screenshots:
        page.screenshot(path=str(screenshots / "demographics-comparison-390.png"), full_page=True)
    page.locator("#houseDemographicOutcome").select_option("2024")
    page.locator("#houseDemographicSample").select_option("baseline")
    expect(page.locator(".house-scatter-point")).to_have_count(397)
    page.close()
    print("PASS: matched election samples, source correlations, fixed demographics, signed party changes, axes, exclusions, history and mobile layout", flush=True)


def check_2022_entry(browser, base_url):
    page = browser.new_page(viewport={"width": 1440, "height": 1050})
    visit(page, base_url, "us-house-2022")
    expect(page.locator("#houseViewControls")).to_be_visible()
    page.get_by_role("button", name="Demographics", exact=True).click()
    expect(page.locator(".house-scatter-point")).to_have_count(312)
    expect(page.locator("#houseDemographicOutcome")).to_have_value("2022-matched")
    expect(page.locator("#houseDemographicYLabel")).to_contain_text("2022")
    expect(page.locator("#houseDemographicComparisonNote")).to_contain_text("Map and full results show 2022")
    page.locator("#houseDemographicDistrict").select_option("California 17th")
    expect(page.locator("#districtSummary h2")).to_have_text("California 17th")
    expect(page.locator('.district-shape[data-district="California 17th"]')).to_have_class(re.compile("active"))
    page.reload(wait_until="networkidle")
    expect(page.locator("#electionYear")).to_have_value("us-house-2022")
    expect(page.locator("#houseDemographicOutcome")).to_have_value("2022-matched")
    expect(page.locator(".house-scatter-point")).to_have_count(312)
    page.locator("#houseDemographicOutcome").select_option("change")
    expect(page.locator("#houseDemographicYLabel")).to_contain_text("2024 − 2022")
    page.locator("#electionYear").select_option("us-house-2024")
    expect(page.locator("#houseDemographicComparisonNote")).to_contain_text("Map and full results show 2024")
    page.locator("#houseDemographicOutcome").select_option("2024")
    expect(page.locator(".house-scatter-point")).to_have_count(397)
    page.locator("#electionYear").select_option("us-house-2022")
    expect(page.locator("#houseDemographicOutcome")).to_have_value("2022-matched")
    expect(page.locator(".house-scatter-point")).to_have_count(312)
    page.close()
    # Direct links need the same default even without an outcome parameter.
    page = browser.new_page()
    page.goto(f"{base_url}/app/?year=us-house-2022&view=demographics", wait_until="networkidle")
    expect(page.locator("#houseDemographicOutcome")).to_have_value("2022-matched")
    expect(page.locator(".house-scatter-point")).to_have_count(312)
    page.close()
    print("PASS: House 2022 entry, default outcome, linked map, reload, direct links and year switching", flush=True)


def check_swing_map(browser, base_url, screenshots):
    with (ROOT / "data/us_house_2022_2024_comparison.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    matched = [r for r in rows if r["comparison_eligible"] == "true"]
    page = browser.new_page(viewport={"width": 1440, "height": 1050})
    visit(page, base_url, "us-house-2024")
    # The map's entry point also opens the linked swing scatterplot.
    page.locator("#mapModeSelect").select_option("house-swing")
    expect(page.locator("#houseDemographicOutcome")).to_have_value("change")
    expect(page.locator(".house-scatter-point")).to_have_count(312)
    expect(page.locator("#houseSwingRankings")).to_be_visible()
    expect(page.locator("#mapModeSelect")).to_have_value("house-swing")
    expect(page.locator("#mapLegend")).to_contain_text("Not comparable")
    expect(page.locator("#mapSubtitle")).to_contain_text("Blue toward Democrats")
    colors = page.locator(".district-shape").evaluate_all("els => Object.fromEntries(els.map(e => [e.dataset.district, e.getAttribute('fill')]))")
    for row in rows:
        if row["comparison_eligible"] != "true":
            expected = "#8b9098"
        else:
            delta = float(row["democratic_share_change_pp"])
            expected = "#f1efeb" if abs(delta) < .5 else ("#2166ac" if delta >= 5 else "#9ecae1") if delta > 0 else ("#b51f24" if delta <= -5 else "#efaaa3")
        assert colors[row["district"]] == expected, row["district"]
    for direction, sign in (("democratic", 1), ("republican", -1)):
        expected = sorted((r for r in matched if float(r["democratic_share_change_pp"]) * sign > 0), key=lambda r: -abs(float(r["democratic_share_change_pp"])))[:5]
        buttons = page.locator(f".house-swing-{direction} button")
        assert buttons.evaluate_all("els => els.map(e => e.dataset.district)") == [r["district"] for r in expected]
        row = expected[0]
        buttons.first.focus()
        buttons.first.press("Enter")
        expect(buttons.first).to_be_focused()
        expect(buttons.first).to_have_attribute("aria-pressed", "true")
        expect(page.locator(f'.house-scatter-point[data-district="{row["district"]}"]')).to_have_attribute("aria-pressed", "true")
        expect(page.locator(f'.district-shape[data-district="{row["district"]}"]')).to_have_class(re.compile("active"))
        expect(buttons.first).to_contain_text(f"{float(row['democratic_two_party_share_pct_2022']):.1f}% → {float(row['democratic_two_party_share_pct_2024']):.1f}%")
    page.locator("#houseDemographicParty").select_option("republican")
    assert colors == page.locator(".district-shape").evaluate_all("els => Object.fromEntries(els.map(e => [e.dataset.district, e.getAttribute('fill')]))"), "Map direction must not flip with chart party"
    expect(page.locator("#houseSwingRankingNote")).to_contain_text("Republican two-party shares")
    # Changing the demographic must not remove otherwise comparable map seats.
    page.locator("#houseDemographicMetric").select_option("english_only_pct")
    assert colors == page.locator(".district-shape").evaluate_all("els => Object.fromEntries(els.map(e => [e.dataset.district, e.getAttribute('fill')]))")
    assert "mode=house-swing" in page.url
    page.reload(wait_until="networkidle")
    expect(page.locator("#mapModeSelect")).to_have_value("house-swing")
    expect(page.locator("#houseSwingRankings")).to_be_visible()
    expect(page.locator('.district-shape[data-district="New York 14th"]')).to_have_attribute("fill", "#8b9098")
    page.locator('.district-shape[data-district="California 17th"]').focus()
    page.locator('.district-shape[data-district="California 17th"]').press("Enter")
    expect(page.locator("#houseDemographicDistrict")).to_have_value("California 17th")
    if screenshots:
        page.screenshot(path=str(screenshots / "swing-map-1440.png"), full_page=True)
    page.locator("#houseDemographicOutcome").select_option("2024-matched")
    expect(page.locator("#mapModeSelect")).to_have_value("party")
    expect(page.locator("#houseSwingRankings")).to_be_hidden()
    page.go_back(wait_until="networkidle")
    expect(page.locator("#mapModeSelect")).to_have_value("house-swing")
    expect(page.locator("#houseSwingRankings")).to_be_visible()
    page.set_viewport_size({"width": 390, "height": 1050})
    page.wait_for_function("() => Math.abs(document.querySelector('#houseDemographicChart svg').viewBox.baseVal.width - document.querySelector('#houseDemographicChart').clientWidth) < 2")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    page.locator('[data-map-mode="party"]').click()
    page.locator("#houseSwingMapMode").click()
    expect(page.locator("#houseDemographicOutcome")).to_have_value("change")
    if screenshots:
        page.screenshot(path=str(screenshots / "swing-map-390.png"), full_page=True)
    # Both election pages expose the same comparison; unrelated elections hide it.
    page.locator("#electionYear").select_option("us-house-2022")
    expect(page.locator("#houseSwingMapMode")).not_to_have_class(re.compile("hidden"))
    page.locator("#houseSwingMapMode").click()
    expect(page.locator(".house-scatter-point")).to_have_count(308)  # four matched language estimates are missing
    expect(page.locator("#houseDemographicComparisonNote")).to_contain_text("results show 2022")
    visit(page, base_url, "2022")
    expect(page.locator("#houseSwingMapMode")).to_have_class(re.compile("hidden"))
    page.close()
    # A map-only URL must load the comparison even with the panel closed.
    page = browser.new_page()
    page.goto(f"{base_url}/app/?year=us-house-2024&mode=house-swing", wait_until="networkidle")
    expect(page.locator("#houseDemographicsPanel")).to_be_hidden()
    expect(page.locator('.district-shape[data-district="California 17th"]')).not_to_have_attribute("fill", "#8b9098")
    page.close()
    print("PASS: all 435 swing colours, excluded geography, top shifts, linked keyboard selection, party-invariant map, URLs, history, mobile and map-only loading", flush=True)


def check_seat_flip_badges(browser, base_url):
    page = browser.new_page(viewport={"width": 1440, "height": 1050})
    open_demographics(page, base_url)
    page.locator("#houseDemographicOutcome").select_option("change")
    with (ROOT / "data/us_house_2022_2024_comparison.csv").open() as handle:
        flips = {row["district"] for row in csv.DictReader(handle) if row["seat_flipped"] == "true" and row["comparison_eligible"] == "true"}
    expect(page.get_by_text("Outlined = flipped seat", exact=True)).to_be_visible()
    assert set(page.locator(".house-seat-flipped").evaluate_all("els => els.map(e => e.dataset.district)")) == flips
    for district, text in (("California 13th", "Flipped to Democrat"), ("Colorado 8th", "Flipped to Republican")):
        page.locator("#houseDemographicDistrict").select_option(district)
        expect(page.locator("#houseDemographicFlip")).to_contain_text(text)
        expect(page.locator("#houseDemographicFlip")).to_contain_text("2022 → 2024")
        marker = page.locator(f'.house-scatter-point[data-district="{district}"]')
        expect(marker).to_have_attribute("aria-label", re.compile(text))
        expect(marker).to_have_class(re.compile("house-seat-flipped"))
        assert marker.evaluate("e => getComputedStyle(e).strokeWidth") == "2px"
        expect(page.locator(f'.district-shape[data-district="{district}"]')).to_have_attribute("aria-label", re.compile(text))
        page.locator("#houseDemographicParty").select_option("republican")
        expect(page.locator("#houseDemographicFlip")).to_contain_text(text)
    page.locator("#houseDemographicDistrict").select_option("Montana 2nd")
    expect(page.locator("#houseDemographicFlip")).to_be_hidden()
    held = page.locator('.house-scatter-point[data-district="Montana 2nd"]')
    expect(held).not_to_have_class(re.compile("house-seat-flipped"))
    assert held.evaluate("e => getComputedStyle(e).stroke") == "rgb(255, 255, 255)"
    page.locator("#houseDemographicDistrict").select_option("New York 19th")
    expect(page.locator("#houseDemographicFlip")).to_be_hidden()
    page.locator("#houseDemographicDistrict").select_option("Alaska at-large")
    expect(page.locator("#houseDemographicFlip")).to_contain_text("Flipped to Republican")
    expect(page.locator("#houseDemographicSelectedValues")).to_contain_text("Not comparable")
    page.set_viewport_size({"width": 320, "height": 1000})
    page.locator("#houseDemographicDistrict").select_option("California 13th")
    expect(page.locator("#houseDemographicFlip")).to_contain_text("Flipped to Democrat")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    page.close()
    print("PASS: actual winner flips, party-independent badges, held seats, unverified boundaries, excluded-count races and mobile", flush=True)


def check_earlier_period(browser, base_url):
    with (ROOT / "data/us_house_2020_2022_comparison.csv").open() as handle:
        matched = [row for row in csv.DictReader(handle) if row["comparison_eligible"] == "true"]
    page = browser.new_page(viewport={"width": 1440, "height": 1050})
    open_demographics(page, base_url)
    page.locator("#houseDemographicPeriod").select_option("2020-2022")
    expect(page.locator(".house-scatter-point")).to_have_count(3)
    assert set(page.locator(".house-scatter-point").evaluate_all("els => els.map(e => e.dataset.district)")) == {r["district"] for r in matched}
    expect(page.locator("#houseDemographicComparisonNote")).to_contain_text("District audit: 6 unchanged seats; 3 with comparable contests")
    page.locator("#houseDemographicDistrict").select_option("Hawaii 2nd")
    expect(page.locator("#houseDemographicSelectedNote")).to_contain_text("this district’s boundaries changed")
    expect(page.locator("#houseDemographicSelectedNote")).not_to_contain_text("not been individually verified")
    expect(page.locator("#mapSubtitle")).to_contain_text("2020 → 2022")
    expect(page.locator("#houseSwingTitle")).to_contain_text("2020 → 2022")
    expect(page.locator("#houseDemographicYLabel")).to_contain_text("2022 − 2020")
    expect(page.locator(".house-seat-flipped")).to_have_count(0)
    expect(page.locator('.district-shape[data-district="California 13th"]')).to_have_attribute("fill", "#8b9098")
    for row in matched:
        expect(page.locator(f'.district-shape[data-district="{row["district"]}"]')).not_to_have_attribute("fill", "#8b9098")
        page.locator("#houseDemographicDistrict").select_option(row["district"])
        values = page.locator("#houseDemographicSelectedValues")
        expect(values).to_contain_text("2020:")
        expect(values).to_contain_text("2022:")
        expect(values).not_to_contain_text("2024:")
    for outcome in ("2020-matched", "2022-matched", "change"):
        page.locator("#houseDemographicOutcome").select_option(outcome)
        expect(page.locator(".house-scatter-point")).to_have_count(3)
        for party in ("republican", "democratic"):
            page.locator("#houseDemographicParty").select_option(party)
            for row in matched:
                field = "democratic_share_change_pp" if outcome == "change" else f"democratic_two_party_share_pct_{outcome[:4]}"
                expected = float(row[field])
                if party == "republican": expected = -expected if outcome == "change" else 100 - expected
                expect(page.locator(f'.house-scatter-point[data-district="{row["district"]}"]')).to_have_attribute("aria-label", re.compile(re.escape(f"{expected:.1f}")))
    expect(page.locator("#houseComparisonDownload")).to_have_attribute("href", "../data/us_house_2020_2022_comparison.csv")
    page.locator("#houseDemographicDistrict").select_option("Alaska at-large")
    expect(page.locator("#houseDemographicFlip")).to_contain_text("Flipped to Democrat")
    expect(page.locator("#houseDemographicFlip")).to_contain_text("2020 → 2022")
    page.reload(wait_until="networkidle")
    expect(page.locator("#houseDemographicPeriod")).to_have_value("2020-2022")
    expect(page.locator(".house-scatter-point")).to_have_count(3)
    page.set_viewport_size({"width": 390, "height": 1050})
    page.wait_for_function("() => Math.abs(document.querySelector('#houseDemographicChart svg').viewBox.baseVal.width - document.querySelector('#houseDemographicChart').clientWidth) < 2")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    page.locator("#houseDemographicPeriod").select_option("2022-2024")
    expect(page.locator(".house-scatter-point")).to_have_count(312)
    expect(page.locator(".house-seat-flipped")).to_have_count(8)
    expect(page.locator("#houseSwingTitle")).to_contain_text("2022 → 2024")
    page.go_back(wait_until="networkidle")
    expect(page.locator("#houseDemographicPeriod")).to_have_value("2020-2022")
    expect(page.locator(".house-scatter-point")).to_have_count(3)
    page.close()
    print("PASS: 2020–2022 period, three verified seats, grey exclusions, year-specific shares and flips, party switching, downloads, reload, mobile and history", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
    Thread(target=server.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    errors = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.on("page", lambda page: page.on("pageerror", lambda error: errors.append(str(error))))
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            check_links_and_statistics(page, base_url)
            check_missing_values_and_urls(page, base_url)
            page.close()
            check_party_and_axis_ranges(browser, base_url, args.screenshots)
            check_election_comparison(browser, base_url, args.screenshots)
            check_2022_entry(browser, base_url)
            check_swing_map(browser, base_url, args.screenshots)
            check_seat_flip_badges(browser, base_url)
            check_earlier_period(browser, base_url)
            check_retry(browser, base_url)
            check_pending_election_switch(browser, base_url)
            check_layout_and_touch(browser, base_url, args.screenshots)
            browser.close()
        assert not errors, errors
        print("All House demographic browser checks passed; no runtime errors.")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
