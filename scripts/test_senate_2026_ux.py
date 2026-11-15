#!/usr/bin/env python3
"""Check provisional Senate state/county navigation and grouped vote semantics."""
import csv
import re
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import expect, sync_playwright
from test_explorer_ux import QuietHandler

ROOT=Path(__file__).resolve().parents[1]

def select_shape(page, name):
    shape=page.locator(f'.district-shape[data-district="{name}"]')
    shape.focus()
    shape.press('Enter')
    expect(page.locator('#districtSummary h2')).to_have_text(name)
    return shape


def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT)))
    Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    with (ROOT/'data/us_2026_senate_county_fpp.csv').open() as handle: rows=list(csv.DictReader(handle))
    expected={r['district'] for r in rows}
    errors=[]
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch()
            page=browser.new_page(viewport={'width':1440,'height':1000},has_touch=True)
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'{base}/app/?year=us-senate-2026',wait_until='networkidle')
            expect(page.locator('#electionHeading')).to_contain_text('Senate 2026 · Provisional')
            expect(page.locator('#electionSnapshotNotice')).to_contain_text('34 reported winners')
            expect(page.locator('#electionSnapshotNotice')).to_contain_text('not the full 100-seat Senate')
            expect(page.locator('[data-geography="state"]')).to_have_attribute('aria-pressed','true')
            expect(page.locator('.district-shape')).to_have_count(35)
            expect(page.locator('#houseViewControls')).to_be_hidden()
            expect(page.locator('#stateSummary')).to_contain_text('reported wins')
            expect(page.locator('#stateSummary')).to_contain_text('uncalled')
            alaska=select_shape(page,'Alaska')
            expect(page.locator('#districtSummary')).to_contain_text('Current leader · not called')
            expect(page.locator('#districtSummary')).to_contain_text('Mary Peltola')
            expect(alaska).to_have_attribute('fill',re.compile('139.*144.*152'))
            expect(page.locator('#mapLegend')).to_contain_text('Not called')
            for state,winner in [('Ohio','Sherrod Brown'),('Florida','Ashley Moody')]:
                select_shape(page,state)
                expect(page.locator('#districtSummary')).to_contain_text('Special election')
                expect(page.locator('#districtSummary')).to_contain_text('Reported winner · provisional')
                expect(page.locator('#districtSummary')).to_contain_text(winner)
            (ROOT/'tmp/explorer-ux').mkdir(parents=True,exist_ok=True)
            page.get_by_text('Source and counting notes',exact=True).click()
            expect(page.locator('#districtSummary details')).to_have_attribute('open','')
            expect(page.locator('#districtSummary details p')).to_be_visible()
            page.get_by_text('Source and counting notes',exact=True).click()
            page.screenshot(path=str(ROOT/'tmp/explorer-ux/senate-2026-state.png'),full_page=True)
            page.locator('[data-geography="county"]').click()
            expect(page.locator('.district-shape')).to_have_count(2443)
            actual=set(page.locator('.district-shape').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.district)'))
            assert actual==expected,(actual-expected,expected-actual)
            expect(page.locator('#stateSummary')).to_contain_text('local leads')
            expect(page.locator('#mapLegend')).to_contain_text('Independent leader')
            shape=select_shape(page,'Alaska (statewide fallback)')
            expect(shape).to_have_attribute('fill',re.compile('139.*144.*152'))
            expect(page.locator('#districtSummary')).to_contain_text('not county/borough')
            expect(page.locator('#districtSummary')).to_contain_text('276,513')
            select_shape(page,'Providence County, Rhode Island')
            expect(page.locator('#districtSummary')).to_contain_text('778 additional statewide votes')
            select_shape(page,'Roosevelt County, Montana')
            # Other's 731 combined votes exceed Bodnar's 704, but are not a
            # single runner-up. Margin is 1,116 - 704 = 412, not 385.
            expect(page.locator('#districtSummary')).to_contain_text('Named-candidate margin')
            expect(page.locator('#districtSummary')).to_contain_text('412 (')
            expect(page.locator('#districtSummary')).to_contain_text('Seth Bodnar')
            expect(page.locator('#districtSummary')).to_contain_text('Current local vote leader')
            expect(page.locator('#districtSummary')).not_to_contain_text('Reported winner')
            expect(page.locator('#primaryBars')).to_contain_text('Other candidates (combined)')
            select_shape(page,'Grant County, Nebraska')
            expect(page.locator('#districtSummary')).to_contain_text('241 (')
            expect(page.locator('#districtSummary')).to_contain_text('Dan Osborn')
            # Find a source county actually led by an independent.
            by_name={}
            for row in rows:by_name.setdefault(row['district'],[]).append(row)
            independent=next(name for name,group in by_name.items() if max(group,key=lambda r:int(r['votes']))['candidate_party']=='Independent')
            select_shape(page,independent)
            expect(page.locator('#districtSummary')).to_contain_text('Independent')
            assert 'geo=county' in page.url
            page.reload(wait_until='networkidle')
            expect(page.locator('.district-shape')).to_have_count(2443)
            expect(page.locator('#districtSummary h2')).to_have_text(independent)
            page.screenshot(path=str(ROOT/'tmp/explorer-ux/senate-2026-county.png'),full_page=True)
            page.set_viewport_size({'width':320,'height':1050})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            page.locator('[data-geography="state"]').tap()
            expect(page.locator('.district-shape')).to_have_count(35)
            select_shape(page,'Texas')
            expect(page.locator('#districtSummary')).to_contain_text('James Talarico')
            page.go_back(wait_until='networkidle')
            expect(page.locator('.district-shape')).to_have_count(35)
            page.go_back(wait_until='networkidle')
            expect(page.locator('.district-shape')).to_have_count(2443)
            page.locator('#electionYear').select_option('us-senate-2024')
            expect(page.locator('#electionSnapshotNotice')).to_be_hidden()
            expect(page.locator('.district-shape')).to_have_count(1875)
            page.locator('#electionYear').select_option('us-senate-2026')
            expect(page.locator('.district-shape')).to_have_count(35)
            browser.close()
        assert not errors,errors
        print('PASS: Senate 2026, 35 races/2443 county areas, special seats, uncalled Alaska, independent labels, grouped Other margins, residuals, mobile, history and older Senate switching')
    finally:
        server.shutdown();server.server_close()

if __name__=='__main__':main()
