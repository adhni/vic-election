"""Check both Chicago rounds at precinct and ward levels, including mobile."""
import json
import math
import re
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright,expect
from test_state_clusters_ux import QuietHandler
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'data/chicago_precinct_dots.json').read_text())['elections']

def color(r,e):
    if r['leader'] not in e['colors']:return '#a6a6a6'
    margin=100*r['margin']/r['total'];factor=.12 if margin<=2 else .32 if margin<=5 else .54 if margin<=10 else .77 if margin<=20 else 1
    base=e['colors'][r['leader']]
    return '#'+''.join(f'{math.floor(255+(int(base[i:i+2],16)-255)*factor+.5):02x}' for i in [1,3,5])

def normalize(c):return '#'+''.join(f'{int(n):02x}' for n in re.findall(r'\d+',c)) if c.startswith('rgb(') else c
server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT)))
Thread(target=server.serve_forever,daemon=True).start()
try:
 with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)));base=f'http://127.0.0.1:{server.server_port}'
    for round_name,e in data.items():
      for level,records in e['geographies'].items():
        count=len(records)
        page.goto(f'{base}/app/chicago-precinct-dots.html?round={round_name}&geo={level}',wait_until='networkidle')
        expect(page.locator('#round')).to_have_value(round_name);expect(page.locator('#geography')).to_have_value(level)
        expect(page.locator('#chart circle')).to_have_count(count);expect(page.locator('#dotCountyMap path')).to_have_count(count)
        expect(page.locator('#boundaryNote')).to_contain_text('certified citywide candidate totals')
        expect(page.locator('#pageTitle')).to_have_text(f'One {level}. One dot.')
        actual=page.locator('#chart circle').evaluate_all('els=>els.map(e=>({name:e.dataset.precinct,color:e.getAttribute("fill"),group:e.closest(".dot-lane").dataset.group}))')
        assert {m['name'] for m in actual}==set(records)
        for m in actual:assert m['color']==color(records[m['name']],e) and m['group']==records[m['name']]['leader']
        for m in page.locator('#dotCountyMap path').evaluate_all('els=>els.map(e=>({name:e.dataset.county,color:e.style.fill}))'):
            assert normalize(m['color'])==color(records[m['name']],e)
        n=next(iter(records));page.select_option('#precinct',n);expect(page.locator('#votes')).to_contain_text('registered voters')
        expect(page.locator('#votes')).to_contain_text('turnout');expect(page.locator('#votes')).to_contain_text('without a recorded mayoral vote')
        if round_name=='first-round':
            expect(page.locator('#votes')).to_contain_text('Johnny Logalbo');expect(page.locator('#sideNote')).to_contain_text('No outright winner')
            expect(page.locator('#votes tbody tr')).to_have_count(15)
        else:expect(page.locator('#votes tbody tr')).to_have_count(2)
        if level=='precinct':
            page.select_option('#ward','Ward 24');expect(page.locator('#dotCountyMap path')).to_have_count(20)
            page.fill('#search','24020');expect(page.locator('#chart circle')).to_have_count(1)
            page.locator('#chart circle').click();expect(page.locator('#name')).to_have_text('Ward 24 · Precinct 20')
        else:
            page.fill('#search','Ward 24');expect(page.locator('#chart circle')).to_have_count(1)
            page.locator('#chart circle').click();expect(page.locator('#name')).to_have_text('Ward 24')
        expect(page.locator('#dotCountyMap .is-selected')).to_have_count(1)
        expect(page.locator('#source')).to_have_attribute('href',f'index.html?year=chicago-mayor-2023-{round_name}&geo={level}')
        page.fill('#search','');page.locator('#chart circle').first.focus();page.keyboard.press('ArrowRight')
        expect(page.locator('#chart .is-selected')).to_have_count(1)
        selected=page.locator('#name').inner_text();page.reload(wait_until='networkidle');expect(page.locator('#name')).to_have_text(selected)
        page.fill('#search','nothing matches');expect(page.locator('#empty')).to_be_visible();page.click('#reset')
        expect(page.locator('#round')).to_have_value('runoff');expect(page.locator('#geography')).to_have_value('precinct');expect(page.locator('#chart circle')).to_have_count(1291)
        # The main explorer offers exactly these round/geometry combinations.
        page.goto(f'{base}/app/?year=chicago-mayor-2023-{round_name}&geo={level}',wait_until='networkidle')
        expect(page.locator('#explorerGrid')).to_have_attribute('aria-busy','false')
        expect(page.locator('#electionYear')).to_have_value('chicago-mayor-2023-runoff')
        expect(page.locator('#electionStage')).to_have_value(f'chicago-mayor-2023-{round_name}')
        expect(page.locator('#electionYear option').filter(has_text='Chicago Mayor 2023')).to_have_count(1)
        expect(page.locator('.district-shape')).to_have_count(count)
        expect(page.locator('#stateSummary')).to_contain_text('Brandon Johnson');expect(page.locator('#stateSummary')).to_contain_text('Paul Vallas')
        if round_name=='first-round':expect(page.locator('#stateSummary')).to_contain_text('Lori Lightfoot')
        expect(page.locator('#mapLegend')).to_contain_text('Darker means a larger lead')
    # Same-page round and geography changes, filters and retained ward filter.
    page.goto(f'{base}/app/chicago-precinct-dots.html',wait_until='networkidle')
    page.select_option('#ward','Ward 24');page.select_option('#geography','ward');expect(page.locator('#chart circle')).to_have_count(50)
    page.select_option('#round','first-round');expect(page.locator('#chart circle')).to_have_count(50)
    page.select_option('#geography','precinct');expect(page.locator('#chart circle')).to_have_count(20)
    page.locator('#legend button').filter(has_text='Paul Vallas').click()
    expected=sum(r['leader']=='Paul Vallas' for r in data['first-round']['geographies']['precinct'].values() if r['ward']==24)
    expect(page.locator('#chart circle')).to_have_count(expected)
    out=ROOT/'tmp/chicago/preview';out.mkdir(parents=True,exist_ok=True)
    page.click('#reset');page.screenshot(path=str(out/'runoff-desktop.png'),full_page=True)
    for width in [320,390,768]:
      page.set_viewport_size({'width':width,'height':900})
      for round_name in data:
       for level in ['precinct','ward']:
        page.goto(f'{base}/app/chicago-precinct-dots.html?round={round_name}&geo={level}',wait_until='networkidle')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,round_name,level)
        assert page.locator('#votes').evaluate('e=>e.scrollWidth<=e.clientWidth')
        page.goto(f'{base}/app/?year=chicago-mayor-2023-{round_name}&geo={level}',wait_until='networkidle')
        expect(page.locator('#explorerGrid')).to_have_attribute('aria-busy','false')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,round_name,level,'main')
      page.screenshot(path=str(out/f'map-{width}.png'),full_page=True)
    assert not errors,errors
    browser.close()
 print('PASS Chicago UX: both rounds × precinct/ward, all dots/map colours, write-ins, turnout, ward 24 split, linked selection, keyboard, filters, reload and mobile')
finally:server.shutdown()
