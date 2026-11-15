#!/usr/bin/env python3
"""Audit all six-year Senate swing scopes, chart samples and navigation."""
import csv
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import expect,sync_playwright
from test_explorer_ux import QuietHandler

ROOT=Path(__file__).resolve().parents[1]
PERIODS=((2016,2022),(2018,2024),(2020,2026))
def read(name):
    with (ROOT/'data'/name).open() as handle:return list(csv.DictReader(handle))
def swing_color(row):
    if row['comparison_eligible']!='true':return '#8b9098'
    delta=float(row['democratic_share_change_pp'])
    return '#f1efeb' if abs(delta)<.5 else ('#2166ac' if delta>=5 else '#9ecae1') if delta>0 else '#b51f24' if delta<=-5 else '#efaaa3'

def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT)))
    Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}'
    errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch()
            page=browser.new_page(viewport={'width':1440,'height':1050})
            page.on('pageerror',lambda error:errors.append(str(error)))
            for scope in ('state','county'):
                demo={r['constituency_code']:r for r in read(f'us_2024_{scope}_demographics.csv')}
                for start,end in PERIODS:
                    comparisons=read(f'us_senate_{scope}_{start}_{end}_comparison.csv')
                    url=f'{base}/app/?year=us-senate-{end}&geo={scope}&view=demographics&mode=house-swing&demographicOutcome=change'
                    page.goto(url,wait_until='networkidle')
                    expect(page.locator('#houseDemographicPeriod')).to_have_value(f'{start}-{end}')
                    expected={r[f'district_{end}'] for r in comparisons if r['comparison_eligible']=='true' and demo.get(r['demographic_constituency_code'],{}).get('bachelors_plus_pct','')!=''}
                    expect(page.locator('.house-scatter-point')).to_have_count(len(expected))
                    actual=set(page.locator('.house-scatter-point').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.district)'))
                    assert actual==expected,(scope,start,actual^expected)
                    flipped={r[f'district_{end}'] for r in comparisons if r['seat_flipped']=='true' and r[f'district_{end}'] in expected}
                    actual_flips=set(page.locator('.house-scatter-point.house-seat-flipped').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.district)'))
                    assert actual_flips==flipped
                    colours=page.locator('.district-shape').evaluate_all('(nodes)=>Object.fromEntries(nodes.map(n=>[n.dataset.district,n.getAttribute("fill")]))')
                    for row in comparisons:
                        if row[f'district_{end}'] in colours:assert colours[row[f'district_{end}']]==swing_color(row),(scope,row['district'],colours[row[f'district_{end}']],swing_color(row))
                    expect(page.locator('#houseComparisonDownload')).to_have_attribute('href',f'../data/us_senate_{scope}_{start}_{end}_comparison.csv')
                    expect(page.locator('#houseDemographicComparisonNote')).to_contain_text('six years apart')
                    # Both shares and change use the same matched sample. Republican
                    # change reverses the sign of the correlation, not map colours.
                    for outcome in (f'{start}-matched',f'{end}-matched','change'):
                        page.locator('#houseDemographicOutcome').select_option(outcome)
                        expect(page.locator('.house-scatter-point')).to_have_count(len(expected))
                    correlation=float(page.locator('[data-statistic="pearson"]').inner_text())
                    page.locator('#houseDemographicParty').select_option('republican')
                    assert abs(correlation+float(page.locator('[data-statistic="pearson"]').inner_text()))<.0001
                    expect(page.locator('.house-scatter-point')).to_have_count(len(expected))
                    stricter={r[f'district_{end}'] for r in comparisons if r['comparison_sensitivity_eligible']=='true' and demo.get(r['demographic_constituency_code'],{}).get('bachelors_plus_pct','')!=''}
                    page.locator('#houseDemographicSample').select_option('sensitivity')
                    expect(page.locator('.house-scatter-point')).to_have_count(len(stricter))
                    page.locator('#houseDemographicSample').select_option('baseline')
                    # The start-year map keeps this same Senate-class comparison.
                    page.locator('#electionYear').select_option(f'us-senate-{start}')
                    expect(page.locator(f'[data-geography="{scope}"]')).to_have_attribute('aria-pressed','true')
                    expect(page.locator('#houseDemographicPeriod')).to_have_value(f'{start}-{end}')
                    expect(page.locator('.house-scatter-point')).to_have_count(len(expected))
                    print(f'PASS: {scope} {start}–{end}, {len(expected)} chart areas, all map colours, flips, matched outcomes and Republican inversion',flush=True)
            page.goto(f'{base}/app/?year=us-senate-2026&geo=state&view=demographics&mode=house-swing',wait_until='networkidle')
            expect(page.locator('.house-scatter-point')).to_have_count(27)
            for state,text in [('Florida','special election'),('Ohio','special election'),('Alaska','not called')]:
                page.locator('#houseDemographicDistrict').select_option(state)
                expect(page.locator('#houseDemographicSelectedNote')).to_contain_text(text)
                expect(page.locator('.house-scatter-point[aria-pressed="true"]')).to_have_count(0)
            page.locator('#houseDemographicDistrict').select_option('North Carolina')
            expect(page.locator('#houseDemographicFlip')).to_be_visible()
            expect(page.locator('#houseDemographicSelectedValues')).to_contain_text('2020:')
            expect(page.locator('#houseDemographicSelectedValues')).to_contain_text('2026:')
            page.locator('#houseDemographicXRange').select_option('fit')
            page.locator('#houseDemographicYRange').select_option('fit')
            (ROOT/'tmp/explorer-ux').mkdir(parents=True,exist_ok=True)
            page.screenshot(path=str(ROOT/'tmp/explorer-ux/senate-six-year-swing.png'),full_page=True)
            page.locator('[data-geography="county"]').click()
            expect(page.locator('.house-scatter-point')).to_have_count(1933)
            page.locator('#houseDemographicPeriod').select_option('2018-2024')
            expect(page.locator('#electionYear')).to_have_value('us-senate-2024')
            expect(page.locator('[data-geography="county"]')).to_have_attribute('aria-pressed','true')
            expect(page.locator('.house-scatter-point')).to_have_count(1630)
            page.locator('#houseDemographicPeriod').select_option('2016-2022')
            expect(page.locator('.house-scatter-point')).to_have_count(1894)
            page.reload(wait_until='networkidle')
            expect(page.locator('.house-scatter-point')).to_have_count(1894)
            page.set_viewport_size({'width':320,'height':1050})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.locator('#electionYear').select_option('us-president-2024')
            expect(page.locator('#houseDemographicPeriod')).to_have_value('2020-2024')
            page.locator('#electionYear').select_option('us-house-2024')
            expect(page.locator('#houseDemographicPeriod')).to_have_value('2022-2024')
            page.locator('#electionYear').select_option('us-senate-2026')
            expect(page.locator('.house-scatter-point')).to_have_count(27)
            page.go_back(wait_until='networkidle')
            expect(page.locator('#houseDemographicPeriod')).to_have_value('2022-2024')
            browser.close()
        assert not errors,errors
        print('PASS: special/uncalled exclusions, same-seat flips, fixed axes, period switching, county scope, reload, mobile and cross-family history')
    finally:server.shutdown();server.server_close()
if __name__=='__main__':main()
