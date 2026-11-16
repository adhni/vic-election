#!/usr/bin/env python3
"""Audit connected election shares, source values and shared explorer controls."""
from functools import partial
from http.server import ThreadingHTTPServer
from threading import Thread
from playwright.sync_api import expect, sync_playwright
from test_explorer_ux import QuietHandler
from test_senate_swing_ux import ROOT, read

CASES=(('us-governor-2024','state','us_governor_state_2024_previous_comparison.csv',2020,2024),
       ('us-governor-2026','county','us_governor_county_2026_previous_comparison.csv',2022,2026),
       ('us-governor-2022','county','us_governor_county_2022_previous_comparison.csv',2018,2022),
       ('us-governor-2018','state','us_governor_state_2018_previous_comparison.csv',2014,2018),
       ('us-senate-2026','state','us_senate_state_2020_2026_comparison.csv',2020,2026),
       ('us-president-2024','county','us_president_county_2020_2024_comparison.csv',2020,2024),
       ('us-house-2024','district','us_house_2022_2024_comparison.csv',2022,2024))

def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT)))
    Thread(target=server.serve_forever,daemon=True).start()
    errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch()
            page=browser.new_page(viewport={'width':1440,'height':1050})
            page.on('pageerror',lambda error:errors.append(str(error)))
            for key,scope,file,start,end in CASES:
                source=read(file)
                eligible=[r for r in source if r['comparison_eligible']=='true']
                by_name={r.get(f'district_{end}') or r['district']:r for r in source}
                page.goto(f'http://127.0.0.1:{server.server_port}/app/?year={key}&geo={scope}&view=demographics&demographicChart=before-after',wait_until='networkidle')
                rows=page.locator('.house-change-row')
                expect(rows).to_have_count(min(20,len(eligible)))
                expect(page.locator('#houseChartType')).to_have_value('before-after')
                expect(page.locator('#houseDemographicStatistics')).to_be_hidden()
                expect(page.locator('#houseDemographicMetric').locator('..')).to_be_hidden()
                expect(page.locator('#houseBeforeAfterNote')).to_contain_text('Hollow dot')
                def audit(republican=False):
                    for row in rows.evaluate_all('(ns)=>ns.map(n=>({...n.dataset, label:n.getAttribute("aria-label"), flipped:!!n.querySelector(".house-change-flipped")}))'):
                        original=by_name[row['district']]
                        baseline=int(original.get('baseline_year') or start)
                        before=float(original[f'democratic_two_party_share_pct_{baseline}'])
                        after=float(original[f'democratic_two_party_share_pct_{end}'])
                        if republican:before,after=100-before,100-after
                        assert abs(float(row['before'])-before)<.000001
                        assert abs(float(row['after'])-after)<.000001
                        assert row['baselineYear']==str(baseline)
                        assert row['electionYear']==str(end)
                        assert row['flipped']==(original['seat_flipped']=='true')
                        assert f'{baseline} → {end}' in row['label']
                audit()
                ranked=sorted(eligible,key=lambda r:(-abs(float(r['democratic_share_change_pp'])),r.get(f'district_{end}') or r['district']))
                selected_name=page.locator('#houseDemographicDistrict').input_value()
                ranked_names=[r.get(f'district_{end}') or r['district'] for r in ranked]
                expected_names=([selected_name]+[name for name in ranked_names if name!=selected_name][:19]) if selected_name in ranked_names else ranked_names[:20]
                assert set(rows.evaluate_all('(ns)=>ns.map(n=>n.dataset.district)'))==set(expected_names)
                outside=next((name for name,r in by_name.items() if r['comparison_eligible']=='true' and name not in rows.evaluate_all('(ns)=>ns.map(n=>n.dataset.district)')),None)
                if key=='us-governor-2022' and scope=='county':
                    demo={r['constituency_code']:r for r in read('us_2024_county_demographics.csv')}
                    outside=next(name for name,r in by_name.items() if r['comparison_eligible']=='true' and not demo.get(r['demographic_constituency_code'],{}).get('bachelors_plus_pct'))
                if outside:
                    page.locator('#houseDemographicDistrict').select_option(outside)
                    expect(rows.first).to_have_attribute('data-district',outside)
                    expect(rows.first).to_have_attribute('aria-pressed','true')
                page.locator('#houseDemographicParty').select_option('republican')
                audit(True)
                page.locator('#houseDemographicYRange').select_option('fit')
                graph=page.locator('#houseDemographicChart svg')
                for row in rows.all():
                    for dot in row.locator('circle').all():
                        cx=float(dot.get_attribute('cx'))
                        assert 0<cx<float(graph.get_attribute('width'))
                rows.first.focus()
                rows.first.press('ArrowDown')
                selected=rows.nth(1).get_attribute('data-district')
                page.keyboard.press('Enter')
                expect(page.locator('#houseDemographicDistrict')).to_have_value(selected)
                expect(rows.first).to_have_attribute('data-district',selected)
                expect(rows.first).to_be_focused()
                page.keyboard.press('ArrowDown')
                expect(rows.nth(1)).to_be_focused()
                page.reload(wait_until='networkidle')
                expect(page.locator('#houseChartType')).to_have_value('before-after')
                expect(page.locator('#houseDemographicParty')).to_have_value('republican')
                for width in (320,390,768):
                    page.set_viewport_size({'width':width,'height':1050})
                    expect(rows).to_have_count(min(20,len(eligible)))
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                if key=='us-governor-2024':
                    (ROOT/'tmp/explorer-ux').mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=str(ROOT/'tmp/explorer-ux/before-after-mobile.png'),full_page=True)
                page.set_viewport_size({'width':1440,'height':1050})
                page.locator('#houseChartType').select_option('demographics')
                expect(page.locator('.house-scatter-point').first).to_be_visible()
                expect(page.locator('#houseDemographicMetric').locator('..')).to_be_visible()
                expect(page.locator('#houseDemographicStatistics')).to_be_visible()
                print(f'PASS: {key} {scope}: source shares, flips, pinning, party, axes, keyboard, reload, mobile and scatter restoration',flush=True)
            browser.close()
        assert not errors,errors
    finally:server.shutdown();server.server_close()

if __name__=='__main__':main()
