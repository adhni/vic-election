"""Audit two-side source arithmetic and precinct dot interactions."""
import csv
import json
from functools import partial
from http.server import ThreadingHTTPServer
from threading import Thread
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from test_state_clusters_ux import QuietHandler
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'data/nyc_precinct_dots.json').read_text())['elections']
for year,e in data.items():
    source={}
    for r in csv.DictReader((ROOT/f'data/nyc_{year}_mayor_ed_fpp.csv').open()):
        source.setdefault(r['district'],{})[r['candidate']]=int(r['votes'])
    assert set(source)==set(e['precincts'])
    for name,r in e['precincts'].items():
        assert r['votes']==source[name]
        d=source[name][e['democratic_candidate']]
        opposition=sum(source[name][n] for n in e['opposition_candidates'])
        assert r['democratic']==d and r['opposition']==opposition
        assert r['other']==sum(source[name].values())-d-opposition
        assert r['share']==(100*d/(d+opposition) if d+opposition else None)
server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT)))
Thread(target=server.serve_forever,daemon=True).start()
try:
 with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(f'http://127.0.0.1:{server.server_port}/app/nyc-precinct-dots.html')
    for year,e in data.items():
      page.select_option('#year',year)
      expect(page.locator('#status')).to_contain_text(f'{year} general election',timeout=30000)
      for k in [2,3,4,5,7]:
        page.select_option('#groups',str(k))
        marks=page.locator('#chart circle').evaluate_all('els=>els.map(e=>({name:e.dataset.precinct,group:e.closest(".dot-lane").dataset.group,color:e.getAttribute("fill")}))')
        assert len(marks)==len(e['precincts']) and len({m['name'] for m in marks})==len(marks)
        expect(page.locator('#dotCountyMap path')).to_have_count(len(marks))
        for m in marks:
          share=e['precincts'][m['name']]['share']
          cuts={2:[50],3:[45,55],4:[40,50,60],5:[40,45,55,60],7:[30,40,45,55,60,70]}[k]
          # Upper boundaries at 55/60/70 are inclusive; 50 is the start of the Democratic side.
          if share is None: group='none'
          else:
            group=str(next((i+1 for i,c in enumerate(cuts) if share<c or (c in [55,60,70] and share==c)),len(cuts)+1))
          assert m['group']==group,(year,k,m,share,group)
          if share is None: assert m['color']=='#a6a6a6'
      if year=='2025':
        expect(page.locator('#sideNote')).to_contain_text('Cuomo + Sliwa')
        assert 'Republican' not in page.locator('#chart').inner_text()
      page.select_option('#borough','Queens')
      expected=[n for n,r in e['precincts'].items() if r['state']=='Queens']
      expect(page.locator('#chart circle')).to_have_count(len(expected))
      name=expected[0]
      page.locator('#chart circle').first.click()
      expect(page.locator('#name')).to_have_text(name)
      expect(page.locator('#dotCountyMap .is-selected')).to_have_count(1)
      page.locator('#chart circle').first.focus()
      page.keyboard.press('ArrowRight')
      expect(page.locator('#chart .is-selected')).to_have_count(1)
      page.reload()
      expect(page.locator('#status')).to_contain_text(f'{year} general election',timeout=30000)
      expect(page.locator('#borough')).to_have_value('Queens')
      expect(page.locator('#source')).to_have_attribute('href',f'index.html?year=nyc-mayor-{year}&geo=ed')
      page.locator('#dotCountyMap path:not(.is-filtered)').last.click()
      expect(page.locator('#chart .is-selected')).to_have_count(1)
      expect(page.locator('#chart circle[tabindex="0"]')).to_have_count(1)
      page.select_option('#borough','all')
    page.fill('#search','no such precinct')
    expect(page.locator('#chart circle')).to_have_count(0)
    expect(page.locator('#empty')).to_be_visible()
    page.click('#reset')
    expect(page.locator('#status')).to_contain_text('2025 general election',timeout=30000)
    expect(page.locator('#chart circle')).to_have_count(4102)
    out=ROOT/'tmp/nyc-precinct-dots';out.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(out/'desktop.png'),full_page=True)
    for width in [320,390,768]:
      page.set_viewport_size({'width':width,'height':900})
      page.wait_for_timeout(300)
      assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
      page.locator('#dots').screenshot(path=str(out/f'mobile-{width}.png'))
    assert not errors,errors
    browser.close()
finally: server.shutdown()
print('PASS all source votes and two-side arithmetic; 3 elections × 5 group counts, exact dot/map coverage, filters, selection, keyboard, reload, empty/reset and mobile layouts')
