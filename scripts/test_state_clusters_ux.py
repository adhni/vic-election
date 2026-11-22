#!/usr/bin/env python3
"""Browser checks for cluster models, linked map, profiles, history and mobile."""
import json
import math
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def copyfile(self, source, outputfile):
        try:
            super().copyfile(source, outputfile)
        except (BrokenPipeError, ConnectionResetError):
            pass  # A browser can abort pending assets when changing elections.


def expected_color(group, mode):
    if mode == "groups":
        return group["color"]
    share = group["mean_democratic_share"]
    end = (33, 102, 172) if share >= 50 else (178, 24, 43)
    strength = min(1, abs(share - 50) / 25)
    return "#" + "".join(f"{math.floor(166 + (value - 166) * strength + .5):02x}" for value in end)


def check_assignments(page, data, k):
    actual = page.locator(".state-shape").evaluate_all("nodes => Object.fromEntries(nodes.map(el => [el.dataset.state, el.getAttribute('fill')]))")
    model = data["models"][str(k)]
    assert len(actual) == 50 and "District of Columbia" not in actual
    color_mode = page.locator("#colorMode").input_value()
    for name, assignment in model["assignments"].items():
        assert actual[name] == expected_color(model["groups"][assignment["group"] - 1], color_mode)
    expect(page.locator("#groupCards .state-buttons button")).to_have_count(50)
    expect(page.locator("#profileRows tr")).to_have_count(k + 1)
    expect(page.locator("#clusterLegend [data-group]")).to_have_count(k + 1)


def main():
    data = json.loads((ROOT / "data/us_state_presidential_clusters.json").read_text())
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT)))
    Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    screenshots = ROOT / "tmp/state-clusters"
    screenshots.mkdir(parents=True, exist_ok=True)
    errors = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1100})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"{base}/app/state-clusters.html", wait_until="networkidle")
            expect(page.locator("#clusterContent")).to_be_visible()
            expect(page.locator("#clusterCount")).to_have_value("4")
            assert page.locator("#clusterCount option").evaluate_all("els => els.map(el => el.value)") == ["2", "3", "4", "5", "7"]
            expect(page.locator("#selectedStateName")).to_have_text("Michigan")
            expect(page.locator("#modelInterpretation")).to_contain_text(f"{max(data['models'].values(), key=lambda m: m['silhouette'])['k']} groups has the highest silhouette score")
            expect(page.locator("#modelCards")).to_be_hidden()
            expect(page.locator("#selectedStateStats")).not_to_contain_text("Silhouette")
            expect(page.locator("#selectedStateNote")).to_contain_text("Republicans led")
            expect(page.locator("#groupCards")).to_contain_text("Strongly Republican")
            page.locator("#methodDetails > summary").click()
            for k in [2, 3, 5, 7, 4]:
                page.locator(f'#modelCards [data-k="{k}"]').click()
                expect(page.locator("#clusterCount")).to_have_value(str(k))
                check_assignments(page, data, k)
                page.locator("#colorMode").select_option("party")
                check_assignments(page, data, k)
                expect(page.locator("#partyColorKey")).to_be_visible()
                for i, group in enumerate(data["models"][str(k)]["groups"]):
                    expect(page.locator("#profileChart g path").nth(i)).to_have_attribute("stroke", expected_color(group, "party"))
                page.locator("#colorMode").select_option("groups")
            page.locator("#methodDetails > summary").click()
            expect(page.locator("#modelCards")).to_be_hidden()
            page.locator("#colorMode").select_option("party")
            page.reload(wait_until="networkidle")
            expect(page.locator("#colorMode")).to_have_value("party")
            check_assignments(page, data, 4)
            page.screenshot(path=str(screenshots / "desktop.png"), full_page=True)
            page.locator("#colorMode").select_option("groups")
            page.locator('.state-shape[data-state="Alaska"]').focus()
            page.locator('.state-shape[data-state="Alaska"]').press("Enter")
            expect(page.locator("#selectedStateName")).to_have_text("Alaska")
            expect(page.locator("#stateSelect")).to_have_value("Alaska")
            expect(page.locator("#stateVoteRows tr")).to_have_count(5)
            expect(page.locator("#openStateResults")).to_have_attribute("href", "./?year=us-president-2024&district=Alaska")
            page.locator("#groupFilter").select_option("4")
            assert page.locator(".state-shape.muted").count() == 50 - data["models"]["4"]["groups"][3]["size"]
            selected = page.locator("#selectedStateName").inner_text()
            page.reload(wait_until="networkidle")
            expect(page.locator("#groupFilter")).to_have_value("4")
            expect(page.locator("#selectedStateName")).to_have_text(selected)
            page.locator("#stateSelect").select_option("Texas")
            expect(page.locator("#selectedStateName")).to_have_text("Texas")
            expect(page.locator("#groupFilter")).to_have_value("all")
            assert "Texas" in page.locator("#profileChartDescription").text_content()
            for i, row in enumerate(page.locator("#stateVoteRows tr").all()):
                value = data["states"]["Texas"]["democratic_share"][i]
                expect(row.locator("td").last).to_have_text(f"{value:.1f}%")
            page.go_back(wait_until="networkidle")
            expect(page.locator("#groupFilter")).to_have_value("4")
            page.locator("#resetClusters").click()
            expect(page.locator("#selectedStateName")).to_have_text("Michigan")
            expect(page.locator("#groupFilter")).to_have_value("all")
            page.locator("#methodDetails > summary").click()
            page.locator("#methodDetails details > summary").click()
            expect(page.locator("#sensitivityRows tr")).to_have_count(5)
            page.goto(f"{base}/app/state-clusters.html?k=999&state=Atlantis&group=99", wait_until="networkidle")
            expect(page.locator("#clusterCount")).to_have_value("4")
            expect(page.locator("#stateSelect")).to_have_value("Michigan")
            page.goto(f"{base}/app/state-clusters.html?k=4&state=Michigan&group=1.5", wait_until="networkidle")
            expect(page.locator("#clusterContent")).to_be_visible()
            expect(page.locator("#groupFilter")).to_have_value("all")
            print("PASS all five models, exact 50-state map colours, profiles, linked selection, filters, reload, history, sensitivity table and invalid URL recovery", flush=True)
            for width in [320, 390, 768]:
                mobile = browser.new_page(viewport={"width": width, "height": 900}, is_mobile=True, has_touch=True)
                mobile.on("pageerror", lambda error: errors.append(str(error)))
                mobile.goto(f"{base}/app/state-clusters.html?k=3&state=California", wait_until="networkidle")
                expect(mobile.locator("#clusterContent")).to_be_visible()
                assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                assert mobile.locator("#profileChart").evaluate("el => Number(el.getAttribute('viewBox').split(' ')[2]) <= el.clientWidth + 1")
                check_assignments(mobile, data, 3)
                mobile.locator("#clusterCount").select_option("5")
                check_assignments(mobile, data, 5)
                mobile.locator("#colorMode").select_option("party")
                check_assignments(mobile, data, 5)
                assert mobile.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                mobile.screenshot(path=str(screenshots / f"mobile-{width}.png"), full_page=True)
                if width == 320:
                    mobile.locator(".profiles").screenshot(path=str(screenshots / "mobile-chart.png"))
                mobile.close()
            # Entry points in the homepage and presidential explorer.
            page.goto(base, wait_until="networkidle")
            expect(page.locator('a[href="app/state-clusters.html"]')).to_be_visible()
            page.goto(f"{base}/app/?year=us-president-2024", wait_until="networkidle")
            expect(page.locator("#stateClusteringEntry")).to_be_visible()
            page.locator("#electionYear").select_option("nyc-mayor-2025")
            expect(page.locator("#stateClusteringEntry")).to_be_hidden()
            browser.close()
        assert not errors, errors
        print("PASS mobile layouts at 320/390/768px and homepage/explorer integration", flush=True)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
