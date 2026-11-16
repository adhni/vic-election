#!/usr/bin/env python3
"""Audit automatic previous-election Governor comparisons and linked chart/map."""
import re
from functools import partial
from http.server import ThreadingHTTPServer
from threading import Thread
from playwright.sync_api import expect, sync_playwright
from test_explorer_ux import QuietHandler
from test_senate_swing_ux import ROOT, read, swing_color


def check_historical(page, base):
    for scope in ('state','county'):
        page.goto(f'{base}?year=us-governor-2024&geo={scope}&view=demographics&mode=house-swing',wait_until='networkidle')
        demo={r['constituency_code']:r for r in read(f'us_2024_{scope}_demographics.csv')}
        # Switch within the same family to exercise cached data and per-year options.
        for year in (2024,2022,2020,2018,2024):
            page.locator('#electionYear').select_option(f'us-governor-{year}')
            rows=read(f'us_governor_{scope}_{year}_previous_comparison.csv')
            expected={r[f'district_{year}'] for r in rows if r['comparison_eligible']=='true' and demo.get(r['demographic_constituency_code'],{}).get('bachelors_plus_pct','')!=''}
            points=page.locator('.house-scatter-point')
            expect(points).to_have_count(len(expected))
            expect(page.locator('#houseDemographicPeriod')).to_have_value(f'previous-{year}')
            expect(page.locator('#houseComparisonDownload')).to_have_attribute('href',f'../data/us_governor_{scope}_{year}_previous_comparison.csv')
            assert set(points.evaluate_all('(ns)=>ns.map(n=>n.dataset.district)'))==expected
            page.locator('#mapModeSelect').select_option('house-swing')
            colours=page.locator('.district-shape').evaluate_all('(ns)=>Object.fromEntries(ns.map(n=>[n.dataset.district,n.getAttribute("fill")]))')
            assert set(colours)=={r[f'district_{year}'] for r in rows}
            for row in rows:assert colours[row[f'district_{year}']]==swing_color(row),(year,scope,row['district'])
            flips={r[f'district_{year}'] for r in rows if r['seat_flipped']=='true' and r[f'district_{year}'] in expected}
            assert set(page.locator('.house-scatter-point.house-seat-flipped').evaluate_all('(ns)=>ns.map(n=>n.dataset.district)'))==flips
            examples=[next(r for r in rows if r['state']=='Vermont' and r[f'district_{year}'] in expected)]
            four_year=next((r for r in rows if r['state'] not in {'New Hampshire','Vermont'} and r[f'district_{year}'] in expected),None)
            if four_year:examples.append(four_year)
            for row in examples:
                page.locator('#houseDemographicDistrict').select_option(row[f'district_{year}'])
                expect(page.locator('#houseDemographicSelectedValues')).to_contain_text(f"{row['baseline_year']}:")
                expect(page.locator('#houseDemographicSelectedValues')).to_contain_text(f'{year}:')
                expect(page.locator('#houseDemographicSelectedNote')).to_contain_text(f"{row['baseline_year']} → {year}")
            for outcome in ('previous-matched',f'{year}-matched','change'):
                page.locator('#houseDemographicOutcome').select_option(outcome)
                expect(points).to_have_count(len(expected))
            correlation=page.locator('[data-statistic="pearson"]').inner_text()
            page.locator('#houseDemographicParty').select_option('republican')
            if len(expected)<3:
                expect(page.locator('[data-statistic="pearson"]')).to_have_text('Unavailable')
            else:
                assert abs(float(correlation)+float(page.locator('[data-statistic="pearson"]').inner_text()))<.0001
            page.locator('#houseDemographicParty').select_option('democratic')
            strict={r[f'district_{year}'] for r in rows if r['comparison_sensitivity_eligible']=='true' and r[f'district_{year}'] in expected}
            page.locator('#houseDemographicSample').select_option('sensitivity')
            expect(points).to_have_count(len(strict))
            page.locator('#houseDemographicSample').select_option('baseline')
            if year==2018:
                excluded=next(r for r in rows if r['state']=='California')
                page.locator('#houseDemographicDistrict').select_option(excluded[f'district_{year}'])
                expect(page.locator('#houseDemographicSelectedNote')).to_contain_text('2014')
                expect(page.locator('#houseDemographicSelectedNote')).to_contain_text('starts in 2016')
                expect(page.locator('#houseDemographicComparisonNote')).to_contain_text('Only New Hampshire and Vermont')
            assert 'Provisional: 15 November 2026' not in page.locator('#houseDemographicComparisonNote').inner_text()
            page.reload(wait_until='networkidle')
            expect(points).to_have_count(len(expected))
            page.set_viewport_size({'width':320,'height':1050})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.set_viewport_size({'width':1440,'height':1050})
            print(f'PASS: Governor {year} {scope}: {len(expected)} chart areas, all colours/flips, mixed baselines, matched outcomes, party, strict sample, reload and mobile',flush=True)
    page.locator('#electionYear').select_option('us-governor-2016')
    expect(page.locator('#houseViewControls')).to_be_hidden()
    expect(page.locator('#houseDemographicsPanel')).to_be_hidden()
    page.locator('#electionYear').select_option('us-governor-2024')
    page.locator('#houseDemographicsView').click()
    expect(page.locator('.house-scatter-point')).to_have_count(518)
    page.go_back(wait_until='networkidle')
    expect(page.locator('#electionYear')).to_have_value('us-governor-2016')
    expect(page.locator('#houseViewControls')).to_be_hidden()
    page.go_forward(wait_until='networkidle')
    expect(page.locator('#houseDemographicPeriod')).to_have_value('previous-2024')
    expect(page.locator('.house-scatter-point')).to_have_count(518)


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
    Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}/app/'
    errors = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={'width': 1440, 'height': 1050})
            page.on('pageerror', lambda error: errors.append(str(error)))
            for scope in ('state', 'county'):
                rows = read(f'us_governor_{scope}_2026_previous_comparison.csv')
                demo = {r['constituency_code']: r for r in read(f'us_2024_{scope}_demographics.csv')}
                page.goto(f'{base}?year=us-governor-2026&geo={scope}&view=demographics&mode=house-swing', wait_until='networkidle')
                expected = {r['district_2026'] for r in rows if r['comparison_eligible'] == 'true' and demo.get(r['demographic_constituency_code'], {}).get('bachelors_plus_pct', '') != ''}
                points = page.locator('.house-scatter-point')
                expect(points).to_have_count(len(expected))
                assert set(points.evaluate_all('(ns)=>ns.map(n=>n.dataset.district)')) == expected
                expect(page.locator('#houseDemographicPeriod')).to_have_value('previous-2026')
                expect(page.locator('#houseDemographicPeriod').locator('..')).to_be_hidden()
                expect(page.locator('#houseDemographicOutcome option[value="change"]')).to_have_text('Swing since previous election')
                expect(page.locator('#houseComparisonDownload')).to_have_attribute('href', f'../data/us_governor_{scope}_2026_previous_comparison.csv')
                flips = {r['district_2026'] for r in rows if r['seat_flipped'] == 'true' and r['district_2026'] in expected}
                assert set(page.locator('.house-scatter-point.house-seat-flipped').evaluate_all('(ns)=>ns.map(n=>n.dataset.district)')) == flips
                colours = page.locator('.district-shape').evaluate_all('(ns)=>Object.fromEntries(ns.map(n=>[n.dataset.district,n.getAttribute("fill")]))')
                assert set(colours) == {r['district_2026'] for r in rows}
                for row in rows:
                    assert colours[row['district_2026']] == swing_color(row), row['district']
                for state, year in [('Vermont', 2024), ('New Hampshire', 2024), ('Texas', 2022), ('Maine', 2022)]:
                    row = next(r for r in rows if r['state'] == state and r['district_2026'] in expected)
                    district = row['district_2026']
                    page.locator('#houseDemographicDistrict').select_option(district)
                    expect(page.locator('#houseDemographicSelectedValues')).to_contain_text(f'{year}:')
                    expect(page.locator('#houseDemographicSelectedValues')).to_contain_text('2026:')
                    expect(page.locator('#houseDemographicSelectedNote')).to_contain_text(f'{year} → 2026')
                    dot = page.locator('.house-scatter-point[aria-pressed="true"]')
                    expect(dot).to_have_attribute('aria-label', re.compile(f'{year} → 2026'))
                    page.locator('#houseDemographicOutcome').select_option('previous-matched')
                    expect(points).to_have_count(len(expected))
                    expect(page.locator('#houseDemographicSelectedValues')).to_contain_text(f"{float(row[f'democratic_two_party_share_pct_{year}']):.1f}%")
                for outcome in ('previous-matched', '2026-matched', 'change'):
                    page.locator('#houseDemographicOutcome').select_option(outcome)
                    expect(points).to_have_count(len(expected))
                correlation = float(page.locator('[data-statistic="pearson"]').inner_text())
                page.locator('#houseDemographicParty').select_option('republican')
                assert abs(correlation + float(page.locator('[data-statistic="pearson"]').inner_text())) < .0001
                assert colours == page.locator('.district-shape').evaluate_all('(ns)=>Object.fromEntries(ns.map(n=>[n.dataset.district,n.getAttribute("fill")]))')
                strict = {r['district_2026'] for r in rows if r['comparison_sensitivity_eligible'] == 'true' and r['district_2026'] in expected}
                page.locator('#houseDemographicSample').select_option('sensitivity')
                expect(points).to_have_count(len(strict))
                page.locator('#houseDemographicSample').select_option('baseline')
                for row in rows:
                    if row['comparison_eligible'] == 'true': continue
                    page.locator('#houseDemographicDistrict').select_option(row['district_2026'])
                    expect(page.locator('#houseDemographicSelectedNote')).to_contain_text('Not compared:')
                    expect(page.locator('.house-scatter-point[aria-pressed="true"]')).to_have_count(0)
                page.locator('#houseDemographicXRange').select_option('fit')
                page.locator('#houseDemographicYRange').select_option('fit')
                page.reload(wait_until='networkidle')
                expect(points).to_have_count(len(expected))
                page.set_viewport_size({'width': 320, 'height': 1050})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                page.set_viewport_size({'width': 1440, 'height': 1050})
                print(f'PASS: Governor {scope}: {len(expected)} matched areas, {len(strict)} strict; all colours/flips, actual baseline years, exclusions, outcomes, party, axes and mobile', flush=True)
            check_historical(page, base)
            page.locator('#electionYear').select_option('us-senate-2026')
            expect(page.locator('#houseDemographicPeriod')).to_have_value('2020-2026')
            expect(page.locator('#houseDemographicPeriod').locator('..')).to_be_visible()
            page.locator('#electionYear').select_option('us-president-2024')
            expect(page.locator('#houseDemographicPeriod')).to_have_value('2020-2024')
            page.locator('#electionYear').select_option('us-house-2024')
            expect(page.locator('#houseDemographicPeriod')).to_have_value('2022-2024')
            page.locator('#electionYear').select_option('us-governor-2026')
            page.locator('[data-geography="state"]').click()
            expect(page.locator('.house-scatter-point')).to_have_count(34)
            page.locator('#houseDemographicDistrict').select_option('Vermont')
            expect(page.locator('#houseDemographicSelectedValues')).to_contain_text('2024:')
            (ROOT / 'tmp/explorer-ux').mkdir(parents=True, exist_ok=True)
            page.locator('#mapModeSelect').select_option('house-swing')
            page.screenshot(path=str(ROOT / 'tmp/explorer-ux/governor-previous-election-swing.png'), full_page=True)
            browser.close()
        assert not errors, errors
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__': main()
