/* One county, one dot. Bismillah. Uses the same models as the county map. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const esc = value => String(value).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  const fmt = new Intl.NumberFormat("en-US");
  const pct = value => `${Number(value).toFixed(1)}%`;
  const initial = () => ({k:5, method:"similarity", measure:"counties", region:"all", group:"all", colors:"party", q:"", view:"groups", metric:"bachelors_plus_pct", outcome:"2024", party:"democratic", county:"Wayne County, Michigan"});
  let data, names, model, population, populationLayout, demographics, demographicNames = [], geography, mapRegion, mapNodes = new Map(), visible = [], state = initial(), resizeTimer, searchTimer;
  const nodes = new Map();
  const countyMarks = new Map();
  const compact = new Intl.NumberFormat("en-US",{notation:"compact",maximumFractionDigits:1});
  const mean = values => values.reduce((a,b) => a+b, 0) / values.length;
  const average = name => mean(data.counties[name].democratic_share);
  const change = name => data.counties[name].democratic_share.at(-1) - data.counties[name].democratic_share[0];
  const color = group => {
    if (state.colors === "groups") return group.color;
    const share = group.mean_democratic_share ?? group.color_share;
    const end = share >= 50 ? [33,102,172] : [178,24,43];
    const strength = Math.min(1, Math.abs(share-50)/25);
    return "#" + end.map(value => Math.round(166+(value-166)*strength).toString(16).padStart(2,"0")).join("");
  };
  const groupDescription = group => {
    if (!group.size) return "No counties in this group";
    if (group.label === "Swing / competitive") return "About evenly split on average";
    const share = group.mean_democratic_share;
    return `${Math.round(share < 50 ? 100-share : share)}% ${share < 50 ? "Republican" : "Democratic"} on average`;
  };

  const demographicMetric = () => demographics.metrics[state.metric];
  const demographicValue = name => ElectionCountyDemographics.demographicValue(demographics,data.counties,name,state.metric);
  const demographicVote = name => ElectionCountyDemographics.votingValue(data.counties[name],data.years,state.outcome,state.party);
  const demographicFormat = (value,tick=false) => ElectionCountyDemographics.format(value,demographicMetric(),tick);
  const demographicVoteLabel = () => `${ElectionCountyDemographics.outcomes[state.outcome]} · ${state.party === "democratic" ? "Democratic" : "Republican"}`;
  const demographicVoteFormat = value => `${state.outcome.startsWith("change-") ? `${value > 0 ? "+" : ""}${value.toFixed(1)} points` : pct(value)}`;

  function readUrl() {
    const p = new URLSearchParams(location.search);
    state = initial();
    if (p.get("measure") === "population") state.measure = "population";
    if (p.get("method") === "bands") state.method = "bands";
    if (data.candidate_k.includes(Number(p.get("k")))) state.k = Number(p.get("k"));
    if (names.some(name => data.counties[name].state === p.get("region"))) state.region = p.get("region");
    if (/^[1-7]$/.test(p.get("group")) && Number(p.get("group")) <= state.k) state.group = p.get("group");
    if (p.get("colors") === "groups") state.colors = "groups";
    if (p.get("view") === "patterns" && state.measure !== "population") state.view = "patterns";
    if (Object.hasOwn(demographics.metrics,p.get("metric"))) state.metric=p.get("metric");
    if (Object.hasOwn(ElectionCountyDemographics.outcomes,p.get("outcome"))) state.outcome=p.get("outcome");
    if (p.get("party") === "republican") state.party="republican";
    if (p.get("view") === "demographics") {state.view="demographics";state.measure="counties";}
    state.q = (p.get("q") || "").slice(0,150);
    if (names.includes(p.get("county"))) state.county = p.get("county");
  }

  function writeUrl(replace=false) {
    const p = new URLSearchParams({k:state.k, view:state.view, colors:state.colors});
    if (state.view === "demographics") {p.set("metric",state.metric);p.set("outcome",state.outcome);p.set("party",state.party);}
    if (state.measure === "population") p.set("measure", "population");
    if (state.method === "bands") p.set("method", "bands");
    if (state.county) p.set("county",state.county);
    if (state.region !== "all") p.set("region",state.region);
    if (state.group !== "all") p.set("group",state.group);
    if (state.q) p.set("q",state.q);
    history[replace ? "replaceState" : "pushState"]({},"",`${location.pathname}?${p}`);
  }

  function dot(name, x, y, radius=3, detail="") {
    const group = model.groups[model.assignments[name].group-1];
    const label = `${name}, ${group.label || `Group ${group.id}`}, ${detail || `${pct(data.counties[name].democratic_share.at(-1))} Democratic in 2024`}`;
    return `<circle class="county-dot${name === state.county ? " is-selected" : ""}" data-county="${esc(name)}" cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" r="${radius}" fill="${color(group)}" role="button" tabindex="${name === state.county ? 0 : -1}" aria-label="${esc(label)}" aria-pressed="${name === state.county}"></circle>`;
  }

  function indexDots() {
    nodes.clear();countyMarks.clear();
    document.querySelectorAll(".county-dot,.population-dot").forEach(node => {
      const name=node.dataset.county;
      if (!nodes.has(name)) nodes.set(name,node);
      if (!countyMarks.has(name)) countyMarks.set(name,[]);
      countyMarks.get(name).push(node);
    });
    if (!nodes.has(state.county) && nodes.size) nodes.values().next().value.setAttribute("tabindex","0");
  }

  function populationDot(name,x,y,index,first) {
    const group=model.groups[model.assignments[name].group-1];
    const selected=name===state.county;
    const label=`About ${fmt.format(Math.round(populationLayout.peoplePerDot))} residents, attributed to ${name} after rounding, ${group.label || `Group ${group.id}`}`;
    return `<circle class="population-dot${selected ? " is-selected" : ""}" data-county="${esc(name)}" data-unit="${index}" cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" r="3" fill="${color(group)}" role="button" tabindex="${selected && first ? 0 : -1}" aria-label="${esc(label)}" aria-pressed="${selected}"></circle>`;
  }

  function renderMap() {
    if (mapRegion !== state.region) {
      mapNodes=ElectionCountyMap.draw($("dotCountyMap"),geography,data.counties,state.region);
      mapRegion=state.region;
    }
    const matching=new Set(visible);
    mapNodes.forEach((node,name) => {
      const group=model.groups[model.assignments[name].group-1];
      const matches=matching.has(name);
      node.setAttribute("fill",matches ? color(group) : "#e8e8e5");
      node.classList.toggle("is-filtered",!matches);
      node.classList.toggle("is-selected",name===state.county);
      node.setAttribute("aria-pressed",String(name===state.county));
      node.setAttribute("aria-disabled",String(!matches));
      node.setAttribute("tabindex",name===state.county ? "0" : "-1");
      node.setAttribute("aria-label",`${name}, ${group.label || `Group ${group.id}`}${matches ? "" : ", outside current filters"}`);
    });
    $("countyMapLegend").innerHTML=$("dotLegend").innerHTML;
    $("countyMapNote").textContent=`${state.region === "all" ? "Hawaii is shown separately. " : `${state.region} · `}Pale counties don’t match the filters. Alaska, Connecticut and DC aren’t included. Colours show the same groups as the dots.`;
  }

  function renderGroupDots() {
    $("patternChart").innerHTML = "";
    $("demographicChart").innerHTML = "";
    const groups = model.groups.filter(group => state.group === "all" || group.id === Number(state.group));
    $("groupDotChart").style.setProperty("--group-columns",groups.length>5 ? 4 : groups.length);
    const populationMode=state.measure === "population";
    $("groupDotChart").classList.toggle("population-mode",populationMode);
    $("groupDotChart").innerHTML = groups.map(group => {
      const members=visible.filter(name => model.assignments[name].group===group.id);
      const filtered=state.region!=="all" || state.q.trim();
      const residents=members.reduce((sum,name) => sum+populationLayout.residents[name],0);
      const dotCount=populationMode ? members.reduce((sum,name) => sum+populationLayout.allocations[name],0) : members.length;
      const count=populationMode ? residents : members.length;
      const unit=populationMode ? "residents" : "counties";
      const detail=populationMode ? `${(100*residents/populationLayout.totalPopulation).toFixed(1)}% of included population · ${fmt.format(dotCount)} dots` : filtered ? `${fmt.format(group.size)} nationwide` : `${(100*group.size/names.length).toFixed(1)}% of all counties`;
      return `<section class="dot-lane" data-group="${group.id}"><h3>${esc(group.label || `Group ${group.id}`)}</h3><p class="lane-count">${fmt.format(count)} <span>${unit}</span></p><p class="lane-share">${populationMode ? "County voting average: " : ""}${groupDescription(group)}<br>${detail}</p><svg role="group" aria-label="${esc(group.label || `Group ${group.id}`)}, ${fmt.format(count)} ${unit}, ${fmt.format(dotCount)} ${populationMode ? "population" : "county"} dots"></svg></section>`;
    }).join("");
    $("groupDotChart").querySelectorAll(".dot-lane").forEach(lane => {
      const svg=lane.querySelector("svg");
      const members=visible.filter(name => model.assignments[name].group===Number(lane.dataset.group));
      const tickets=populationMode ? members.flatMap(name => Array(populationLayout.allocations[name]).fill(name)) : members;
      const width=Math.max(60,svg.clientWidth);
      const columns=Math.max(1,Math.floor((width-8)/9));
      const height=Math.max(20,Math.ceil(tickets.length/columns)*9+8);
      svg.setAttribute("viewBox",`0 0 ${width} ${height}`);
      const seen=new Set();
      svg.innerHTML=tickets.map((name,i) => {
        const x=6+(i%columns)*9,y=6+Math.floor(i/columns)*9;
        if (!populationMode) return dot(name,x,y);
        const first=!seen.has(name);seen.add(name);
        return populationDot(name,x,y,i,first);
      }).join("");
    });
  }

  function renderPatterns() {
    $("demographicChart").innerHTML = "";
    $("groupDotChart").innerHTML = "";
    const svg = $("patternChart");
    const width = Math.max(280,svg.clientWidth), height = width < 500 ? 410 : 550;
    const left=58, right=width-24, top=38, bottom=height-70;
    const extent=Math.ceil(Math.max(10,...names.map(name => Math.abs(change(name))))/10)*10;
    const x=value => left+value/100*(right-left);
    const y=value => bottom-(value+extent)/(extent*2)*(bottom-top);
    svg.setAttribute("viewBox",`0 0 ${width} ${height}`);
    let html = `<title>County voting patterns</title><desc>Horizontal position is average Democratic support in five presidential elections. Vertical position is change in Democratic support from 2008 to 2024, in percentage points. One dot per matching county; dots may overlap.</desc><text x="${left}" y="20">Change since 2008 (points)</text>`;
    [-extent,-extent/2,0,extent/2,extent].forEach(value => {
      html+=`<line class="plot-grid${value===0 ? " plot-mid" : ""}" x1="${left}" x2="${right}" y1="${y(value)}" y2="${y(value)}"></line><text text-anchor="end" x="${left-9}" y="${y(value)+5}">${value>0 ? "+" : ""}${value}</text>`;
    });
    const ticks=width<500 ? [0,50,100] : [0,25,50,75,100];
    ticks.forEach(value => { html+=`<line class="plot-grid${value===50 ? " plot-mid" : ""}" x1="${x(value)}" x2="${x(value)}" y1="${top}" y2="${bottom}"></line><text text-anchor="middle" x="${x(value)}" y="${bottom+25}">${value}%</text>`; });
    html+=`<text x="${left}" y="${height-12}">Average Democratic support</text>`;
    html+=visible.filter(name => name!==state.county).map(name => dot(name,x(average(name)),y(change(name)),3.5)).join("");
    if (state.county) html+=dot(state.county,x(average(state.county)),y(change(state.county)),3.5);
    svg.innerHTML=html;
  }

  function renderDemographics() {
    $("groupDotChart").innerHTML="";$("patternChart").innerHTML="";
    const svg=$("demographicChart"),metric=demographicMetric();
    const width=Math.max(280,svg.clientWidth),height=width<500 ? 460 : 570;
    const left=60,right=width-28,top=42,bottom=height-90;
    const available=names.filter(name => demographicValue(name)!==null);
    demographicNames=visible.filter(name => demographicValue(name)!==null);
    const maximum=metric.unit === "percent" ? 100 : ElectionCountyDemographics.niceMax(Math.max(0,...available.map(demographicValue)));
    const swing=state.outcome.startsWith("change-");
    const extent=swing ? Math.max(5,Math.ceil(Math.max(0,...names.map(name => Math.abs(demographicVote(name))))/5)*5) : 100;
    const x=value => left+value/maximum*(right-left);
    const y=value => bottom-(value+(swing ? extent : 0))/(swing ? extent*2 : 100)*(bottom-top);
    svg.setAttribute("viewBox",`0 0 ${width} ${height}`);
    svg.setAttribute("aria-label",`${metric.label} against ${demographicVoteLabel()}; ${demographicNames.length} county dots`);
    let html=`<title>Demographics and voting</title><desc>${esc(metric.label)} horizontally; ${esc(demographicVoteLabel())} vertically. Each dot is a county. Estimates are from the 2020–2024 ACS, not individual voter data.</desc>`;
    const party=state.party === "democratic" ? "Democratic" : "Republican";
    html+=`<text x="${left}" y="22">${party} ${swing ? "swing (points)" : "support (%)"}</text>`;
    const yTicks=swing ? [-extent,-extent/2,0,extent/2,extent] : [0,25,50,75,100];
    yTicks.forEach(value => {
      html+=`<line class="plot-grid${value===(swing ? 0 : 50) ? " plot-mid" : ""}" x1="${left}" x2="${right}" y1="${y(value)}" y2="${y(value)}"></line><text text-anchor="end" x="${left-9}" y="${y(value)+5}">${swing && value>0 ? "+" : ""}${value}${swing ? "" : "%"}</text>`;
    });
    const xTicks=width<500 ? [0,maximum/2,maximum] : [0,maximum/4,maximum/2,maximum*3/4,maximum];
    xTicks.forEach(value => {html+=`<line class="plot-grid" x1="${x(value)}" x2="${x(value)}" y1="${top}" y2="${bottom}"></line><text text-anchor="middle" x="${x(value)}" y="${bottom+25}">${demographicFormat(value,true)}</text>`;});
    const label=`${metric.short_label}${metric.unit === "percent" ? " (%)" : metric.unit === "years" ? " (years)" : metric.unit.startsWith("USD") ? " ($)" : ""}`;
    const lines=[],limit=Math.max(20,Math.floor((right-left)/7));
    for (const word of label.split(" ")) {
      if (!lines.length || (lines.at(-1)+" "+word).length>limit) lines.push(word);
      else lines[lines.length-1]+=" "+word;
    }
    lines.forEach((line,i) => {html+=`<text text-anchor="middle" x="${(left+right)/2}" y="${bottom+52+i*18}">${esc(line)}</text>`;});
    const mark=name => dot(name,x(demographicValue(name)),y(demographicVote(name)),3.5,`${metric.short_label}: ${demographicFormat(demographicValue(name))}; ${demographicVoteLabel()}: ${demographicVoteFormat(demographicVote(name))}`);
    html+=demographicNames.filter(name => name!==state.county).map(mark).join("");
    if (demographicNames.includes(state.county)) html+=mark(state.county);
    svg.innerHTML=html;
    const missing=visible.length-demographicNames.length;
    $("demographicCoverage").textContent=`${fmt.format(demographicNames.length)} of ${fmt.format(visible.length)} matching counties plotted${missing ? `; ${fmt.format(missing)} missing estimates left out` : ""}. 2020–2024 ACS five-year estimates; point estimates shown without margins of error.`;
  }

  function renderStory() {
    const name=state.county;
    $("storyContent").hidden=!name;
    $("storyEmpty").hidden=Boolean(name);
    if (!name) return;
    const record=data.counties[name], shares=record.democratic_share;
    const group=model.groups[model.assignments[name].group-1];
    const last=shares.at(-1), margin=Math.abs(last-50)*2;
    $("storyName").textContent=name;
    $("storyDemographic").hidden=state.view!=="demographics";
    $("storyDemographic").textContent=`${demographicMetric().short_label}: ${demographicFormat(demographicValue(name))}. ${demographicVoteLabel()}: ${demographicVoteFormat(demographicVote(name))}.`;
    const represented=populationLayout.allocations[name];
    $("storyPopulation").textContent=`${fmt.format(populationLayout.residents[name])} residents · 2020–2024 ACS estimate.${state.measure === "population" ? ` ${represented ? `${fmt.format(represented)} population ${represented === 1 ? "dot" : "dots"} at this scale.` : "Too small for a whole population dot at this scale; still available on the map."}` : ""}`;
    $("storyGroup").textContent=`${group.label || `Group ${group.id}`} · ${groupDescription(group)}`;
    $("storyGroup").style.setProperty("--story-color",color(group));
    $("storySummary").textContent=margin < .0001 ? "The two parties tied here in 2024." : `${last>50 ? "Democrats" : "Republicans"} led by ${margin.toFixed(1)} points here in 2024.`;
    $("storyDemBar").style.width=`${last}%`;
    $("storyRepBar").style.width=`${100-last}%`;
    $("storyDemShare").textContent=`D ${pct(last)}`;
    $("storyRepShare").textContent=`R ${pct(100-last)}`;
    $("storyHistory").innerHTML=data.years.map((year,i) => `<tr><th scope="row">${year}</th><td>${pct(shares[i])}</td><td>${pct(100-shares[i])}</td></tr>`).join("");
    const delta=change(name);
    $("storyShift").textContent=Math.abs(delta)<.05 ? "Support for the two parties was much the same in 2008 and 2024." : `Democratic support ${delta>0 ? "rose" : "fell"} by ${Math.abs(delta).toFixed(1)} points between 2008 and 2024. Percentages count votes for Democrats and Republicans only.`;
    const p=new URLSearchParams({k:state.k,county:name,colors:state.colors});
    if (state.method === "bands") p.set("method","bands");
    $("storyMapLink").href=`county-clusters.html?${p}`;

  }

  function selectCounty(name, focus=false, source="dots") {
    if (!visible.includes(name)) return;
    for (const node of [...(countyMarks.get(state.county) || []),mapNodes.get(state.county)].filter(Boolean)) {
      node.classList.remove("is-selected");node.setAttribute("aria-pressed","false");node.setAttribute("tabindex","-1");
    }
    state.county=name;
    for (const node of [...(countyMarks.get(name) || []),mapNodes.get(name)].filter(Boolean)) {
      node.classList.add("is-selected");node.setAttribute("aria-pressed","true");
      node.setAttribute("tabindex",node===nodes.get(name) || node===mapNodes.get(name) ? "0" : "-1");
    }
    const mapNode=mapNodes.get(name);
    if (mapNode) mapNode.parentElement.appendChild(mapNode);
    if (state.measure !== "population" && nodes.has(name)) nodes.get(name).parentElement.appendChild(nodes.get(name));
    if (!nodes.has(name) && nodes.size) nodes.values().next().value.setAttribute("tabindex","0");
    if (focus) (source === "map" ? mapNodes : nodes).get(name)?.focus({preventScroll:true});
    $("dotCounty").value=name;
    renderStory();writeUrl();
    document.title=`${name} · County dots · Election Explorer`;
  }

  function render() {
    hideTooltip();
    model=ElectionVotingMethods.model(data,state.k,state.method);
    populationLayout=ElectionPopulationDots.distribution(model,data.counties,population);
    const populationMode=state.measure === "population";
    const demographicMode=state.view === "demographics";
    $("viewDemographics").setAttribute("aria-pressed",demographicMode);
    $("demographicControls").hidden=!demographicMode;
    $("demographicWrap").hidden=!demographicMode;
    $("demographicMetric").value=state.metric;$("demographicOutcome").value=state.outcome;$("demographicParty").value=state.party;
    $("demographicDefinition").textContent=`${demographicMetric().label}. Population measured: ${demographicMetric().source_universes.join("; ")}. ${demographicMetric().unit.startsWith("USD") ? "Dollar amounts are in 2024 inflation-adjusted dollars. " : ""}2020–2024 ACS five-year estimates.`;
    $("countCounties").setAttribute("aria-pressed",!populationMode);
    $("countPopulation").setAttribute("aria-pressed",populationMode);
    $("viewPatterns").disabled=populationMode;
    $("populationDotNote").hidden=!populationMode;
    $("populationDotNote").textContent=`Full view: ${fmt.format(populationLayout.totalDots)} equally sized dots. Each dot ≈ ${fmt.format(Math.round(populationLayout.peoplePerDot))} residents. Uses 2020–2024 ACS estimates, including children and nonvoters. Whole-dot rounding applies; filters keep the same scale. Switch to Counties for individual voting patterns.`;
    $("dotPageTitle").textContent=demographicMode ? "Demographics and voting." : populationMode ? "The people behind the counties." : "One county. One dot.";
    $("dotIntro").textContent=demographicMode ? "Compare any demographic measure with voting or swing. Each dot is a county, coloured by its voting group. Click a dot or a county on the map to explore it." : populationMode ? "See each group’s share of residents using the same 3,103 dots. More populated counties contribute more dots. Groups still describe how counties vote, not how every resident votes." : "See how big each voting group really is. Every dot is one county, whether it has a thousand voters or a million. Click a dot to meet the county.";
    $("dotMethod").value=state.method;
    $("dotMethodSummary").textContent=state.method === "bands" ? "Political bands use fixed cutoffs for average support across five elections. Swing means close between the parties on average. Sizes follow the results." : "These are the existing voting groups. Their sizes have not been balanced.";
    $("dotBandDetails").hidden=state.method!=="bands";
    $("dotBandRows").innerHTML=state.method === "bands" ? model.groups.map(group => `<tr><th scope="row">${esc(group.label)}</th><td>${group.threshold}</td></tr>`).join("") : "";
    const q=state.q.trim().toLocaleLowerCase();
    visible=names.filter(name => (state.region==="all" || data.counties[name].state===state.region) && (state.group==="all" || model.assignments[name].group===Number(state.group)) && (!q || name.toLocaleLowerCase().includes(q)));
    if (!visible.includes(state.county)) state.county=visible[0] || null;
    const mapParams=new URLSearchParams({k:state.k,colors:state.colors});
    if (state.method === "bands") mapParams.set("method","bands");
    if (state.county) mapParams.set("county",state.county);
    document.querySelector('nav a[href^="county-clusters.html"]').href=`county-clusters.html?${mapParams}`;
    $("dotGroupCount").value=state.k;$("dotState").value=state.region;$("dotColors").value=state.colors;$("dotSearch").value=state.q;
    $("dotGroup").innerHTML='<option value="all">All groups</option>'+model.groups.map(group => `<option value="${group.id}">${esc(group.label || `Group ${group.id}`)} · ${groupDescription(group)}</option>`).join("");
    $("dotGroup").value=state.group;
    $("dotLegend").innerHTML=`<button type="button" data-filter="all" aria-pressed="${state.group==="all"}">All groups</button>`+model.groups.map(group => `<button type="button" data-filter="${group.id}" aria-pressed="${state.group===String(group.id)}"><span class="dot" style="background:${color(group)}"></span>${esc(group.label || `Group ${group.id}`)} · ${populationMode ? `${compact.format(visible.reduce((sum,name) => sum+(model.assignments[name].group===group.id ? populationLayout.residents[name] : 0),0))} residents` : fmt.format(group.size)}</button>`).join("");
    $("dotColorNote").textContent=state.colors==="party" ? "Blue = more Democratic. Red = more Republican. Grey = more evenly split. Shades describe the group average." : "Colours identify the voting groups. Every county keeps the same group in both views.";
    $("viewGroups").setAttribute("aria-pressed",state.view==="groups");$("viewPatterns").setAttribute("aria-pressed",state.view==="patterns");
    $("groupDotChart").hidden=state.view!=="groups";$("patternWrap").hidden=state.view!=="patterns";
    $("dotChartTitle").textContent=demographicMode ? "Demographics versus voting" : populationMode ? "How many people live in each group?" : state.view==="groups" ? "How many counties are in each group?" : "How do the counties compare?";
    $("dotChartHelp").textContent=demographicMode ? "Choose a demographic for the horizontal axis and a voting measure for the vertical axis. Colours follow your selected groups." : populationMode ? "Every dot represents about the same number of residents. Longer blocks mean more people, with the same 3,103-dot budget across all included counties." : state.view==="groups" ? "Every dot has the same size. Longer blocks mean more counties." : "Further right means more Democratic support. Higher up means a shift toward Democrats since 2008; lower down means a shift toward Republicans.";
    const visibleDots=demographicMode ? visible.filter(name => demographicValue(name)!==null).length : populationMode ? visible.reduce((sum,name) => sum+populationLayout.allocations[name],0) : visible.length;
    $("dotEmpty").hidden=visible.length>0 && visibleDots>0;
    $("dotEmpty").textContent=demographicMode && visible.length ? "No estimates are available for these matching counties. Choose another demographic, or inspect a county on the map." : visible.length ? "These counties are too small for a whole population dot at this scale. Select them on the map or in the county picker." : "No counties match. Try a different name or clear a filter.";
    $("dotCounty").innerHTML=visible.map(name => `<option>${esc(name)}</option>`).join("");
    $("dotCounty").disabled=!visible.length;
    if (state.county) $("dotCounty").value=state.county;
    if (state.view==="groups") renderGroupDots();else if (demographicMode) renderDemographics();else renderPatterns();
    indexDots();renderMap();renderStory();
    $("dotStatus").textContent=demographicMode ? `${fmt.format(demographicNames.length)} county dots plotted · ${state.k} groups · ${demographicMetric().short_label} versus ${demographicVoteLabel()}.` : populationMode ? `${fmt.format(visibleDots)} of ${fmt.format(populationLayout.totalDots)} population dots shown · ${fmt.format(visible.reduce((sum,name) => sum+populationLayout.residents[name],0))} residents across ${fmt.format(visible.length)} matching counties · 2020–2024 ACS estimates.` : `${fmt.format(visible.length)} of ${fmt.format(names.length)} counties shown · ${state.k} groups · Presidential elections, 2008–2024.`;
    document.title=state.county ? `${state.county} · County dots · Election Explorer` : "County dots · Election Explorer";
  }

  function hideTooltip() { $("dotTooltip").hidden=true; }
  function tooltip(event,node) {
    const name=node.dataset.county, group=model.assignments[name].group;
    const label=model.groups[group-1].label || `Group ${group}`;
    const tip=$("dotTooltip");
    tip.innerHTML=`<strong>${esc(name)}</strong>${node.classList.contains("population-dot") ? `<span>Population dot ≈ ${fmt.format(Math.round(populationLayout.peoplePerDot))} residents, attributed to this county after rounding.</span>` : ""}${node.classList.contains("is-filtered") ? "<span>Outside current filters</span>" : ""}<span>${esc(label)} · ${pct(average(name))} average Democratic support</span><span>2024: ${pct(data.counties[name].democratic_share.at(-1))} Democratic</span>`;
    if (state.view === "demographics") tip.innerHTML=`<strong>${esc(name)}</strong><span>${esc(label)}</span><span>${esc(demographicMetric().short_label)}: ${demographicFormat(demographicValue(name))}</span><span>${esc(demographicVoteLabel())}: ${demographicVoteFormat(demographicVote(name))}</span>`;
    tip.hidden=false;
    const rect=node.getBoundingClientRect();
    const x=Number.isFinite(event.clientX) && event.type!=="focusin" ? event.clientX : rect.left+rect.width/2;
    const y=Number.isFinite(event.clientY) && event.type!=="focusin" ? event.clientY : rect.bottom;
    tip.style.left=`${Math.max(12,Math.min(innerWidth-tip.offsetWidth-12,x+14))}px`;
    tip.style.top=`${Math.max(12,Math.min(innerHeight-tip.offsetHeight-12,y+16))}px`;
  }

  async function start() {
    try {
      const responses=await Promise.all([fetch("../data/us_county_presidential_clusters.json"),fetch("../data/us_president_2024_county_boundaries.geojson"),fetch("../data/us_county_cluster_population.json"),fetch("../data/us_county_cluster_demographics.json")]);
      if (responses.some(response => !response.ok)) throw new Error("County data or boundaries unavailable");
      [data,geography,population,demographics]=await Promise.all(responses.map(response => response.json()));
      names=Object.keys(data.counties).sort();
      if (names.length!==data.county_count) throw new Error("Incomplete county data");
      $("dotState").innerHTML='<option value="all">All available states</option>'+[...new Set(names.map(name => data.counties[name].state))].sort().map(region => `<option>${esc(region)}</option>`).join("");
      const metrics=["bachelors_plus_pct",...demographics.metric_keys.filter(key => key!=="bachelors_plus_pct")];
      $("demographicMetric").innerHTML=metrics.map(key => `<option value="${key}">${esc(demographics.metrics[key].short_label)}</option>`).join("");
      $("demographicOutcome").innerHTML=Object.entries(ElectionCountyDemographics.outcomes).map(([key,label]) => `<option value="${key}">${esc(label)}</option>`).join("");
      $("dotContent").hidden=false;
      document.querySelectorAll("#dotControls select,#dotControls input,#dotControls button").forEach(node => {node.disabled=false;});
      readUrl();render();writeUrl(true);
      if (location.hash === "#demographicControls") $("demographicControls").scrollIntoView();
      const update=(field,value,replace=false) => {state[field]=value;render();writeUrl(replace);};
      $("dotMethod").onchange=event => {state.group="all";update("method",event.target.value);};
      $("dotBandDownload").onclick=() => {
        const url=URL.createObjectURL(new Blob([ElectionVotingMethods.csv(data,state.k)],{type:"text/csv;charset=utf-8"}));
        const link=document.createElement("a");link.href=url;link.download=`us_county_political_bands_${state.k}.csv`;link.click();setTimeout(() => URL.revokeObjectURL(url),1000);
      };
      $("dotGroupCount").onchange=event => {state.group="all";update("k",Number(event.target.value));};
      $("dotState").onchange=event => update("region",event.target.value);
      $("dotGroup").onchange=event => update("group",event.target.value);
      $("dotColors").onchange=event => update("colors",event.target.value);
      $("dotSearch").oninput=event => { clearTimeout(searchTimer);const query=event.target.value;searchTimer=setTimeout(() => update("q",query,true),120); };
      $("dotCounty").onchange=event => selectCounty(event.target.value);
      $("dotReset").onclick=() => {clearTimeout(searchTimer);state=initial();render();writeUrl();};
      $("countCounties").onclick=() => update("measure","counties");
      $("countPopulation").onclick=() => {state.view="groups";update("measure","population");};
      $("viewGroups").onclick=() => update("view","groups");
      $("viewPatterns").onclick=() => update("view","patterns");
      $("viewDemographics").onclick=() => {state.measure="counties";update("view","demographics");};
      $("demographicMetric").onchange=event => update("metric",event.target.value);
      $("demographicOutcome").onchange=event => update("outcome",event.target.value);
      $("demographicParty").onchange=event => update("party",event.target.value);
      const filterGroup=event => {const button=event.target.closest("[data-filter]");if (button) update("group",button.dataset.filter);};
      $("dotLegend").onclick=filterGroup;$("countyMapLegend").onclick=filterGroup;
      const panel=document.querySelector(".linked-county-views");
      panel.onclick=event => {const node=event.target.closest(".county-dot,.population-dot,.county-map-shape");if (node) selectCounty(node.dataset.county);};
      panel.onpointermove=event => {const node=event.target.closest(".county-dot,.population-dot,.county-map-shape");if (node) tooltip(event,node);else hideTooltip();};
      panel.onpointerleave=hideTooltip;
      panel.onfocusin=event => {const node=event.target.closest(".county-dot,.population-dot,.county-map-shape");if (node) tooltip(event,node);};
      panel.onfocusout=hideTooltip;
      panel.onkeydown=event => {
        const node=event.target.closest(".county-dot,.population-dot,.county-map-shape");if (!node || node.classList.contains("is-filtered")) return;
        if (event.key==="Escape") {hideTooltip();return;}
        if (["Enter"," "].includes(event.key)) {event.preventDefault();selectCounty(node.dataset.county,true,node.classList.contains("county-map-shape") ? "map" : "dots");}
        if (["ArrowRight","ArrowDown","ArrowLeft","ArrowUp"].includes(event.key)) {
          event.preventDefault();const direction=["ArrowRight","ArrowDown"].includes(event.key) ? 1 : -1;
          const source=node.classList.contains("county-map-shape") ? "map" : "dots";
          const available=source === "dots" ? visible.filter(name => nodes.has(name)) : visible;
          selectCounty(available[(available.indexOf(node.dataset.county)+direction+available.length)%available.length],true,source);
        }
      };
      window.addEventListener("popstate",() => {clearTimeout(searchTimer);readUrl();render();});
      window.addEventListener("resize",() => {clearTimeout(resizeTimer);resizeTimer=setTimeout(render,120);});
      window.addEventListener("scroll",hideTooltip,{passive:true});
    } catch (error) {
      $("dotContent").hidden=true;
      $("dotStatus").textContent="Could not load the county data. Reload this page to try again.";
      console.error(error);
    }
  }
  start();
})();
