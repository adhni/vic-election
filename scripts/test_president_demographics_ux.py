#!/usr/bin/env python3
"""Browser checks for state-level presidential demographics, 2008–2024."""
import argparse
import csv
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import expect, sync_playwright
from test_explorer_ux import QuietHandler
from build_us_house_analysis import pearson, average_ranks

ROOT = Path(__file__).resolve().parents[1]
PERIODS = ('2020-2024', '2016-2020', '2012-2016', '2008-2012')


def read(name):
    with (ROOT / 'data' / name).open() as handle:
        return list(csv.DictReader(handle))


def check(browser, base, screenshots):
    page = browser.new_page(viewport={'width': 1440, 'height': 1100}, has_touch=True)
    page.goto(base + '/app/?year=us-president-2024&view=demographics&mode=house-swing&demographicY=fit', wait_until='networkidle')
    expect(page.locator('.house-scatter-point')).to_have_count(51)
    expect(page.locator('[data-geography="state"]')).to_have_attribute('aria-pressed', 'true')
    expect(page.locator('#houseDemographicSample')).to_be_hidden()
    demo = {r['constituency_code']: r for r in read('us_2024_state_demographics.csv')}
    for period in PERIODS:
        page.locator('#houseDemographicPeriod').select_option(period)
        start, end = period.split('-')
        expect(page.locator('#electionYear')).to_have_value('us-president-' + end)
        expect(page.locator('.house-scatter-point')).to_have_count(51)
        rows = read('us_president_' + period.replace('-', '_') + '_comparison.csv')
        flips = {r['district'] for r in rows if r['seat_flipped'] == 'true'}
        assert set(page.locator('.house-seat-flipped').evaluate_all('els => els.map(e => e.dataset.district)')) == flips
        expect(page.locator('[data-statistic="flipped-states"]')).to_have_text(str(len(flips)))
        assert page.locator('[data-statistic="within-state"]').count() == 0
        colors = page.locator('.district-shape').evaluate_all("els => Object.fromEntries(els.map(e => [e.dataset.district, e.getAttribute('fill')]))")
        for row in rows:
            delta = float(row['democratic_share_change_pp'])
            expected = '#f1efeb' if abs(delta) < .5 else ('#2166ac' if delta >= 5 else '#9ecae1') if delta > 0 else ('#b51f24' if delta <= -5 else '#efaaa3')
            assert colors[row['district']] == expected
        for outcome in (start + '-matched', end + '-matched', 'change'):
            page.locator('#houseDemographicOutcome').select_option(outcome)
            for party in ('democratic', 'republican'):
                page.locator('#houseDemographicParty').select_option(party)
                labels = page.locator('.house-scatter-point').evaluate_all("els => Object.fromEntries(els.map(e => [e.dataset.district, e.getAttribute('aria-label')]))")
                x, y = [], []
                for row in rows:
                    value = float(row['democratic_share_change_pp' if outcome == 'change' else 'democratic_two_party_share_pct_' + outcome[:4]])
                    if party == 'republican': value = -value if outcome == 'change' else 100 - value
                    assert f'{value:.1f}' in labels[row['district']]
                    x.append(float(demo[row['constituency_code']]['bachelors_plus_pct']))
                    y.append(value)
                expect(page.locator('[data-statistic="pearson"]')).to_have_text(f'{pearson(x, y):.3f}')
                expect(page.locator('[data-statistic="spearman"]')).to_have_text(f'{pearson(average_ranks(x), average_ranks(y)):.3f}')
        expect(page.locator('#houseComparisonDownload')).to_have_attribute('href', '../data/us_president_' + period.replace('-', '_') + '_comparison.csv')
        page.reload(wait_until='networkidle')
        expect(page.locator('#houseDemographicPeriod')).to_have_value(period)
        expect(page.locator('.house-scatter-point')).to_have_count(51)
    print('PASS: 4 comparisons, all 51 state/DC shares, 24 source correlations, flip sets, map colours and reload', flush=True)
    page.locator('#houseDemographicPeriod').select_option('2020-2024')
    page.locator('#houseDemographicParty').select_option('democratic')
    point = page.locator('.house-scatter-point[data-district="Georgia"]')
    point.focus()
    point.press('Enter')
    expect(page.locator('#houseDemographicDistrict')).to_have_value('Georgia')
    expect(page.locator('#houseDemographicFlip')).to_contain_text('Flipped to Republican')
    expect(page.locator('#houseDemographicSelectedNote')).to_contain_text('statewide popular-vote leader')
    for axis in ('X', 'Y'):
        page.locator('#houseDemographic' + axis + 'Range').select_option('fit')
    page.locator('#houseDemographicMetric').select_option('english_only_pct')
    expect(page.locator('.house-scatter-point')).to_have_count(51)
    if screenshots:
        page.locator('#explorerGrid').screenshot(path=str(screenshots / 'president-state-desktop.png'))
    for width in (320, 390, 768):
        page.set_viewport_size({'width': width, 'height': 1100})
        page.wait_for_function("() => Math.abs(document.querySelector('#houseDemographicChart svg').viewBox.baseVal.width - document.querySelector('#houseDemographicChart').clientWidth) < 2")
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        point = page.locator('.house-scatter-point[data-district="Arizona"]')
        point.scroll_into_view_if_needed()
        point.tap()
        expect(page.locator('#houseDemographicDistrict')).to_have_value('Arizona')
        if screenshots:
            page.screenshot(path=str(screenshots / f'president-state-{width}.png'), full_page=True)
    page.locator('[data-geography="county"]').click()
    expect(page.locator('.house-scatter-point')).to_have_count(3104)
    page.locator('[data-geography="state"]').click()
    expect(page.locator('.house-scatter-point')).to_have_count(51)
    page.locator('#electionYear').select_option('us-house-2024')
    expect(page.locator('.house-scatter-point')).to_have_count(308)  # selected language metric
    page.locator('#electionYear').select_option('us-president-2024')
    expect(page.locator('.house-scatter-point')).to_have_count(51)
    page.go_back(wait_until='networkidle')
    expect(page.locator('#electionYear')).to_have_value('us-house-2024')
    expect(page.locator('.house-scatter-point')).to_have_count(308)
    page.go_forward(wait_until='networkidle')
    expect(page.locator('.house-scatter-point')).to_have_count(51)
    page.close()
    for year in (2008, 2012, 2016, 2020, 2024):
        page = browser.new_page()
        page.goto(f'{base}/app/?year=us-president-{year}&view=demographics', wait_until='networkidle')
        expect(page.locator('.house-scatter-point')).to_have_count(51)
        expect(page.locator('[data-geography="state"]')).to_have_attribute('aria-pressed', 'true')
        page.close()
    print('PASS: all 5 election entries, state/map linking, touch, axes, county scope and House/presidential history', flush=True)



def check_retry_and_pending(browser, base):
    pattern = '**/data/us_2024_state_demographics.csv'
    page = browser.new_page()
    page.route(pattern, lambda route: route.fulfill(status=503, body='Unavailable'))
    page.goto(base + '/app/?year=us-president-2024&view=demographics', wait_until='networkidle')
    expect(page.locator('#houseDemographicRetry')).to_be_visible()
    page.unroute(pattern)
    page.locator('#houseDemographicRetry').click()
    expect(page.locator('.house-scatter-point')).to_have_count(51)
    page.close()
    page = browser.new_page()
    pending = []
    page.route(pattern, lambda route: pending.append(route))
    page.goto(base + '/app/?year=us-president-2024', wait_until='networkidle')
    page.get_by_role('button', name='Demographics', exact=True).click()
    expect(page.locator('#houseDemographicStatus')).to_contain_text('Loading')
    with page.expect_event('requestfailed', predicate=lambda request: 'us_2024_state_demographics.csv' in request.url):
        page.locator('#electionYear').select_option('us-house-2024')
    expect(page.locator('.house-scatter-point')).to_have_count(312)
    for route in pending:
        route.continue_()
    page.unroute(pattern)
    page.go_back(wait_until='networkidle')
    expect(page.locator('.house-scatter-point')).to_have_count(51)
    page.close()
    print('PASS: presidential retry and cancelled state loads recover across House/history switches', flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshots', type=Path)
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
    Thread(target=server.serve_forever, daemon=True).start()
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.on('page', lambda page: page.on('pageerror', lambda error: errors.append(str(error))))
            check(browser, f'http://127.0.0.1:{server.server_port}', args.screenshots)
            check_retry_and_pending(browser, f'http://127.0.0.1:{server.server_port}')
            browser.close()
        assert not errors, errors
        print('Presidential demographic browser checks passed; no runtime errors.', flush=True)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
