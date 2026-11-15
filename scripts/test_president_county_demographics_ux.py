#!/usr/bin/env python3
"""County presidential chart, source correlations, aliases and geography switching."""
import argparse
import re
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright
from test_explorer_ux import QuietHandler
from build_us_president_demographics import ROOT, read_csv
from build_us_house_analysis import pearson, average_ranks


def check(browser, base, screenshots):
    page = browser.new_page(viewport={'width':1440, 'height':1100}, has_touch=True)
    page.goto(base + '/app/?year=us-president-2024&geo=county&view=demographics&mode=house-swing&demographicY=fit', wait_until='networkidle')
    expect(page.locator('.house-scatter-point')).to_have_count(3104)
    expect(page.locator('#houseDemographicComparisonNote')).to_contain_text('2020–2024 ACS five-year')
    demo = {r['constituency_code']: r for r in read_csv(ROOT / 'data/us_2024_county_demographics.csv')}
    for period in ('2020-2024','2016-2020','2012-2016','2008-2012'):
        page.locator('#houseDemographicPeriod').select_option(period)
        start, end = period.split('-')
        expect(page.locator('#electionYear')).to_have_value('us-president-' + end)
        expect(page.locator('[data-geography="county"]')).to_have_attribute('aria-pressed','true')
        expect(page.locator('.house-scatter-point')).to_have_count(3104)
        rows = read_csv(ROOT / ('data/us_president_county_' + period.replace('-','_') + '_comparison.csv'))
        eligible = [r for r in rows if r['comparison_eligible'] == 'true']
        self_flips = {r['district'] for r in eligible if r['seat_flipped'] == 'true'}
        assert set(page.locator('.house-seat-flipped').evaluate_all('els => els.map(e=>e.dataset.district)')) == self_flips
        expect(page.locator('[data-statistic="flipped-states"]')).to_have_text(str(len(self_flips)))
        colors = page.locator('.district-shape').evaluate_all("els=>Object.fromEntries(els.map(e=>[e.dataset.district,e.getAttribute('fill')]))")
        for row in rows:
            if not row[f'district_{end}']: continue
            delta = float(row['democratic_share_change_pp']) if row['democratic_share_change_pp'] else None
            expected = '#8b9098' if delta is None else '#f1efeb' if abs(delta)<.5 else ('#2166ac' if delta>=5 else '#9ecae1') if delta>0 else ('#b51f24' if delta<=-5 else '#efaaa3')
            assert colors[row['district']] == expected
        for outcome in (start+'-matched',end+'-matched','change'):
            page.locator('#houseDemographicOutcome').select_option(outcome)
            for party in ('democratic','republican'):
                page.locator('#houseDemographicParty').select_option(party)
                labels = page.locator('.house-scatter-point').evaluate_all("els=>Object.fromEntries(els.map(e=>[e.dataset.district,e.getAttribute('aria-label')]))")
                x,y=[],[]
                for row in eligible:
                    value = float(row['democratic_share_change_pp' if outcome=='change' else 'democratic_two_party_share_pct_'+outcome[:4]])
                    if party=='republican': value=-value if outcome=='change' else 100-value
                    displayed = re.search(r'\((?:%|pp)\): ([+-]?[0-9.]+)', labels[row['district']])
                    assert displayed and abs(float(displayed[1])-value) <= .050001, (period,outcome,party,row['district'],value,labels[row['district']])
                    x.append(float(demo[row['demographic_constituency_code']]['bachelors_plus_pct']));y.append(value)
                expect(page.locator('[data-statistic="pearson"]')).to_have_text(f'{pearson(x,y):.3f}')
                expect(page.locator('[data-statistic="spearman"]')).to_have_text(f'{pearson(average_ranks(x),average_ranks(y)):.3f}')
        page.reload(wait_until='networkidle')
        expect(page.locator('.house-scatter-point')).to_have_count(3104)
        expect(page.locator('#houseDemographicPeriod')).to_have_value(period)
        expect(page.locator('#houseComparisonDownload')).to_have_attribute('href','../data/us_president_county_'+period.replace('-','_')+'_comparison.csv')
    print('PASS: 4 county comparisons, 3104 areas, all 24 vote/party combinations, correlations, map colours, flips and reload',flush=True)
    page.locator('#houseDemographicDistrict').select_option('Fairfield County, Connecticut')
    expect(page.locator('#houseDemographicSelectedNote')).to_contain_text('Connecticut')
    expect(page.locator('#houseDemographicSelectedValues')).to_contain_text('Not published')
    page.locator('#houseDemographicPeriod').select_option('2016-2020')
    page.locator('#electionYear').select_option('us-president-2016')
    expect(page.locator('.house-scatter-point')).to_have_count(3104)
    page.locator('#houseDemographicDistrict').select_option('Shannon County, South Dakota')
    expect(page.locator('#houseDemographicSelectedValues')).to_contain_text('2016:')
    expect(page.locator('#houseDemographicSelectedNote')).not_to_contain_text('Not plotted')
    page.locator('#houseDemographicPeriod').select_option('2020-2024')
    page.locator('#electionYear').select_option('us-president-2020')
    expect(page.locator('.house-scatter-point')).to_have_count(3104)
    page.locator('#houseDemographicDistrict').select_option('Fairfield County, Connecticut')
    expect(page.locator('#houseDemographicSelectedNote')).to_contain_text('Connecticut')
    page.locator('#electionYear').select_option('us-president-2024')
    page.locator('#houseDemographicDistrict').select_option('Alaska statewide')
    expect(page.locator('#houseDemographicSelectedNote')).to_contain_text('reported statewide')
    page.locator('#houseDemographicDistrict').select_option('Maricopa County, Arizona')
    expect(page.locator('#houseDemographicFlip')).to_contain_text('Flipped to Republican')
    page.locator('#houseDemographicParty').select_option('democratic')
    page.locator('#houseDemographicXRange').select_option('fit')
    if screenshots:
        page.locator('#explorerGrid').screenshot(path=str(screenshots/'county-desktop.png'))
    page.set_viewport_size({'width':390,'height':1100})
    page.wait_for_function("()=>Math.abs(document.querySelector('#houseDemographicChart svg').viewBox.baseVal.width-document.querySelector('#houseDemographicChart').clientWidth)<2")
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    page.locator('#houseDemographicDistrict').select_option('Los Angeles County, California')
    if screenshots:
        page.screenshot(path=str(screenshots/'county-mobile.png'),full_page=True)
    page.locator('[data-geography="state"]').click()
    expect(page.locator('.house-scatter-point')).to_have_count(51)
    page.go_back(wait_until='networkidle')
    expect(page.locator('[data-geography="county"]')).to_have_attribute('aria-pressed','true')
    expect(page.locator('.house-scatter-point')).to_have_count(3104)
    page.locator('#electionYear').select_option('us-house-2024')
    expect(page.locator('.house-scatter-point')).to_have_count(312)
    page.go_back(wait_until='networkidle')
    expect(page.locator('.house-scatter-point')).to_have_count(3104)
    page.close()
    print('PASS: historical aliases, both CT geographies, Alaska exclusion, selection, mobile, state/House switching and history',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--screenshots',type=Path);args=parser.parse_args()
    if args.screenshots:args.screenshots.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT)))
    Thread(target=server.serve_forever,daemon=True).start();errors=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch();browser.on('page',lambda page:page.on('pageerror',lambda error:errors.append(str(error))))
            check(browser,f'http://127.0.0.1:{server.server_port}',args.screenshots);browser.close()
        assert not errors,errors
        print('County presidential browser checks passed; no runtime errors.',flush=True)
    finally:server.shutdown();server.server_close()


if __name__=='__main__':main()
