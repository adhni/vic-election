#!/usr/bin/env python3
"""Audit political bands across state maps, county maps and county dots."""
import csv
import io
import json
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright
from test_state_clusters_ux import QuietHandler, expected_color

ROOT = Path(__file__).resolve().parents[1]
LABELS = {
    2: ["Republican", "Democratic"],
    3: ["Republican", "Swing / competitive", "Democratic"],
    4: ["Republican", "Lean Republican", "Lean Democratic", "Democratic"],
    5: ["Republican", "Lean Republican", "Swing / competitive", "Lean Democratic", "Democratic"],
    7: ["Strong Republican", "Republican", "Lean Republican", "Swing / competitive", "Lean Democratic", "Democratic", "Strong Democratic"],
}


def expected_model(data, k):
    places = data.get("counties", data.get("states"))
    groups = [{"members": [], "histories": [], "color": c} for c in ["#7851a9", "#c57928", "#288b87", "#4267b2", "#bd4c71", "#6b7f30", "#8c564b"][:k]]
    assignments = {}
    for name, record in places.items():
        history = [100 * record["votes"][str(year)]["democratic"] / (record["votes"][str(year)]["democratic"] + record["votes"][str(year)]["republican"]) for year in data["years"]]
        value = sum(history) / 5
        if k == 2:
            group = 1 if value < 50 else 2
        elif k == 3:
            group = 1 if value < 45 else 2 if value <= 55 else 3
        elif k == 4:
            group = 1 if value < 40 else 2 if value < 50 else 3 if value <= 60 else 4
        elif k == 7:
            group = 1 if value < 30 else 2 if value < 40 else 3 if value < 45 else 4 if value <= 55 else 5 if value <= 60 else 6 if value <= 70 else 7
        else:
            group = 1 if value < 40 else 2 if value < 45 else 3 if value <= 55 else 4 if value <= 60 else 5
        assignments[name] = group
        groups[group - 1]["members"].append(name)
        groups[group - 1]["histories"].append(history)
    for group in groups:
        group["mean_democratic_share"] = sum(sum(row) for row in group["histories"]) / (len(group["members"]) * 5) if group["members"] else None
    return assignments, groups


def check_marks(page, data, k, dots=False, region="all"):
    assignments, groups = expected_model(data, k)
    places = data.get("counties", data.get("states"))
    expected = {name for name in places if region == "all" or places[name]["state"] == region}
    selector = ".county-dot" if dots else ".state-shape"
    attribute = "county" if dots else "state"
    actual = page.locator(selector).evaluate_all(f"els => Object.fromEntries(els.map(el => [el.dataset.{attribute},el.getAttribute('fill')]))")
    assert set(actual) == expected
    mode = page.locator("#dotColors" if dots else "#colorMode").input_value()
    for name in expected:
        assert actual[name] == expected_color(groups[assignments[name] - 1], mode)
    labels = page.locator("#dotGroup option" if dots else "#groupFilter option").all_text_contents()[1:]
    assert all(label in value for label, value in zip(LABELS[k], labels)) and len(labels) == k
    return assignments, groups


def main():
    county = json.loads((ROOT / "data/us_county_presidential_clusters.json").read_text())
    state = json.loads((ROOT / "data/us_state_presidential_clusters.json").read_text())
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
    Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    screenshots = ROOT / "tmp/political-bands"
    screenshots.mkdir(parents=True, exist_ok=True)
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1550, "height": 1100}, accept_downloads=True)
            page.on("pageerror", lambda error: errors.append(str(error)))
            for geography, data in [("state", state), ("county", county)]:
                page.goto(f"{base}/app/{geography}-clusters.html", wait_until="networkidle")
                page.locator("#methodology").select_option("bands")
                for k in [2, 3, 4, 5, 7]:
                    page.locator("#clusterCount").select_option(str(k))
                    page.locator("#colorMode").select_option("groups")
                    check_marks(page, data, k)
                    page.locator("#colorMode").select_option("party")
                    check_marks(page, data, k)
                    expect(page.locator("#bandThresholdRows tr")).to_have_count(k)
                page.locator("#clusterCount").select_option("5")
                page.locator("#methodDetails > summary").click()
                expect(page.locator("#bandsDetails")).to_be_visible()
                expect(page.locator("#modelCards")).to_be_hidden()
                expect(page.locator(".ward-tree-export")).to_be_hidden()
                with page.expect_download() as download_info:
                    page.locator("#modelDownload").click()
                rows = list(csv.DictReader(io.StringIO(Path(download_info.value.path()).read_text())))
                assert len(rows) == len(data.get("counties", data.get("states")))
                assignments, groups = expected_model(data, 5)
                assert all(int(row["group"]) == assignments[row["place"]] and row["label"] == LABELS[5][int(row["group"]) - 1] and row["methodology"] == "bands" for row in rows)
                page.reload(wait_until="networkidle")
                expect(page.locator("#methodology")).to_have_value("bands")
                check_marks(page, data, 5)
                if geography == "county":
                    page.locator("#regionFilter").select_option("Michigan")
                    check_marks(page, data, 5, region="Michigan")
                    page.screenshot(path=str(screenshots / "county-map.png"), full_page=True)
                page.locator("#methodology").select_option("similarity")
                assert "method=bands" not in page.url
                page.go_back(wait_until="networkidle")
                expect(page.locator("#methodology")).to_have_value("bands")
            page.goto(f"{base}/app/county-dots.html", wait_until="networkidle")
            page.locator("#dotMethod").select_option("bands")
            for k in [2, 3, 4, 5, 7]:
                page.locator("#dotGroupCount").select_option(str(k))
                for colors in ["groups", "party"]:
                    page.locator("#dotColors").select_option(colors)
                    check_marks(page, county, k, dots=True)
                expect(page.locator("#dotBandRows tr")).to_have_count(k)
            page.locator("#dotGroupCount").select_option("5")
            page.screenshot(path=str(screenshots / "county-dots.png"), full_page=True)
            page.locator("#viewPatterns").click()
            check_marks(page, county, 5, dots=True)
            page.locator("#dotState").select_option("Michigan")
            check_marks(page, county, 5, dots=True, region="Michigan")
            page.locator("#dotCounty").select_option("Washtenaw County, Michigan")
            expect(page.locator("#storyGroup")).to_contain_text("Democratic")
            assert "method=bands" in page.locator("#storyMapLink").get_attribute("href")
            page.locator("#storyMapLink").click()
            expect(page.locator("#methodology")).to_have_value("bands")
            expect(page.locator("#selectedStateName")).to_have_text("Washtenaw County, Michigan")
            page.locator('nav a[href^="county-dots.html"]').click()
            expect(page.locator("#dotMethod")).to_have_value("bands")
            expect(page.locator("#storyName")).to_have_text("Washtenaw County, Michigan")
            page.locator("#dotBandDetails > summary").click()
            with page.expect_download() as download_info:
                page.locator("#dotBandDownload").click()
            rows = list(csv.DictReader(Path(download_info.value.path()).open()))
            assert len(rows) == 3103 and set(row["methodology"] for row in rows) == {"bands"}
            print("PASS all 2–5 and 7 political bands, exact labels and every map/dot colour, state filter, scatter, method switching, URL/history, cutoff display, downloads and map/dot crosslinks", flush=True)
            for width in [320, 390, 768]:
                for file, dots in [("county-clusters", False), ("county-dots", True)]:
                    mobile = browser.new_page(viewport={"width": width, "height": 900}, is_mobile=True, has_touch=True)
                    mobile.on("pageerror", lambda error: errors.append(str(error)))
                    mobile.goto(f"{base}/app/{file}.html?method=bands&k=5&region=Michigan", wait_until="networkidle")
                    check_marks(mobile, county, 5, dots=dots, region="Michigan")
                    assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                    mobile.screenshot(path=str(screenshots / f"{file}-{width}.png"), full_page=True)
                    mobile.close()
            browser.close()
        assert not errors, errors
        print("PASS political bands on phones/tablets at 320/390/768px", flush=True)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
