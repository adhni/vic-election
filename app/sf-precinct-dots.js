/* San Francisco 2024: citywide RCV eliminations, mapped by precinct. Bismillah. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id), esc=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=n=>n.toLocaleString('en-US'), pct=n=>n.toFixed(1)+'%';
  const defaults={round:1,district:'all',group:'all',q:'',selected:''}, state={...defaults};
  let data,geo,records,round,visible=[],dots=new Map(),map=new Map();
  function read(){const p=new URLSearchParams(location.search);const r=Number(p.get('round'));state.round=Number.isInteger(r)&&r>=1&&r<=14?r:1;state.district=[...$('district').options].some(o=>o.value===p.get('district'))?p.get('district'):'all';state.group=p.get('group')||'all';state.q=p.get('q')||'';state.selected=p.get('precinct')||'';}
  function url(replace=false){const p=new URLSearchParams({round:state.round});for(const key of ['district','group','q'])if(state[key]&&state[key]!=='all')p.set(key,state[key]);if(state.selected)p.set('precinct',state.selected);history[replace?'replaceState':'pushState'](null,'','?'+p);}
  function color(r){if(!data.colors[r.leader])return '#a6a6a6';const margin=r.continuing?100*r.margin/r.continuing:0,t=margin<=2?.12:margin<=5?.32:margin<=10?.54:margin<=20?.77:1;return '#'+[1,3,5].map(i=>Math.round(255+(parseInt(data.colors[r.leader].slice(i,i+2),16)-255)*t).toString(16).padStart(2,'0')).join('');}
  function description(n){const r=records[n];return r.continuing?`${r.leader==='Tied local leaders'?'Tied local leads':r.leader+' leads'} · ${(100*r.margin/r.continuing).toFixed(1)} point margin · ${fmt(r.continuing)} continuing votes`:'No continuing mayoral votes';}
  function select(n,push=true){
    if(!visible.includes(n))return;state.selected=n;
    for(const collection of [dots,map])for(const [name,node] of collection){node.classList.toggle('is-selected',name===n);node.setAttribute('aria-pressed',name===n);node.tabIndex=name===n?0:-1;}
    $('precinct').value=n;const area=data.precincts[n],r=records[n],previous=state.round>1?area.rounds[state.round-2]:null;
    $('name').textContent=n;$('badge').textContent=r.leader;$('badge').style.setProperty('--story-color',color(r));$('summary').textContent=`${area.neighborhood} · ${area.state} · Round ${state.round}. `+description(n);
    $('votes').innerHTML='<table><thead><tr><th scope="col">Candidate</th><th scope="col">Votes</th><th scope="col">Share</th></tr></thead><tbody>'+Object.entries(r.votes).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).map(([c,v])=>{
      const change=previous?v-(previous.votes[c]||0):0;
      return `<tr><th scope="row">${esc(c)}${round.eliminated.includes(c)?'<small>Eliminated after this round</small>':''}</th><td>${fmt(v)}${previous&&change?`<small>${change>0?'+':''}${fmt(change)}</small>`:''}</td><td>${r.continuing?pct(100*v/r.continuing):'—'}</td></tr>`;
    }).join('')+'</tbody></table>'+`<ul class="precinct-facts"><li>${fmt(r.continuing)} votes still counting</li><li>${fmt(r.exhausted)} exhausted ballots</li><li>${fmt(r.overvotes)} overvoted ballots</li><li>${fmt(r.blanks)} blank / no usable ranking</li><li>${fmt(r.cvr_ballots)} CVR ballot records</li></ul>`;
    const t=area.turnout;
    $('votes').innerHTML+=t?`<p>Election turnout (statement of vote): <strong>${(100*t.ballots/t.registered).toFixed(2)}%</strong> · ${fmt(t.ballots)} ballots cast / ${fmt(t.registered)} registered voters. This is fixed across rounds.</p>`:'<p class="story-quality">Statement-of-vote row withheld. These round counts come from public CVR records. Election turnout is unavailable.</p>';
    $('combined').textContent='Reconstructed precinct count, not an official precinct round report. Shares use continuing votes in this round. Eliminations follow the citywide count. '+(state.round===14?'Daniel Lurie won citywide; this precinct may have a different local leader.':'Candidates shown remain in this counting round.');
    $('source').href=`index.html?year=sf-mayor-2024-round-${state.round}&geo=precinct&district=${encodeURIComponent(n)}`;if(push)url();
  }
  function tip(e,n){const t=$('tooltip'),r=e.currentTarget.getBoundingClientRect();t.textContent=n+' · Round '+state.round+' · '+description(n);t.hidden=false;t.style.left=Math.max(8,Math.min(innerWidth-340,(e.clientX||r.x)+12))+'px';t.style.top=Math.max(8,Math.min(innerHeight-t.offsetHeight-8,(e.clientY||r.y)+12))+'px';}
  function bind(node,n,source){
    node.addEventListener('click',()=>select(n));node.addEventListener('pointermove',e=>tip(e,n));node.addEventListener('pointerleave',()=>$('tooltip').hidden=true);node.addEventListener('focus',e=>tip(e,n));node.addEventListener('blur',()=>$('tooltip').hidden=true);
    node.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();select(n);}if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(e.key)){e.preventDefault();const collection=source==='map'?map:dots,available=source==='map'?visible:[...dots.keys()];let i=available.indexOf(n);i=e.key==='Home'?0:e.key==='End'?available.length-1:Math.max(0,Math.min(available.length-1,i+(['ArrowLeft','ArrowUp'].includes(e.key)?-1:1)));select(available[i]);collection.get(available[i])?.focus();}});
  }
  function render(){
    $('tooltip').hidden=true;$('content').hidden=false;round=data.rounds[state.round-1];records=Object.fromEntries(Object.entries(data.precincts).map(([n,a])=>[n,a.rounds[state.round-1]]));
    $('round').value=state.round;$('district').value=state.district;$('search').value=state.q;$('previousRound').disabled=state.round===1;$('nextRound').disabled=state.round===14;
    const ranked=Object.entries(round.votes).sort((a,b)=>b[1]-a[1]);
    $('roundTitle').textContent=`Citywide · Round ${state.round} of 14`;
    $('roundSummary').textContent=`${ranked[0][0]} ${state.round===14?'wins':'leads'} citywide: ${fmt(ranked[0][1])} votes (${(100*ranked[0][1]/round.continuing).toFixed(2)}%). `+(round.eliminated.length?`${round.eliminated.join(', ')} is eliminated after this round.`:'Final count: Daniel Lurie defeats London Breed.');
    for(const key of ['continuing','exhausted','overvotes','blanks'])$(key).textContent=fmt(round[key]);
    const groups=[...round.active.filter(c=>Object.values(records).some(r=>r.leader===c)),...['Tied local leaders','No continuing votes'].filter(c=>Object.values(records).some(r=>r.leader===c))];
    if(state.group!=='all'&&!groups.includes(state.group))state.group='all';
    const matching=Object.keys(records).sort().filter(n=>(state.district==='all'||data.precincts[n].state===state.district)&&(n+' '+data.precincts[n].neighborhood).toLowerCase().includes(state.q.trim().toLowerCase()));
    visible=matching.filter(n=>state.group==='all'||records[n].leader===state.group);
    $('legend').innerHTML=['all',...groups].map(g=>`<button type="button" data-group="${esc(g)}" aria-pressed="${g===state.group}">${g==='all'?'':`<span class="dot" style="background:${data.colors[g]||'#a6a6a6'}"></span>`}${esc(g==='all'?'All precincts':g)}${g==='all'?'':' · '+fmt(matching.filter(n=>records[n].leader===g).length)}</button>`).join('');
    $('legend').querySelectorAll('button').forEach(b=>b.onclick=()=>{state.group=b.dataset.group;render();url();});
    const mapped=Object.fromEntries(Object.entries(data.precincts).filter(([,r])=>state.district==='all'||r.state===state.district).map(([n,r])=>[n,{state:state.district==='all'?'San Francisco':r.state}]));
    map=ElectionCountyMap.draw($('dotCountyMap'),geo,mapped,state.district==='all'?'San Francisco':state.district);const active=new Set(visible);
    for(const [n,node] of map){const valid=active.has(n);node.style.fill=valid?color(records[n]):'#e8e8e5';node.classList.toggle('is-filtered',!valid);node.setAttribute('aria-label',n+' · '+description(n));node.setAttribute('aria-disabled',!valid);node.tabIndex=-1;if(valid)bind(node,n,'map');}
    $('chart').innerHTML=groups.filter(g=>state.group==='all'||state.group===g).map(g=>{const names=visible.filter(n=>records[n].leader===g);return `<section class="dot-lane" data-group="${esc(g)}"><h3>${esc(g)}</h3><p class="lane-count">${fmt(names.length)} <span>precincts</span></p><p class="lane-share">${matching.length?(100*names.length/matching.length).toFixed(1):'0.0'}% of matching precincts</p><svg role="group" aria-label="${esc(g)} precinct dots"></svg></section>`;}).join('');dots=new Map();
    $('chart').querySelectorAll('.dot-lane').forEach(lane=>{const names=visible.filter(n=>records[n].leader===lane.dataset.group),svg=lane.querySelector('svg'),w=Math.max(100,lane.clientWidth-20),cols=Math.max(1,Math.floor(w/12));svg.setAttribute('viewBox',`0 0 ${w} ${Math.max(12,Math.ceil(names.length/cols)*12)}`);svg.innerHTML=names.map((n,i)=>`<circle class="county-dot" data-precinct="${esc(n)}" cx="${6+i%cols*12}" cy="${6+Math.floor(i/cols)*12}" r="4" fill="${color(records[n])}" role="button" tabindex="-1" aria-pressed="false" aria-label="${esc(n+' · '+description(n))}"></circle>`).join('');svg.querySelectorAll('circle').forEach(node=>{const n=node.dataset.precinct;dots.set(n,node);bind(node,n,'dots');});});
    $('precinct').innerHTML=visible.map(n=>`<option>${esc(n)}</option>`).join('');$('empty').hidden=visible.length>0;$('status').textContent=`${fmt(visible.length)} of 514 mapped precincts shown · Round ${state.round} of 14 · 3 CVR records without a precinct are included only in citywide totals.`;
    if(visible.length)select(visible.includes(state.selected)?state.selected:visible[0],false);else{for(const id of ['badge','summary','votes','combined'])$(id).textContent='';$('name').textContent='No matching precinct';$('source').removeAttribute('href');}
  }
  async function start(){try{
    const responses=await Promise.all([fetch('../data/sf_2024_mayor_rounds.json'),fetch('../data/sf_2024_mayor_precinct_boundaries.geojson')]);if(responses.some(r=>!r.ok))throw Error('Data unavailable');[data,geo]=await Promise.all(responses.map(r=>r.json()));
    $('round').innerHTML=data.rounds.map(r=>`<option value="${r.round}">Round ${r.round}${r.round===1?' · First choices':r.round===14?' · Final count':''}</option>`).join('');$('district').innerHTML='<option value="all">All districts</option>'+Array.from({length:11},(_,i)=>`<option>District ${String(i+1).padStart(2,'0')}</option>`).join('');
    read();render();url(true);$('round').onchange=()=>{state.round=+$('round').value;render();url();};$('district').onchange=()=>{state.district=$('district').value;render();url();};$('search').oninput=()=>{state.q=$('search').value;render();url(true);};$('precinct').onchange=()=>select($('precinct').value);
    for(const [id,delta] of [['previousRound',-1],['nextRound',1]])$(id).onclick=()=>{state.round=Math.max(1,Math.min(14,state.round+delta));render();url();};$('reset').onclick=()=>{Object.assign(state,defaults);render();url();};addEventListener('popstate',()=>{read();render();});let timer;addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(render,180);});
  }catch(e){$('status').textContent='Could not load SF ranked-choice counts. '+e.message;}}
  start();
})();
