#!/usr/bin/env python3
"""Check provisional Governor State/County views and unresolved local leaders."""
import csv
import re
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import expect,sync_playwright
from test_explorer_ux import QuietHandler

ROOT=Path(__file__).resolve().parents[1]
def read(name):
    with (ROOT/'data'/name).open() as handle:return list(csv.DictReader(handle))
def select(page,name):
    shape=page.locator(f'.district-shape[data-district="{name}"]')
    shape.focus();shape.press('Enter')
    expect(page.locator('#districtSummary h2')).to_have_text(name)
    return shape

def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT)))
    Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    expected={r['district'] for r in read('us_2026_governor_county_fpp.csv')}
    older_count=len({r['district'] for r in read('us_2022_governor_county_fpp.csv')})
    errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch()
            page=browser.new_page(viewport={'width':1440,'height':1000},has_touch=True)
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'{base}/app/?year=us-governor-2026',wait_until='networkidle')
            expect(page.locator('#electionHeading')).to_contain_text('Governor 2026 · Provisional')
            expect(page.locator('#electionSnapshotNotice')).to_contain_text('15 November 2026, 18:19 UTC')
            expect(page.locator('#electionSnapshotNotice')).to_contain_text('36 source-reported winners')
            expect(page.locator('.district-shape')).to_have_count(36)
            expect(page.locator('[data-geography="state"]')).to_have_attribute('aria-pressed','true')
            expect(page.locator('#houseViewControls')).to_be_hidden()
            expect(page.locator('#stateSummary')).to_contain_text('reported wins')
            select(page,'Alaska')
            expect(page.locator('#districtSummary')).to_contain_text('Reported winner · provisional')
            expect(page.locator('#districtSummary')).to_contain_text('Kreiss-Tomkins')
            select(page,'Texas')
            expect(page.locator('#districtSummary')).to_contain_text('Gina Hinojosa')
            page.get_by_text('Source and counting notes',exact=True).click()
            expect(page.locator('#districtSummary details p')).to_be_visible()
            page.get_by_text('Source and counting notes',exact=True).click()
            (ROOT/'tmp/explorer-ux').mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(ROOT/'tmp/explorer-ux/governor-2026-state.png'),full_page=True)
            page.locator('[data-geography="county"]').click()
            expect(page.locator('.district-shape')).to_have_count(2151)
            actual=set(page.locator('.district-shape').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.district)'))
            assert actual==expected,(actual-expected,expected-actual)
            expect(page.locator('#stateSummary')).to_contain_text('local leads')
            expect(page.locator('#stateSummary')).to_contain_text('Local leader unavailable')
            franklin=select(page,'Franklin County, Arkansas')
            expect(franklin).to_have_attribute('fill',re.compile('139.*144.*152'))
            expect(franklin.locator('title')).to_contain_text('Local leader unavailable')
            expect(page.locator('#mapLegend')).to_contain_text('Local leader unavailable')
            expect(page.locator('#districtSummary')).to_contain_text('Grouped Other votes prevent identifying a candidate leader')
            expect(page.locator('#districtSummary')).to_contain_text('Named-candidate margin')
            expect(page.locator('#districtSummary')).to_contain_text('1,476 (')
            expect(page.locator('#primaryBars')).to_contain_text('Other candidates (combined)')
            expect(page.locator('#primaryBars')).to_contain_text('2,354')
            ranking_names=page.locator('#rankingsPanel .ranking-row').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.district)')
            assert 'Franklin County, Arkansas' not in ranking_names
            select(page,'Capitol Planning Region, Connecticut')
            expect(page.locator('#districtSummary')).to_contain_text('Ned Lamont')
            assert len([name for name in actual if 'Planning Region, Connecticut' in name])==9
            select(page,'Alaska (statewide fallback)')
            expect(page.locator('#districtSummary')).to_contain_text('not county/borough')
            expect(page.locator('#districtSummary')).to_contain_text('Kreiss-Tomkins')
            page.reload(wait_until='networkidle')
            expect(page.locator('.district-shape')).to_have_count(2151)
            expect(page.locator('#districtSummary h2')).to_have_text('Alaska (statewide fallback)')
            page.screenshot(path=str(ROOT/'tmp/explorer-ux/governor-2026-county.png'),full_page=True)
            page.set_viewport_size({'width':320,'height':1050})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.locator('[data-geography="state"]').tap()
            expect(page.locator('.district-shape')).to_have_count(36)
            select(page,'Georgia')
            expect(page.locator('#districtSummary')).to_contain_text('Keisha Lance Bottoms')
            page.go_back(wait_until='networkidle')
            page.go_back(wait_until='networkidle')
            expect(page.locator('.district-shape')).to_have_count(2151)
            page.locator('#electionYear').select_option('us-governor-2022')
            expect(page.locator('.district-shape')).to_have_count(older_count)
            expect(page.locator('#electionSnapshotNotice')).to_be_hidden()
            page.locator('#electionYear').select_option('us-governor-2026')
            expect(page.locator('.district-shape')).to_have_count(2151)
            expect(page.locator('[data-geography="county"]')).to_have_attribute('aria-pressed','true')
            page.locator('#electionYear').select_option('us-senate-2026')
            expect(page.locator('.district-shape')).to_have_count(35)
            expect(page.locator('#houseViewControls')).to_be_visible()
            page.locator('#electionYear').select_option('us-governor-2026')
            expect(page.locator('.district-shape')).to_have_count(36)
            expect(page.locator('#houseViewControls')).to_be_hidden()
            browser.close()
        assert not errors,errors
        print('PASS: Governor 2026, 36 State races, all 2151 County areas, explicit calls, unknown local leader, grouped vote margins, Connecticut regions, Alaska fallback, source notes, mobile and year/history switching')
    finally:server.shutdown();server.server_close()
if __name__=='__main__':main()
