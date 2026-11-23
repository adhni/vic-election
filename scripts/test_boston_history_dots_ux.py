"""Browser checks for Boston history coverage, partitions and linked views."""
import json
import re
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright, expect
from test_state_clusters_ux import QuietHandler

ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'data/boston_history_clusters.json').read_text())
server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT)))
Thread(target=server.serve_forever,daemon=True).start()

def normalized(color):
    return '#'+''.join(f'{int(n):02x}' for n in re.findall(r'\d+',color)) if color.startswith('rgb(') else color

try:
 with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    base=f'http://127.0.0.1:{server.server_port}/app/boston-history-dots.html'
    page.goto(base,wait_until='networkidle')
    expect(page.locator('#qualityNote')).to_contain_text('38 of 255')
    expect(page.locator('#qualityNote')).to_contain_text('not representative')
    expect(page.locator('#groups')).to_have_value('3')
    for mode in ['screened','exploratory']:
      page.select_option('#coverage',mode)
      for k in [2,3,4,5,7]:
        page.select_option('#groups',str(k));model=data['models'][mode][str(k)]
        marks=page.locator('#chart circle').evaluate_all('els=>els.map(e=>({name:e.dataset.precinct,color:e.getAttribute("fill"),group:e.closest(".dot-lane").dataset.group}))')
        assert len(marks)==255 and {m['name'] for m in marks}==set(data['areas'])
        def color(n):return model['groups'][model['assignments'][n]-1]['color'] if n in model['assignments'] else '#a6a6a6'
        for m in marks:
            assert m['group']==str(model['assignments'].get(m['name'],'none')) and m['color']==color(m['name'])
        expect(page.locator('#dotCountyMap path')).to_have_count(255)
        for m in page.locator('#dotCountyMap path').evaluate_all('els=>els.map(e=>({name:e.dataset.county,color:e.style.fill}))'):
            assert normalized(m['color'])==color(m['name'])
    page.select_option('#groups','3');page.click('#viewPatterns')
    expect(page.locator('#patternChart circle')).to_have_count(254)
    for xyear,yyear in [('2013','2017'),('2017','2021'),('2021','2013')]:
        page.select_option('#xYear',xyear);page.select_option('#yYear',yyear)
        frame=page.locator('#patternChart').evaluate('s=>({w:s.viewBox.baseVal.width,h:s.viewBox.baseVal.height})')
        for m in page.locator('#patternChart circle').evaluate_all('els=>els.map(e=>({name:e.dataset.precinct,x:+e.getAttribute("cx"),y:+e.getAttribute("cy")}))'):
            a=data['areas'][m['name']]['shares'];xi=data['years'].index(int(xyear));yi=data['years'].index(int(yyear))
            assert abs(m['x']-(45+a[xi]/100*(frame['w']-22-45)))<1e-6
            assert abs(m['y']-(frame['h']-65-a[yi]/100*(frame['h']-65-50)))<1e-6
    page.select_option('#coverage','screened');expect(page.locator('#patternChart circle')).to_have_count(38)
    page.locator('#patternChart circle').first.click();expect(page.locator('#dotCountyMap .is-selected')).to_have_count(1)
    expect(page.locator('#votes')).to_contain_text('Marty Walsh');expect(page.locator('#votes')).to_contain_text('Michelle Wu')
    expect(page.locator('#combined')).to_contain_text('not verification')
    page.locator('#patternChart .is-selected').focus();page.keyboard.press('ArrowRight')
    expect(page.locator('#patternChart .is-selected')).to_have_count(1)
    page.reload(wait_until='networkidle');expect(page.locator('#viewPatterns')).to_have_attribute('aria-pressed','true')
    expect(page.locator('#xYear')).to_have_value('2021');expect(page.locator('#yYear')).to_have_value('2013')
    page.click('#viewGroups');page.select_option('#ward','Ward 05');page.fill('#search','0502A')
    expect(page.locator('#chart circle')).to_have_count(1);page.locator('#chart circle').click()
    expect(page.locator('#name')).to_have_text('Ward 05 · Precinct 02A');expect(page.locator('#badge')).to_have_text('Not grouped')
    expect(page.locator('#summary')).to_contain_text('No matching code')
    page.click('#reset');page.select_option('#precinct','Ward 01 · Precinct 15')
    expect(page.locator('#summary')).to_contain_text('No votes');expect(page.locator('#votes')).to_contain_text('Unavailable')
    page.select_option('#coverage','exploratory');expect(page.locator('#badge')).to_have_text('Not grouped')
    expect(page.locator('#qualityNote')).to_contain_text('provisional')
    page.click('#legend [data-group="none"]');expect(page.locator('#chart circle')).to_have_count(1)
    page.click('#viewPatterns');expect(page.locator('#patternChart circle')).to_have_count(0)
    expect(page.locator('#empty')).to_be_visible();expect(page.locator('#dotCountyMap .is-selected')).to_have_count(1)
    page.click('#reset');page.fill('#search','no such precinct');expect(page.locator('#empty')).to_be_visible()
    expect(page.locator('#chart circle')).to_have_count(0);page.click('#reset')
    page.goto(base+'?k=99&coverage=invalid&ward=missing&group=99&xYear=bad',wait_until='networkidle')
    expect(page.locator('#groups')).to_have_value('3');expect(page.locator('#coverage')).to_have_value('screened')
    expect(page.locator('#chart circle')).to_have_count(255)
    out=ROOT/'tmp/boston-history';out.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(out/'desktop-screened.png'),full_page=True)
    page.select_option('#coverage','exploratory');page.screenshot(path=str(out/'desktop-exploratory.png'),full_page=True)
    for width in [320,390,768]:
        page.set_viewport_size({'width':width,'height':900});page.wait_for_timeout(250)
        for view in ['Groups','Patterns']:
            page.click('#view'+view);page.wait_for_timeout(100)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,view)
            assert page.locator('.view-switch button,.axis-controls select').evaluate_all('els=>els.every(e=>{const b=e.getBoundingClientRect();return !b.width || (b.left>=0 && b.right<=innerWidth);})'),(width,view,'controls')
            assert page.locator('#votes').evaluate('e=>e.scrollWidth<=e.clientWidth'),(width,view,'table')
        page.screenshot(path=str(out/f'mobile-{width}.png'),full_page=True)
    assert not errors,errors
    browser.close()
 print('PASS Boston history UX: both coverage rules, all group counts and map colours, every scatter coordinate, exclusions, filters, keyboard, URL restoration and mobile layouts')
finally:
 server.shutdown()
