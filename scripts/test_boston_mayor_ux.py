"""Check both Boston elections, candidate shades, linked dots/maps and mobile."""
import json
import math
import re
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import quote
from playwright.sync_api import sync_playwright,expect
from test_state_clusters_ux import QuietHandler
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'data/boston_precinct_dots.json').read_text())['elections']

def color(r,e):
    if r['leader'] not in e['colors']:return '#a6a6a6'
    margin=100*r['margin']/r['total'];factor=.12 if margin<=2 else .32 if margin<=5 else .54 if margin<=10 else .77 if margin<=20 else 1
    base=e['colors'][r['leader']]
    return '#'+''.join(f'{math.floor(255+(int(base[i:i+2],16)-255)*factor+.5):02x}' for i in [1,3,5])

def normalize(c):return '#'+''.join(f'{int(n):02x}' for n in re.findall(r'\d+',c)) if c.startswith('rgb(') else c
server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT)));Thread(target=server.serve_forever,daemon=True).start()
try:
 with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    base=f'http://127.0.0.1:{server.server_port}'
    for year,e in data.items():
        page.goto(f'{base}/app/boston-precinct-dots.html?year={year}',wait_until='networkidle')
        expect(page.locator('#chart circle')).to_have_count(255);expect(page.locator('#dotCountyMap path')).to_have_count(255)
        assert page.locator('#votes').evaluate('e=>e.scrollWidth<=e.clientWidth')
        actual=page.locator('#chart circle').evaluate_all('els=>els.map(e=>({name:e.dataset.precinct,color:e.getAttribute("fill"),group:e.closest(".dot-lane").dataset.group}))')
        assert {m['name'] for m in actual}==set(e['precincts'])
        for m in actual:
            r=e['precincts'][m['name']];assert m['color']==color(r,e) and m['group']==r['leader']
        for m in page.locator('#dotCountyMap path').evaluate_all('els=>els.map(e=>({name:e.dataset.county,color:e.style.fill}))'):
            assert normalize(m['color'])==color(e['precincts'][m['name']],e)
        if year!='2017':expect(page.locator('#boundaryNote')).to_contain_text('not been independently verified')
        else:expect(page.locator('#boundaryNote')).to_be_hidden()
        page.select_option('#ward','Ward 05');expect(page.locator('#chart circle')).to_have_count(sum(r['ward']==5 for r in e['precincts'].values()))
        page.fill('#search','0502A');expect(page.locator('#chart circle')).to_have_count(1)
        page.locator('#chart circle').click();expect(page.locator('#name')).to_have_text('Ward 05 · Precinct 02A');expect(page.locator('#dotCountyMap .is-selected')).to_have_count(1)
        expect(page.locator('#source')).to_have_attribute('href',f'index.html?year=boston-mayor-{year}&geo=precinct')
        page.fill('#search','');page.locator('#chart circle').first.focus();page.keyboard.press('ArrowRight');expect(page.locator('#chart .is-selected')).to_have_count(1)
        page.reload(wait_until='networkidle');expect(page.locator('#ward')).to_have_value('Ward 05')
        page.select_option('#ward','all')
        leader=next(r['leader'] for r in e['precincts'].values() if r['leader'] in e['colors'])
        page.locator('#legend button').filter(has_text=leader).click();expect(page.locator('#chart circle')).to_have_count(sum(r['leader']==leader for r in e['precincts'].values()))
        page.locator('#legend button').filter(has_text='All precincts').click()
        page.fill('#search','no such place');expect(page.locator('#empty')).to_be_visible();expect(page.locator('#chart circle')).to_have_count(0)
        page.click('#reset');expect(page.locator('#year')).to_have_value('2021');expect(page.locator('#chart circle')).to_have_count(255)
        # Main explorer includes both precinct and ward geographies.
        page.goto(f'{base}/app/?year=boston-mayor-{year}',wait_until='networkidle')
        expect(page.locator('#explorerGrid')).to_have_attribute('aria-busy','false')
        expect(page.locator('#electionYear')).to_have_value(f'boston-mayor-{year}');expect(page.locator('.district-shape')).to_have_count(255)
        expect(page.locator('#electionHeading')).to_have_text(f'Boston Mayor {year}')
        for c in e['candidates'][:2]:expect(page.locator('#stateSummary')).to_contain_text(c)
        expect(page.locator('#mapLegend')).to_contain_text('Darker means a larger lead')
        for leader in e['candidates'][:2]:
            candidates=[(n,r) for n,r in e['precincts'].items() if r['leader']==leader];candidates.sort(key=lambda pair:pair[1]['margin']/pair[1]['total'])
            close,strong=candidates[0][0],candidates[-1][0]
            colors=[]
            for n in [close,strong]:
                colors.append(page.locator(f'.district-shape[data-district={json.dumps(n,ensure_ascii=False)}]').evaluate('e=>getComputedStyle(e).fill'))
            assert colors[0]!=colors[1],(year,leader,colors)
        page.locator('[data-geography="ward"]').click();expect(page.locator('.district-shape')).to_have_count(22)
        if year=='2017':
            tied=next(n for n,r in e['precincts'].items() if r['leader']=='Tied local leaders');zero=next(n for n,r in e['precincts'].items() if r['leader']=='No mayoral votes')
            for n,text in [(tied,'Tied:'),(zero,'No mayoral votes')]:
                page.goto(f'{base}/app/?year=boston-mayor-2017&district={quote(n)}',wait_until='networkidle');expect(page.locator('#districtSummary')).to_contain_text(text)
            page.locator(f'.district-shape[data-district={json.dumps(zero,ensure_ascii=False)}]').hover();expect(page.locator('#mapTooltip')).not_to_contain_text('BOE reports')
    out=ROOT/'tmp/boston/preview';out.mkdir(parents=True,exist_ok=True)
    page.goto(f'{base}/app/boston-precinct-dots.html?year=2013',wait_until='networkidle');page.screenshot(path=str(out/'dots-desktop.png'),full_page=True)
    for width in [320,390,768]:
        page.set_viewport_size({'width':width,'height':900});page.wait_for_timeout(300)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
        page.screenshot(path=str(out/f'dots-{width}.png'),full_page=True)
        page.goto(f'{base}/app/?year=boston-mayor-2021',wait_until='networkidle')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
        page.screenshot(path=str(out/f'map-{width}.png'),full_page=True)
        page.goto(f'{base}/app/boston-precinct-dots.html?year=2021',wait_until='networkidle')
    assert not errors,errors;browser.close()
finally:server.shutdown()
print('PASS all three Boston elections: exact 255 dot/map colours and leaders, 22 wards, subprecinct 2A, ties/zero votes, filters, linked selection, keyboard, reload, coverage notices and 320/390/768px layouts')
