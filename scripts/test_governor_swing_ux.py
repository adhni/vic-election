#!/usr/bin/env python3
"""Audit automatic previous-election Governor comparisons and linked chart/map."""
import re
from functools import partial
from http.server import ThreadingHTTPServer
from threading import Thread
from playwright.sync_api import expect, sync_playwright
from test_explorer_ux import QuietHandler
from test_senate_swing_ux import ROOT, read, swing_color


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
