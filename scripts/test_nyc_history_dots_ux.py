"""Browser checks for all NYC history methods, groups, palettes and linked views."""
import json
import math
import re
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright, expect
from test_state_clusters_ux import QuietHandler
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'data/nyc_history_clusters.json').read_text());areas=data['areas']
PALETTE=['#7851a9','#c57928','#288b87','#4267b2','#bd4c71','#6b7f30','#8c564b']

def expected(method,k,palette):
    groups={};assignments={}
    if method=='similarity':
        m=data['models'][str(k)];assignments={n:r['group'] for n,r in m['assignments'].items()}
        groups={g['id']:g['mean_democratic_share'] for g in m['groups']}
    else:
        for n,r in areas.items():
            if not r['eligible']:continue
            v=sum(r['democratic_share'])/3
            if k==2:g=1 if v<50 else 2
            elif k==3:g=1 if v<45 else 2 if v<=55 else 3
            elif k==4:g=1 if v<40 else 2 if v<50 else 3 if v<=60 else 4
            elif k==5:g=1 if v<40 else 2 if v<45 else 3 if v<=55 else 4 if v<=60 else 5
            else:g=1 if v<30 else 2 if v<40 else 3 if v<45 else 4 if v<=55 else 5 if v<=60 else 6 if v<=70 else 7
            assignments[n]=g
        for g in set(assignments.values()):groups[g]=sum(sum(areas[n]['democratic_share'])/3 for n,a in assignments.items() if a==g)/sum(a==g for a in assignments.values())
    def color(n):
        if n not in assignments:return '#a6a6a6'
        g=assignments[n]
        if palette=='groups':return PALETTE[g-1]
        v=groups[g];end=[33,102,172] if v>=50 else [178,24,43];t=min(1,abs(v-50)/25)
        return '#'+''.join(f'{math.floor(166+(c-166)*t+.5):02x}' for c in end)
    return assignments,color

server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT)));Thread(target=server.serve_forever,daemon=True).start()
try:
 with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page(viewport={'width':1500,'height':1000});errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(f'http://127.0.0.1:{server.server_port}/app/nyc-history-dots.html')
    expect(page.locator('#status')).to_contain_text('2017 and 2025 estimated.',timeout=30000)
    expect(page.locator('#qualityNote')).to_contain_text('5,145')
    for method in ['similarity','bands']:
      page.select_option('#method',method)
      for k in [2,3,4,5,7]:
        page.select_option('#groups',str(k))
        for palette in ['party','groups']:
          page.select_option('#colors',palette);assignment,color=expected(method,k,palette)
          marks=page.locator('#chart circle').evaluate_all('els=>els.map(e=>({name:e.dataset.precinct,color:e.getAttribute("fill"),group:e.closest(".dot-lane").dataset.group}))')
          assert len(marks)==len(areas) and {m['name'] for m in marks}==set(areas)
          for m in marks:
            assert m['group']==str(assignment.get(m['name'],'none'))
            assert m['color']==color(m['name']),(method,k,palette,m,color(m['name']))
          expect(page.locator('#dotCountyMap path')).to_have_count(len(areas))
          map_colors=page.locator('#dotCountyMap path').evaluate_all('els=>els.map(e=>({name:e.dataset.county,color:e.style.fill}))')
          for m in map_colors:
            serialized=m['color']
            if serialized.startswith('rgb('):serialized='#'+''.join(f'{int(v):02x}' for v in re.findall(r'\d+',serialized))
            assert serialized==color(m['name']),(method,k,palette,m,color(m['name']))
    page.click('#viewPatterns')
    expect(page.locator('#patternChart circle')).to_have_count(5145)
    frame=page.locator('#patternChart').evaluate('s=>({w:s.viewBox.baseVal.width,h:s.viewBox.baseVal.height})')
    for m in page.locator('#patternChart circle').evaluate_all('els=>els.map(e=>({name:e.dataset.precinct,x:+e.getAttribute("cx"),y:+e.getAttribute("cy")}))'):
        a=areas[m['name']]['democratic_share'];left=55;right=frame['w']-25;top=40;bottom=frame['h']-75
        assert abs(m['x']-(left+sum(a)/3/100*(right-left)))<1e-6
        assert abs(m['y']-(bottom-((a[2]-a[0])+100)/200*(bottom-top)))<1e-6
    page.select_option('#borough','Queens')
    expect(page.locator('#dotCountyMap path')).to_have_count(sum(r['state']=='Queens' for r in areas.values()))
    page.locator('#patternChart circle').first.click()
    selected=page.locator('#patternChart .is-selected').get_attribute('data-precinct')
    expect(page.locator('#name')).to_have_text(selected)
    expect(page.locator('#votes')).to_contain_text('Andrew Cuomo + Curtis Sliwa')
    expect(page.locator('#votes')).to_contain_text('Estimated')
    expect(page.locator('#votes')).to_contain_text('Reported')
    page.locator('#patternChart .is-selected').focus();page.keyboard.press('ArrowRight')
    expect(page.locator('#patternChart .is-selected')).to_have_count(1)
    page.reload();expect(page.locator('#status')).to_contain_text('2017 and 2025 estimated.',timeout=30000)
    expect(page.locator('#borough')).to_have_value('Queens');expect(page.locator('#viewPatterns')).to_have_attribute('aria-pressed','true')
    page.select_option('#borough','all');page.click('#viewGroups')
    incomplete=next(n for n,r in areas.items() if not r['eligible'])
    page.select_option('#precinct',incomplete);expect(page.locator('#badge')).to_have_text('Incomplete history')
    expect(page.locator('#chart .is-selected')).to_have_count(1)
    page.click('#legend [data-group="none"]');expect(page.locator('#chart circle')).to_have_count(552)
    page.click('#viewPatterns');expect(page.locator('#patternChart circle')).to_have_count(0);expect(page.locator('#empty')).to_be_visible()
    expect(page.locator('#dotCountyMap .is-selected')).to_have_count(1)
    page.click('#reset');expect(page.locator('#chart circle')).to_have_count(5697)
    sensitive=next(n for n,r in areas.items() if r['eligible'] and r['allocation_sensitive'])
    page.select_option('#precinct',sensitive);expect(page.locator('#combined')).to_contain_text('Sensitive to allocation')
    page.fill('#search','no matching place');expect(page.locator('#empty')).to_be_visible();expect(page.locator('#chart circle')).to_have_count(0)
    page.click('#reset');out=ROOT/'tmp/nyc-history-dots';out.mkdir(parents=True,exist_ok=True)
    page.locator('#dots').screenshot(path=str(out/'desktop-groups.png'));page.click('#viewPatterns');page.locator('#dots').screenshot(path=str(out/'desktop-patterns.png'))
    page.select_option('#borough','Manhattan')
    for width in [320,390,768]:
        page.set_viewport_size({'width':width,'height':900});page.wait_for_timeout(300)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
        page.locator('#dots').screenshot(path=str(out/f'patterns-{width}.png'))
        page.click('#viewGroups');page.locator('#dots').screenshot(path=str(out/f'groups-{width}.png'))
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
        page.click('#viewPatterns')
    assert not errors,errors;browser.close()
finally:server.shutdown()
print('PASS 2 methods × 5 group counts × 2 palettes, all 5,697 dots/map marks and 5,145 plot coordinates; linked selection, estimates/coverage/sensitivity, keyboard, URL, filters/reset and mobile layouts')
