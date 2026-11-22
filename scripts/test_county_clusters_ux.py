#!/usr/bin/env python3
"""Check nationwide county maps, state zoom, linked history and mobile layout."""
import json
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright

from test_state_clusters_ux import QuietHandler, expected_color

ROOT = Path(__file__).resolve().parents[1]


def check_map(page, data, k, region="all"):
    names = {name for name, record in data["counties"].items() if region == "all" or record["state"] == region}
    paths = page.locator(".state-shape").evaluate_all("els => Object.fromEntries(els.map(el => [el.dataset.state, el.getAttribute('fill')]))")
    assert set(paths) == names
    model = data["models"][str(k)]
    color_mode = page.locator("#colorMode").input_value()
    for name in names:
        assert paths[name] == expected_color(model["groups"][model["assignments"][name]["group"] - 1], color_mode)
    expect(page.locator("#stateSelect option")).to_have_count(len(names))
    expect(page.locator("#profileRows tr")).to_have_count(k + 1)


def main():
    data = json.loads((ROOT / "data/us_county_presidential_clusters.json").read_text())
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
    Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    screenshots = ROOT / "tmp/county-clusters"
    screenshots.mkdir(parents=True, exist_ok=True)
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1100})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"{base}/app/county-clusters.html", wait_until="networkidle")
            expect(page.locator("#clusterContent")).to_be_visible()
            expect(page.locator("#selectedStateName")).to_have_text("Wayne County, Michigan")
            expect(page.locator("#modelCards")).to_be_hidden()
            expect(page.locator("#regionFilter option")).to_have_count(49)
            assert not page.locator('#regionFilter option[value="Alaska"]').count()
            assert not page.locator('#regionFilter option[value="Connecticut"]').count()
            for k in [2, 3, 5, 7, 4]:
                page.locator("#clusterCount").select_option(str(k))
                check_map(page, data, k)
                page.locator("#colorMode").select_option("party")
                check_map(page, data, k)
                for i, group in enumerate(data["models"][str(k)]["groups"]):
                    expect(page.locator("#profileChart g path").nth(i)).to_have_attribute("stroke", expected_color(group, "party"))
                page.locator("#colorMode").select_option("groups")
            assert page.locator("#groupCards .state-buttons button").count() <= 124
            page.locator("#colorMode").select_option("party")
            page.reload(wait_until="networkidle")
            expect(page.locator("#colorMode")).to_have_value("party")
            check_map(page, data, 4)
            page.screenshot(path=str(screenshots / "desktop.png"), full_page=True)
            page.locator("#colorMode").select_option("groups")
            group = data["models"]["4"]["groups"][0]
            page.locator('#groupCards [data-expand="1"]').click()
            expect(page.locator('#groupCards article').first.locator('.state-buttons button')).to_have_count(group["size"])
            page.locator("#regionFilter").select_option("Michigan")
            check_map(page, data, 4, "Michigan")
            page.locator('#stateSelect').select_option("Washtenaw County, Michigan")
            expect(page.locator("#selectedStateName")).to_have_text("Washtenaw County, Michigan")
            expect(page.locator("#openStateResults")).to_have_attribute("href", "./?year=us-president-2024&geo=county&district=Washtenaw%20County%2C%20Michigan")
            page.locator(".vote-details > summary").click()
            for i, row in enumerate(page.locator("#stateVoteRows tr").all()):
                year = str(data["years"][i])
                record = data["counties"]["Washtenaw County, Michigan"]
                expect(row.locator("td").nth(0)).to_have_text(f'{record["votes"][year]["democratic"]:,}')
                expect(row.locator("td").last).to_have_text(f'{record["democratic_share"][i]:.1f}%')
            page.reload(wait_until="networkidle")
            expect(page.locator("#regionFilter")).to_have_value("Michigan")
            expect(page.locator("#stateSelect")).to_have_value("Washtenaw County, Michigan")
            page.locator("#groupFilter").select_option("1")
            assert page.locator("#selectedStateName").inner_text().endswith(", Michigan")
            page.locator("#regionFilter").select_option("Hawaii")
            check_map(page, data, 4, "Hawaii")
            assert page.locator("#clusterMap path").evaluate_all("els => els.every(el => !/NaN|Infinity/.test(el.getAttribute('d')))")
            selected = page.locator("#stateSelect").input_value()
            page.locator(f'.state-shape[data-state="{selected}"]').focus()
            page.locator(f'.state-shape[data-state="{selected}"]').press("ArrowRight")
            page.keyboard.press("Enter")
            assert page.locator("#stateSelect").input_value() != selected
            page.locator("#resetClusters").click()
            check_map(page, data, 4)
            page.goto(f"{base}/app/county-clusters.html?k=99&county=Atlantis&region=Alaska&group=1.5", wait_until="networkidle")
            expect(page.locator("#stateSelect")).to_have_value("Wayne County, Michigan")
            expect(page.locator("#regionFilter")).to_have_value("all")
            expect(page.locator("#groupFilter")).to_have_value("all")
            page.locator("#regionFilter").select_option("Texas")
            page.go_back(wait_until="networkidle")
            expect(page.locator("#regionFilter")).to_have_value("all")
            print("PASS all 3,103 county colours in all five models, state zoom, county selection, exact votes, URLs, reload/back, Hawaii, keyboard, group expansion and invalid URL recovery", flush=True)
            for width in [320, 390, 768]:
                mobile = browser.new_page(viewport={"width": width, "height": 900}, is_mobile=True, has_touch=True)
                mobile.on("pageerror", lambda error: errors.append(str(error)))
                mobile.goto(f"{base}/app/county-clusters.html?region=Michigan", wait_until="networkidle")
                expect(mobile.locator("#clusterContent")).to_be_visible()
                check_map(mobile, data, 4, "Michigan")
                mobile.locator("#clusterCount").select_option("5")
                check_map(mobile, data, 5, "Michigan")
                mobile.locator("#colorMode").select_option("party")
                check_map(mobile, data, 5, "Michigan")
                assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                mobile.screenshot(path=str(screenshots / f"mobile-{width}.png"), full_page=True)
                mobile.close()
            page.goto(base, wait_until="networkidle")
            expect(page.locator('a[href="app/county-clusters.html"]')).to_be_visible()
            page.goto(f"{base}/app/?year=us-president-2024", wait_until="networkidle")
            expect(page.locator('#stateClusteringEntry a[href="county-clusters.html"]')).to_be_visible()
            browser.close()
        assert not errors, errors
        print("PASS mobile layouts at 320/390/768px and county entry links", flush=True)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
