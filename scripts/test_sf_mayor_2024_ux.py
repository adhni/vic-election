"""Check every SF count snapshot and linked precinct interactions."""
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
data=json.loads((ROOT/'data/sf_2024_mayor_rounds.json').read_text())

def expected_color(r):
    if r['leader'] not in data['colors']:return '#a6a6a6'
    v=100*r['margin']/r['continuing'];t=.12 if v<=2 else .32 if v<=5 else .54 if v<=10 else .77 if v<=20 else 1
    base=data['colors'][r['leader']]
    return '#'+''.join(f'{math.floor(255+(int(base[i:i+2],16)-255)*t+.5):02x}' for i in [1,3,5])

def normalize(c):return '#'+''.join(f'{int(n):02x}' for n in re.findall(r'\d+',c)) if c.startswith('rgb(') else c
server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT)))
Thread(target=server.serve_forever,daemon=True).start()
try:
 with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)));base=f'http://127.0.0.1:{server.server_port}'
    page.goto(base+'/app/sf-precinct-dots.html',wait_until='networkidle')
    expect(page.locator('#chart circle')).to_have_count(514)
    expect(page.locator('#round option')).to_have_count(14)
    expect(page.locator('#previousRound')).to_be_disabled()
    for number in range(1,15):
        page.select_option('#round',str(number));city=data['rounds'][number-1]
        expect(page.locator('#roundTitle')).to_have_text(f'Citywide · Round {number} of 14')
        for key in ['continuing','exhausted','overvotes','blanks']:
            expect(page.locator('#'+key)).to_have_text(f'{city[key]:,}')
        marks=page.locator('#chart circle').evaluate_all('els=>els.map(e=>({name:e.dataset.precinct,color:e.getAttribute("fill"),group:e.closest(".dot-lane").dataset.group}))')
        assert len(marks)==514 and {m['name'] for m in marks}==set(data['precincts'])
        for mark in marks:
            r=data['precincts'][mark['name']]['rounds'][number-1]
            assert mark['color']==expected_color(r) and mark['group']==r['leader']
        for m in page.locator('#dotCountyMap path').evaluate_all('els=>els.map(e=>({name:e.dataset.county,color:e.style.fill}))'):
            assert normalize(m['color'])==expected_color(data['precincts'][m['name']]['rounds'][number-1])
        assert page.locator('#votes tbody tr').count()==len(city['active'])
        expect(page.locator('#votes')).to_contain_text('Election turnout (statement of vote)')
        if city['eliminated']:expect(page.locator('#votes')).to_contain_text('Eliminated after this round')
    expect(page.locator('#nextRound')).to_be_disabled()
    expect(page.locator('#roundSummary')).to_contain_text('182,364')
    expect(page.locator('#roundSummary')).to_contain_text('55.02%')
    expect(page.locator('#votes')).to_contain_text('Daniel Lurie');expect(page.locator('#votes')).to_contain_text('London Breed')
    page.click('#previousRound');expect(page.locator('#round')).to_have_value('13')
    page.click('#nextRound');expect(page.locator('#round')).to_have_value('14')
    withheld=next(n for n,a in data['precincts'].items() if a['sov_suppressed'])
    page.select_option('#precinct',withheld);expect(page.locator('#votes')).to_contain_text('Statement-of-vote row withheld')
    expect(page.locator('#votes')).to_contain_text('Election turnout is unavailable')
    expect(page.locator('#source')).to_have_attribute('href',re.compile('year=sf-mayor-2024-round-14'))
    page.select_option('#precinct','Precinct 1101');expect(page.locator('#votes')).to_contain_text('74.91%')
    page.select_option('#round','1');expect(page.locator('#votes')).to_contain_text('74.91%')
    page.select_option('#district','District 11')
    count=sum(a['state']=='District 11' for a in data['precincts'].values())
    expect(page.locator('#chart circle')).to_have_count(count);expect(page.locator('#dotCountyMap path')).to_have_count(count)
    page.fill('#search','1101');expect(page.locator('#chart circle')).to_have_count(1)
    page.locator('#chart circle').click();expect(page.locator('#name')).to_have_text('Precinct 1101')
    expect(page.locator('#dotCountyMap .is-selected')).to_have_count(1)
    page.fill('#search','');page.locator('#chart circle').first.focus();page.keyboard.press('ArrowRight')
    expect(page.locator('#chart .is-selected')).to_have_count(1)
    selected=page.locator('#name').inner_text();page.reload(wait_until='networkidle')
    expect(page.locator('#name')).to_have_text(selected);expect(page.locator('#district')).to_have_value('District 11')
    page.click('#reset');page.locator('#legend button').filter(has_text='Daniel Lurie').click()
    expected=sum(a['rounds'][0]['leader']=='Daniel Lurie' for a in data['precincts'].values())
    expect(page.locator('#chart circle')).to_have_count(expected)
    page.click('#reset');page.fill('#search','nothing matches');expect(page.locator('#empty')).to_be_visible()
    expect(page.locator('#chart circle')).to_have_count(0);page.click('#reset')
    page.goto(base+'/app/sf-precinct-dots.html?round=99&district=missing&group=missing&precinct=missing',wait_until='networkidle')
    expect(page.locator('#round')).to_have_value('1');expect(page.locator('#chart circle')).to_have_count(514)
    out=ROOT/'tmp/sf/preview';out.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(out/'first-round-desktop.png'),full_page=True)
    page.select_option('#round','14');page.screenshot(path=str(out/'final-round-desktop.png'),full_page=True)
    for number in range(1,15):
        page.goto(f'{base}/app/?year=sf-mayor-2024-round-{number}',wait_until='networkidle')
        expect(page.locator('#explorerGrid')).to_have_attribute('aria-busy','false')
        expect(page.locator('#electionYear')).to_have_value('sf-mayor-2024-round-14')
        expect(page.locator('#electionStage')).to_have_value(f'sf-mayor-2024-round-{number}')
        expect(page.locator('#electionYear option').filter(has_text='San Francisco Mayor 2024')).to_have_count(1)
        expect(page.locator('.district-shape')).to_have_count(514)
        expect(page.locator('#stateSummary')).to_contain_text('Daniel Lurie');expect(page.locator('#stateSummary')).to_contain_text('London Breed')
        expect(page.locator('#mapLegend')).to_contain_text('Darker means a larger lead')
    page.select_option('#electionStage','sf-mayor-2024-round-1')
    expect(page.locator('#electionHeading')).to_contain_text('Count 1 of 14')
    page.select_option('#electionStage','sf-mayor-2024-round-14')
    expect(page.locator('#electionHeading')).to_contain_text('Count 14 of 14')
    page.locator('.district-shape[data-district="Precinct 9901"]').dispatch_event('pointerover',{'clientX':200,'clientY':200})
    expect(page.locator('#mapTooltip')).to_contain_text('No mayoral CVR records')
    for width in [320,390,768]:
      page.set_viewport_size({'width':width,'height':900})
      for number in [1,8,14]:
        page.goto(f'{base}/app/sf-precinct-dots.html?round={number}',wait_until='networkidle')
        expect(page.locator('#chart circle')).to_have_count(514)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,number)
        assert page.locator('#votes').evaluate('e=>e.scrollWidth<=e.clientWidth')
        assert page.locator('.round-stepper button').evaluate_all('els=>els.every(e=>{const b=e.getBoundingClientRect();return b.left>=0&&b.right<=innerWidth})')
        page.goto(f'{base}/app/?year=sf-mayor-2024-round-{number}',wait_until='networkidle')
        expect(page.locator('#explorerGrid')).to_have_attribute('aria-busy','false')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,number,'main')
      page.screenshot(path=str(out/f'main-{width}.png'),full_page=True)
    assert not errors,errors
    browser.close()
 print('PASS SF UX: all 14 rounds, every precinct dot/map colour, main explorer snapshots, fixed turnout, withheld labels, controls, keyboard, filters, reload and mobile layouts')
finally:server.shutdown()
