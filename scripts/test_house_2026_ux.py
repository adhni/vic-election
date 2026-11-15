#!/usr/bin/env python3
"""Browser audit of provisional results, geography exclusions and chart controls."""
import csv
import re
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import expect, sync_playwright
from test_explorer_ux import QuietHandler

ROOT=Path(__file__).resolve().parents[1]

def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT)))
    Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    with (ROOT/'data/us_house_2024_2026_comparison.csv').open() as handle: comparisons=list(csv.DictReader(handle))
    expected={r['district'] for r in comparisons if r['comparison_eligible']=='true'}
    flipped={r['district'] for r in comparisons if r['comparison_eligible']=='true' and r['seat_flipped']=='true'}
    errors=[]
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch()
            page=browser.new_page(viewport={'width':1440,'height':1050})
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'{base}/app/?year=us-house-2026&view=demographics&mode=house-swing',wait_until='networkidle')
            expect(page.locator('#electionHeading')).to_contain_text('2026 · Provisional')
            expect(page.locator('#electionSnapshotNotice')).to_be_visible()
            expect(page.locator('#electionSnapshotNotice')).to_contain_text('14 November 2026')
            expect(page.locator('#houseDemographicPeriod')).to_have_value('2024-2026')
            expect(page.locator('#houseDemographicOutcome')).to_have_value('change')
            expect(page.locator('.house-scatter-point')).to_have_count(236)
            expect(page.locator('.district-shape')).to_have_count(435)
            expect(page.locator('#houseDemographicComparisonNote')).to_contain_text('Provisional')
            actual=set(page.locator('.house-scatter-point').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.district)'))
            assert actual==expected, (actual-expected,expected-actual)
            actual_flips=set(page.locator('.house-scatter-point.house-seat-flipped').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.district)'))
            assert actual_flips==flipped, (actual_flips,flipped)
            pearson=page.locator('[data-statistic="pearson"]').inner_text()
            page.locator('#houseDemographicParty').select_option('republican')
            assert abs(float(pearson)+float(page.locator('[data-statistic="pearson"]').inner_text()))<.0001
            page.locator('#houseDemographicOutcome').select_option('2026-matched')
            expect(page.locator('.house-scatter-point')).to_have_count(236)
            page.locator('#houseDemographicDistrict').select_option('Arizona 1st')
            expect(page.locator('#houseDemographicSelectedNote')).to_contain_text('Amish Shah')
            expect(page.locator('#houseDemographicSelectedNote')).to_contain_text('provisional')
            expect(page.locator('#houseDemographicFlip')).to_be_visible()
            page.locator('#houseDemographicDistrict').select_option('California 17th')
            expect(page.locator('#houseDemographicSelectedValues')).to_contain_text('Not published')
            expect(page.locator('#houseDemographicSelectedNote')).to_contain_text('plan changed')
            expect(page.locator('#houseDemographicFlip')).to_be_hidden()
            page.locator('#houseDemographicDistrict').select_option('Colorado 4th')
            expect(page.locator('#houseDemographicSelectedNote')).to_contain_text('not called')
            expect(page.locator('#houseDemographicFlip')).to_be_hidden()
            page.locator('#houseResultsView').click()
            expect(page.locator('#districtSummary')).to_contain_text('Current leader · not called')
            expect(page.locator('#districtSummary')).not_to_contain_text('MP elected')
            shape=page.locator('.district-shape[data-district="Colorado 4th"]')
            expect(shape).to_have_attribute('fill',re.compile('139.*144.*152'))
            expect(shape.locator('title')).to_contain_text('Not called')
            expect(page.locator('#stateSummary')).to_contain_text('Not called')
            ranked_seats=set(page.locator('#rankingsPanel .ranking-row').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.district)'))
            assert not ranked_seats & {r['district'] for r in comparisons if r['result_called_2026']=='false'}
            page.locator('#houseDemographicsView').click()
            page.locator('#houseDemographicDistrict').select_option('Florida 10th')
            page.locator('#houseResultsView').click()
            expect(page.locator('#districtSummary')).to_contain_text('Not published')
            expect(page.locator('#districtSummary')).to_contain_text('Frost')
            page.locator('#houseDemographicsView').click()
            page.locator('#houseDemographicXRange').select_option('fit')
            page.locator('#houseDemographicYRange').select_option('fit')
            page.reload(wait_until='networkidle')
            expect(page.locator('.house-scatter-point')).to_have_count(236)
            expect(page.locator('#houseDemographicOutcome')).to_have_value('2026-matched')
            expect(page.locator('#houseDemographicParty')).to_have_value('republican')
            expect(page.locator('#houseDemographicXRange')).to_have_value('fit')
            (ROOT/'tmp/explorer-ux').mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(ROOT/'tmp/explorer-ux/house-2026-desktop.png'),full_page=True)
            page.set_viewport_size({'width':320,'height':1000})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            page.locator('#houseDemographicPeriod').select_option('2022-2024')
            expect(page.locator('#electionYear')).to_have_value('us-house-2024')
            expect(page.locator('.house-scatter-point')).to_have_count(312)
            expect(page.locator('#electionSnapshotNotice')).to_be_hidden()
            page.locator('#houseDemographicPeriod').select_option('2024-2026')
            expect(page.locator('#electionYear')).to_have_value('us-house-2026')
            expect(page.locator('.house-scatter-point')).to_have_count(236)
            page.go_back(wait_until='networkidle')
            expect(page.locator('#electionYear')).to_have_value('us-house-2024')
            expect(page.locator('.house-scatter-point')).to_have_count(312)
            browser.close()
        assert not errors,errors
        print('PASS: House 2026 snapshot, all 236 chart seats and flips, uncalled results, changed maps, party/axes, mobile, periods and history')
    finally:
        server.shutdown();server.server_close()

if __name__=='__main__':main()
