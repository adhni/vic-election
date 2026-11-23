/* Boston candidate histories, with explicit boundary screening. Bismillah. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = n => n.toLocaleString('en-US'), pct = n => n === null ? 'Unavailable' : n.toFixed(1) + '%';
  const defaults = {coverage:'screened',k:3,ward:'all',q:'',group:'all',selected:'',view:'groups',xYear:'2017',yYear:'2021'};
  const state = {...defaults};
  let data, geo, model, visible = [], dots = new Map(), map = new Map();
  function read() {
    const p = new URLSearchParams(location.search);
    Object.assign(state, defaults);
    state.coverage = p.get('coverage') === 'exploratory' ? 'exploratory' : 'screened';
    state.k = [2,3,4,5,7].includes(+p.get('k')) ? +p.get('k') : 3;
    state.ward = [...$('ward').options].some(o => o.value === p.get('ward')) ? p.get('ward') : 'all';
    for (const key of ['q','group','selected']) state[key] = p.get(key === 'selected' ? 'precinct' : key) || defaults[key];
    state.view = p.get('view') === 'patterns' ? 'patterns' : 'groups';
    for (const key of ['xYear','yYear']) if (['2013','2017','2021'].includes(p.get(key))) state[key] = p.get(key);
  }
  function url(replace = false) {
    const p = new URLSearchParams({coverage:state.coverage,k:state.k});
    for (const key of ['ward','q','group','view','xYear','yYear']) if (state[key] !== defaults[key]) p.set(key,state[key]);
    if (state.selected) p.set('precinct',state.selected);
    history[replace ? 'replaceState' : 'pushState'](null,'','?' + p);
  }
  const groupOf = n => String(model.assignments[n] || 'none');
  const color = n => model.assignments[n] ? model.groups[model.assignments[n] - 1].color : '#a6a6a6';
  function reasons(n) {
    const r = data.areas[n];
    return state.coverage === 'screened' ? r.exclusion_reasons : r.exclusion_reasons.filter(s => s.startsWith('No votes'));
  }
  function description(n) {
    const r = data.areas[n];
    return groupOf(n) === 'none' ? 'Not grouped: ' + reasons(n).join(' ') :
      `Group ${groupOf(n)} · ${r.shares.map((v,i) => data.years[i] + ' ' + data.candidates[i].split(' ').at(-1) + ' ' + pct(v)).join(' · ')}`;
  }
  function select(n, push = true) {
    if (!visible.includes(n)) return;
    state.selected = n;
    for (const collection of [dots,map]) for (const [name,node] of collection) {
      node.classList.toggle('is-selected',name === n); node.setAttribute('aria-pressed',name === n); node.tabIndex = name === n ? 0 : -1;
    }
    if (!dots.has(n) && dots.size) dots.values().next().value.tabIndex = 0;
    $('precinct').value = n; $('name').textContent = n;
    $('badge').textContent = groupOf(n) === 'none' ? 'Not grouped' : 'Group ' + groupOf(n);
    $('badge').style.setProperty('--story-color',color(n));
    const r = data.areas[n];
    $('summary').textContent = groupOf(n) === 'none' ? reasons(n).join(' ') : 'Group average: ' + model.groups[model.assignments[n] - 1].label;
    $('votes').innerHTML = '<table class="history-table"><thead><tr><th scope="col">Year</th><th scope="col">Candidate</th><th scope="col">Opponent</th></tr></thead><tbody>' + data.years.map((y,i) => {
      const v = r.votes[y], share = r.shares[i];
      return `<tr><th scope="row">${y}</th><td>${pct(share)}<small>${esc(data.candidates[i])}<br>${fmt(v[data.candidates[i]])} votes</small></td><td>${pct(share === null ? null : 100-share)}<small>${esc(data.opponents[i])}<br>${fmt(v[data.opponents[i]])} votes</small></td></tr>`;
    }).join('') + '</tbody></table>';
    const checks = Object.entries(r.boundary_audit).map(([year,a]) => `${year.replace('_','–')} map: ${a.present ? (100*a.minimum_coverage).toFixed(2) + '% minimum shape coverage' : 'no matching code'}.`);
    $('combined').textContent = (r.boundary_pass ? 'Passes the map agreement screen. ' : 'Does not pass the map agreement screen. ') + checks.join(' ') + ' This is not verification of election-day boundaries. Votes are reported under the same code; none are reallocated.';
    $('source').href = 'boston-precinct-dots.html?year=2021&precinct=' + encodeURIComponent(n);
    if (push) url();
  }
  function tip(e,n) {
    const t = $('tooltip'), b = e.currentTarget.getBoundingClientRect(); t.textContent = n + ' · ' + description(n); t.hidden = false;
    t.style.left = Math.max(8,Math.min(innerWidth-340,(e.clientX || b.x)+12))+'px';
    t.style.top = Math.max(8,Math.min(innerHeight-t.offsetHeight-8,(e.clientY || b.y)+12))+'px';
  }
  function bind(node,n,source) {
    node.addEventListener('click',() => select(n)); node.addEventListener('pointermove',e => tip(e,n));
    node.addEventListener('pointerleave',() => $('tooltip').hidden = true); node.addEventListener('focus',e => tip(e,n));
    node.addEventListener('blur',() => $('tooltip').hidden = true);
    node.addEventListener('keydown',e => {
      if (['Enter',' '].includes(e.key)) {e.preventDefault();select(n);}
      if (['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(e.key)) {
        e.preventDefault(); const collection = source === 'map' ? map : dots;
        const available = source === 'map' ? visible : [...dots.keys()]; let i = available.indexOf(n);
        i = e.key === 'Home' ? 0 : e.key === 'End' ? available.length-1 : Math.max(0,Math.min(available.length-1,i+(['ArrowLeft','ArrowUp'].includes(e.key)?-1:1)));
        select(available[i]); collection.get(available[i])?.focus();
      }
    });
  }
  function mark(n,x,y) {return `<circle class="county-dot" data-precinct="${esc(n)}" cx="${x}" cy="${y}" r="4" fill="${color(n)}" role="button" tabindex="-1" aria-pressed="false" aria-label="${esc(n+' · '+description(n))}"></circle>`;}
  function renderPatterns() {
    const svg = $('patternChart'), w = Math.max(260,svg.clientWidth), h = w < 500 ? 420 : 520, left = 45, right = w-22, top = 50, bottom = h-65;
    const x = v => left+v/100*(right-left), y = v => bottom-v/100*(bottom-top);
    const xi = data.years.indexOf(+state.xYear), yi = data.years.indexOf(+state.yYear);
    svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
    let html = `<text x="${left}" y="22">${state.yYear} · ${esc(data.candidates[yi])} (%)</text>`;
    for (const t of (w < 500 ? [0,50,100] : [0,25,50,75,100])) {
      html += `<line class="${t===50?'plot-mid':'plot-grid'}" x1="${left}" x2="${right}" y1="${y(t)}" y2="${y(t)}"></line><text x="${left-7}" y="${y(t)+5}" text-anchor="end">${t}</text>`;
      html += `<line class="${t===50?'plot-mid':'plot-grid'}" x1="${x(t)}" x2="${x(t)}" y1="${top}" y2="${bottom}"></line><text x="${x(t)}" y="${bottom+22}" text-anchor="middle">${t}%</text>`;
    }
    html += `<text x="${(left+right)/2}" y="${h-10}" text-anchor="middle">${state.xYear} · ${esc(data.candidates[xi])} (%)</text>`;
    html += visible.filter(n => groupOf(n) !== 'none').map(n => mark(n,x(data.areas[n].shares[xi]),y(data.areas[n].shares[yi]))).join(''); svg.innerHTML = html;
  }
  function render() {
    $('tooltip').hidden = true; $('content').hidden = false; model = data.models[state.coverage][state.k];
    if (state.group !== 'none' && !model.groups.some(g => String(g.id) === state.group)) state.group = 'all';
    for (const id of ['coverage','ward','xYear','yYear']) $(id).value = state[id]; $('groups').value = state.k; $('search').value = state.q;
    const matching = Object.keys(data.areas).sort().filter(n => (state.ward === 'all' || data.areas[n].state === state.ward) && (n+' '+data.areas[n].code).toLowerCase().includes(state.q.trim().toLowerCase()));
    visible = matching.filter(n => state.group === 'all' || groupOf(n) === state.group);
    const grouped = Object.keys(model.assignments).length;
    $('qualityNote').textContent = state.coverage === 'screened' ? `${grouped} of ${data.summary.total} precincts pass the conservative map agreement check and have usable votes. This small subset is not representative of Boston. The other ${data.summary.total-grouped} stay grey. Passing the check does not prove identical election-day boundaries.` : `Exploratory: ${grouped} precincts have usable votes under matching codes; boundaries may differ between elections. Only ${data.summary.screened} also pass the map agreement screen. One precinct has no main-candidate votes in 2017. These are provisional histories.`;
    const groups = [...model.groups.map(g => ({...g,id:String(g.id)})),{id:'none',label:'Not grouped'}];
    $('legend').innerHTML = [{id:'all',label:'All groups'},...groups].map(g => `<button type="button" data-group="${g.id}" aria-pressed="${state.group===g.id}">${g.id === 'all' ? 'All groups' : (g.id === 'none' ? 'Not grouped' : 'Group '+g.id)+' · '+fmt(matching.filter(n => groupOf(n)===g.id).length)}</button>`).join('');
    $('legend').querySelectorAll('button').forEach(b => b.onclick = () => {state.group=b.dataset.group;render();url();});
    const mapped = Object.fromEntries(Object.entries(data.areas).filter(([,r]) => state.ward==='all'||r.state===state.ward).map(([n,r]) => [n,{state:state.ward==='all'?'Boston':r.state}]));
    map = ElectionCountyMap.draw($('dotCountyMap'),geo,mapped,state.ward==='all'?'Boston':state.ward); const active = new Set(visible);
    for (const [n,node] of map) {const valid=active.has(n);node.style.fill=valid?color(n):'#e8e8e5';node.classList.toggle('is-filtered',!valid);node.setAttribute('aria-label',n+' · '+description(n));node.setAttribute('aria-disabled',!valid);node.tabIndex=-1;if(valid)bind(node,n,'map');}
    $('chart').hidden=state.view!=='groups';$('patternWrap').hidden=state.view!=='patterns';
    $('viewGroups').setAttribute('aria-pressed',state.view==='groups');$('viewPatterns').setAttribute('aria-pressed',state.view==='patterns');
    $('chart').innerHTML='';$('patternChart').innerHTML='';dots=new Map();
    if (state.view==='groups') {
      $('chart').innerHTML=groups.filter(g => state.group==='all'||state.group===g.id).map(g => {
        const names=visible.filter(n => groupOf(n)===g.id);
        const detail=g.id==='none'?'Outside the selected grouping rule':g.centroid.map((v,i) => `<span>${data.years[i]} ${esc(data.candidates[i].split(' ').at(-1))}: ${pct(v)}</span>`).join('');
        return `<section class="dot-lane" data-group="${g.id}"><h3>${g.id==='none'?'Not grouped':'Group '+g.id}</h3><p class="lane-count">${fmt(names.length)} <span>precincts</span></p><p class="history-profile">${detail}</p><svg role="group" aria-label="${g.id==='none'?'Not grouped':'Group '+g.id} precinct dots"></svg></section>`;
      }).join('');
      $('chart').querySelectorAll('.dot-lane').forEach(lane => {const names=visible.filter(n=>groupOf(n)===lane.dataset.group),svg=lane.querySelector('svg'),w=Math.max(100,lane.clientWidth-20),cols=Math.max(1,Math.floor(w/12));svg.setAttribute('viewBox',`0 0 ${w} ${Math.max(12,Math.ceil(names.length/cols)*12)}`);svg.innerHTML=names.map((n,i)=>mark(n,6+i%cols*12,6+Math.floor(i/cols)*12)).join('');});
    } else renderPatterns();
    document.querySelectorAll('#chart circle,#patternChart circle').forEach(node => {const n=node.dataset.precinct;dots.set(n,node);bind(node,n,'dots');});
    $('precinct').innerHTML=visible.map(n=>`<option>${esc(n)}</option>`).join('');
    $('empty').hidden=state.view==='patterns'?dots.size>0:visible.length>0;
    $('empty').textContent=visible.length?'No grouped precincts to plot. Use the map or picker to inspect excluded areas.':'No precincts match these filters.';
    $('status').textContent=`${fmt(visible.length)} of ${data.summary.total} precincts shown · ${grouped} grouped citywide · ${state.k} groups · ${state.coverage==='screened'?'map agreement screen':'provisional code matches'}.`;
    if(visible.length)select(visible.includes(state.selected)?state.selected:visible.find(n=>groupOf(n)!=='none')||visible[0],false);
    else {for(const id of ['badge','summary','votes','combined'])$(id).textContent='';$('name').textContent='No matching precinct';$('source').removeAttribute('href');}
  }
  async function start() {
    try {
      const responses=await Promise.all([fetch('../data/boston_history_clusters.json'),fetch('../data/boston_historical_precinct_boundaries.geojson')]);
      if(responses.some(r=>!r.ok))throw Error('Data unavailable');[data,geo]=await Promise.all(responses.map(r=>r.json()));
      $('ward').innerHTML='<option value="all">All wards</option>'+Array.from({length:22},(_,i)=>`<option>Ward ${String(i+1).padStart(2,'0')}</option>`).join('');
      read();render();url(true);
      for(const id of ['coverage','ward','xYear','yYear'])$(id).onchange=()=>{state[id]=$(id).value;if(id==='coverage')state.group='all';render();url();};
      $('groups').onchange=()=>{state.k=+$('groups').value;state.group='all';render();url();};
      $('search').oninput=()=>{state.q=$('search').value;render();url(true);};$('precinct').onchange=()=>select($('precinct').value);
      $('viewGroups').onclick=()=>{state.view='groups';render();url();};$('viewPatterns').onclick=()=>{state.view='patterns';render();url();};
      $('reset').onclick=()=>{Object.assign(state,defaults);render();url();};addEventListener('popstate',()=>{read();render();});
      let timer;addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(render,180);});
    } catch(e) {$('status').textContent='Could not load Boston voting groups. '+e.message;}
  }
  start();
})();
