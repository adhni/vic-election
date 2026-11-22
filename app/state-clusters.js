/* State and county voting histories, Ward clusters and sensitivity checks. Bismillah. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const esc = text => String(text).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  const fmt = new Intl.NumberFormat("en-US");
  const percent = value => value == null ? "—" : `${Number(value).toFixed(1)}%`;
  const groupName = group => {
    if (group.label) return group.label;
    const share = group.mean_democratic_share;
    return share < 30 ? "Very strongly Republican" : share > 70 ? "Very strongly Democratic" : share < 40 ? "Strongly Republican" : share < 47 ? "Leans Republican" : share <= 53 ? "Closely split" : share <= 60 ? "Leans Democratic" : "Strongly Democratic";
  };
  const shift = value => Math.abs(value) < .05 ? "Little change since 2008." : `${Math.abs(value).toFixed(1)} points toward ${value > 0 ? "Democrats" : "Republicans"} since 2008.`;
  const countyMode = document.body.dataset.geography === "county";
  const unit = countyMode ? "county" : "state";
  const units = countyMode ? "counties" : "states";
  const defaultPlace = countyMode ? "Wayne County, Michigan" : "Michigan";
  const dataFile = countyMode ? "us_county_presidential_clusters.json" : "us_state_presidential_clusters.json";
  const boundaryFile = countyMode ? "us_president_2024_county_boundaries.geojson" : "us_president_state_boundaries.geojson";
  let data, names, model, geography, mapRegion;
  let state = { k: 4, selected: defaultPlace, group: "all", region: "all", colors: "groups", method: "similarity" };
  const visibleNames = () => countyMode && state.region !== "all" ? names.filter(name => data.places[name].state === state.region) : names;
  const groupMembers = group => group.members.filter(name => !countyMode || state.region === "all" || data.places[name].state === state.region);
  const expandedGroups = new Set();
  const getModel = () => ElectionVotingMethods.model(data,state.k,state.method);
  let downloadUrl, downloadKey;

  function groupColor(group) {
    if (state.colors !== "party") return group.color;
    // A fixed scale keeps the same group average the same shade in every view.
    const share = group.mean_democratic_share ?? group.color_share;
    const neutral = [166, 166, 166];
    const end = share >= 50 ? [33, 102, 172] : [178, 24, 43];
    const strength = Math.min(1, Math.abs(share - 50) / 25);
    return "#" + neutral.map((value, i) => Math.round(value + (end[i] - value) * strength).toString(16).padStart(2, "0")).join("");
  }

  function readUrl() {
    const params = new URLSearchParams(location.search);
    const k = Number(params.get("k"));
    const selected = params.get(unit);
    const group = params.get("group");
    state = { k: [2,3,4,5,7].includes(k) ? k : 4,
      selected: names.includes(selected) ? selected : defaultPlace,
      method: params.get("method") === "bands" ? "bands" : "similarity",
      colors: params.get("colors") === "party" ? "party" : "groups",
      region: countyMode && names.some(name => data.places[name].state === params.get("region")) ? params.get("region") : "all",
      group: group && Number.isInteger(Number(group)) && Number(group) >= 1 && Number(group) <= ([2,3,4,5,7].includes(k) ? k : 4) ? String(Number(group)) : "all" };
    if (!visibleNames().includes(state.selected)) state.selected = visibleNames()[0];
    if (state.group !== "all" && getModel().assignments[state.selected].group !== Number(state.group)) {
      const members = groupMembers(getModel().groups.find(group => group.id === Number(state.group)));
      if (members.length) state.selected = members[0];
      else state.group = "all";
    }
  }

  function writeUrl(replace = false) {
    const url = new URL(location.href);
    url.search = "";
    url.searchParams.set("k", state.k);
    if (state.method === "bands") url.searchParams.set("method", "bands");
    url.searchParams.set(unit, state.selected);
    if (state.colors === "party") url.searchParams.set("colors", "party");
    if (countyMode && state.region !== "all") url.searchParams.set("region", state.region);
    if (state.group !== "all") url.searchParams.set("group", state.group);
    history[replace ? "replaceState" : "pushState"]({}, "", url);
  }

  function selectState(name) {
    if (!names.includes(name)) return;
    state.selected = name;
    if (!visibleNames().includes(name)) state.region = "all";
    if (state.group !== "all" && model.assignments[name].group !== Number(state.group)) state.group = "all";
    render();
    writeUrl();
  }

  function selectGroup(group) {
    state.group = String(group);
    if (state.group !== "all" && model.assignments[state.selected].group !== Number(state.group)) {
      const members = groupMembers(model.groups.find(g => g.id === Number(state.group)));
      if (members.length) state.selected = members[0];
      else state.group = "all";
    }
    render();
    writeUrl();
  }

  function setK(k) {
    if (![2,3,4,5,7].includes(k)) return;
    expandedGroups.clear();
    state.k = k;
    state.group = "all";
    render();
    writeUrl();
  }

  function walk(coords, visit) {
    if (typeof coords?.[0] === "number") visit(coords);
    else (coords || []).forEach(part => walk(part, visit));
  }

  function mapShapes(geo) {
    const allowed = new Set(visibleNames());
    const features = geo.features.filter(feature => allowed.has(feature.properties.district));
    const isHawaii = feature => countyMode ? data.places[feature.properties.district].state === "Hawaii" : feature.properties.district === "Hawaii";
    const regions = [
      { features: features.filter(f => f.properties.district !== "Alaska" && !isHawaii(f)), box: [25, 15, 910, 415] },
      { features: features.filter(f => f.properties.district === "Alaska"), box: [65, 435, 200, 115], label: "Alaska", labelAt: [65, 572] },
      { features: features.filter(isHawaii), box: countyMode && state.region === "Hawaii" ? [25, 30, 900, 480] : [340, 465, 145, 80], label: "Hawaii", labelAt: [340, 572] }
    ];
    const paths = [];
    regions.filter(region => region.features.length).forEach(region => {
      const polygons = region.features.map(feature => ({name: feature.properties.district,
        polygons: (feature.geometry.type === "Polygon" ? [feature.geometry.coordinates] : feature.geometry.coordinates)
          .filter(polygon => region.label !== "Hawaii" || polygon[0].some(([lon,lat]) => lon > -161 && lat < 23))}));
      let west = Infinity, east = -Infinity, south = Infinity, north = -Infinity;
      polygons.forEach(feature => walk(feature.polygons, ([lon,lat]) => {
        west = Math.min(west,lon); east = Math.max(east,lon); south = Math.min(south,lat); north = Math.max(north,lat);
      }));
      const [x,y,w,h] = region.box;
      const aspect = Math.cos((south + north) / 2 * Math.PI / 180);
      const scale = Math.min(w / ((east-west)*aspect), h / (north-south));
      const ox = x + (w - (east-west)*aspect*scale)/2;
      const oy = y + (h - (north-south)*scale)/2;
      polygons.forEach(feature => {
        const path = feature.polygons.map(polygon => polygon.map(ring => ring.map(([lon,lat],i) =>
          `${i ? "L" : "M"}${(ox+(lon-west)*aspect*scale).toFixed(2)},${(oy+(north-lat)*scale).toFixed(2)}`).join("")+"Z").join("")).join("");
        paths.push(`<path class="state-shape" data-state="${esc(feature.name)}" d="${path}" role="button" tabindex="0" aria-pressed="false"><title>${esc(feature.name)}</title></path>`);
      });
      if (region.label) paths.push(`<text class="inset-label" x="${region.labelAt[0]}" y="${region.labelAt[1]}">${region.label}</text>`);
    });
    if (polygonsCount(paths) !== allowed.size) throw new Error("Boundary coverage is incomplete");
    $("clusterMap").innerHTML = paths.join("");
    mapRegion = state.region;
  }

  function polygonsCount(paths) { return paths.filter(path => path.startsWith("<path")).length; }

  function renderModels() {
    if (state.method === "bands") return;
    const models = Object.values(data.models);
    const bestSeparation = models.reduce((best,item) => item.silhouette > best.silhouette ? item : best);
    const bestStability = models.reduce((best,item) => item.mean_adjusted_rand > best.mean_adjusted_rand ? item : best);
    $("modelCards").innerHTML = models.map(item => `<button class="model-card" type="button" data-k="${item.k}" aria-pressed="${item.k === state.k}">
      <strong>${item.k} groups</strong><span class="model-metric"><span>Separation</span><b>${item.silhouette.toFixed(3)}</b></span>
      <span class="model-metric"><span>Stability</span><b>${item.mean_adjusted_rand.toFixed(3)}</b></span>
      <span class="badge">${item.k === bestSeparation.k ? "Highest separation" : item.k === bestStability.k ? "Highest stability" : item.k === 4 ? "Starting view" : "Compare this cut"}</span></button>`).join("");
    $("modelInterpretation").textContent = `${bestSeparation.k} groups has the highest silhouette score (${bestSeparation.silhouette.toFixed(3)}); ${bestStability.k} groups has the highest mean leave-one-election-out agreement (${bestStability.mean_adjusted_rand.toFixed(3)}). Four groups remains the default for comparison. These are exploratory partitions of a continuous political spectrum.`;
  }

  function renderMap() {
    $("clusterLegend").innerHTML = `<button type="button" data-group="all" aria-pressed="${state.group === "all"}">All groups</button>` + model.groups.map(group =>
      `<button type="button" data-group="${group.id}" aria-pressed="${state.group === String(group.id)}"><span class="dot" style="background:${groupColor(group)}"></span>${group.id}. ${groupName(group)}</button>`).join("");
    $("clusterMap").querySelectorAll(".state-shape").forEach(path => {
      const name = path.dataset.state;
      const group = model.assignments[name].group;
      path.setAttribute("fill", groupColor(model.groups[group-1]));
      path.setAttribute("aria-label", `${name} · Group ${group} · ${percent(data.places[name].democratic_share.at(-1))} Democratic two-party vote in 2024`);
      path.setAttribute("aria-pressed", String(name === state.selected));
      path.classList.toggle("selected", name === state.selected);
      path.classList.toggle("muted", state.group !== "all" && Number(state.group) !== group);
      path.querySelector("title").textContent = `${name} · ${groupName(model.groups[group-1])} · Group ${group}`;
    });
  }

  function renderSelected() {
    const record = data.places[state.selected];
    const assignment = model.assignments[state.selected];
    const group = model.groups[assignment.group-1];
    const shares = record.democratic_share;
    $("selectedStateName").textContent = state.selected;
    $("selectedGroup").textContent = `${groupName(group)} · Group ${group.id}`;
    $("selectedGroup").style.cssText = `color:${state.colors === "party" ? "#171a1f" : groupColor(group)};background:${groupColor(group)}25`;
    const last = shares.at(-1);
    const lead = Math.abs(last - 50) * 2;
    $("selectedStateNote").textContent = `${Math.abs(last - 50) < .0001 ? "The two parties tied in 2024." : `${last > 50 ? "Democrats" : "Republicans"} led by ${lead.toFixed(1)} points in 2024.`} ${shift(last-shares[0])}`;
    $("selectedStateStats").innerHTML = [
      ["Democrats in 2024", percent(last)], ["Republicans in 2024", percent(100-last)],
      ["Elections Democrats won", `${shares.filter(value => value > 50).length} of 5`],
      ["Elections Republicans won", `${shares.filter(value => value < 50).length} of 5`]
    ].map(([label,value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join("");
    $("stateVoteRows").innerHTML = data.years.map((year,i) => `<tr><th scope="row">${year}</th><td>${fmt.format(record.votes[year].democratic)}</td><td>${fmt.format(record.votes[year].republican)}</td><td>${percent(shares[i])}</td></tr>`).join("");
    $("openStateResults").href = `./?year=us-president-2024${countyMode ? "&geo=county" : ""}&district=${encodeURIComponent(state.selected)}`;
    $("openStateResults").textContent = `Open ${state.selected}’s 2024 results`;
  }

  function renderProfiles() {
    const width = Math.max(280, $("profileChart").clientWidth);
    const height = width < 580 ? 280 : 340;
    const left = 50, right = width - 24, top = 32, bottom = height - 44;
    const x = i => left + i * (right-left) / 4;
    const y = value => bottom - value * (bottom-top) / 100;
    $("profileChart").setAttribute("viewBox", `0 0 ${width} ${height}`);
    const line = values => values.map((value,i) => `${i ? "L" : "M"}${x(i)},${y(value)}`).join("");
    const selected = data.places[state.selected].democratic_share;
    let html = `<title id="profileChartTitle">Group voting profiles, 2008 to 2024</title><desc id="profileChartDescription">Mean Democratic two-party vote shares for ${state.k} groups. Dashed line: ${esc(state.selected)}. Exact group means follow in a table.</desc>`;
    [0,25,50,75,100].forEach(value => { html += `<line class="grid${value === 50 ? " half" : ""}" x1="${left}" y1="${y(value)}" x2="${right}" y2="${y(value)}"></line><text x="${left-10}" y="${y(value)+5}" text-anchor="end">${value}%</text>`; });
    data.years.forEach((year,i) => { html += `<text x="${x(i)}" y="${height-14}" text-anchor="middle">${year}</text>`; });
    model.groups.filter(group => group.size).forEach(group => {
      const muted = state.group !== "all" && Number(state.group) !== group.id;
      html += `<g opacity="${muted ? .18 : 1}"><path d="${line(group.centroid)}" stroke="${groupColor(group)}"></path>${group.centroid.map((value,i) => `<circle cx="${x(i)}" cy="${y(value)}" r="4" fill="${groupColor(group)}"><title>Group ${group.id}, ${data.years[i]}: ${percent(value)}</title></circle>`).join("")}</g>`;
    });
    html += `<path class="selected-profile" d="${line(selected)}"></path>`;
    selected.forEach((value,i) => { html += `<circle cx="${x(i)}" cy="${y(value)}" r="3" fill="#20262e"><title>${esc(state.selected)}, ${data.years[i]}: ${percent(value)}</title></circle>`; });
    $("profileChart").innerHTML = html;
    $("profileLegend").innerHTML = model.groups.map(group => `<span class="legend-item"><span class="dot" style="background:${groupColor(group)}"></span>${group.id}. ${groupName(group)}</span>`).join("") + `<span class="legend-item"><span class="dot" style="background:#20262e"></span>${esc(state.selected)} · dashed</span>`;
    $("profileRows").innerHTML = model.groups.map(group => `<tr><th scope="row">${esc(group.label || `Group ${group.id}`)}</th><td>${group.size}</td>${group.centroid.map(value => `<td>${percent(value)}</td>`).join("")}</tr>`).join("") + `<tr><th scope="row">${esc(state.selected)}</th><td>1</td>${selected.map(value => `<td>${percent(value)}</td>`).join("")}</tr>`;
  }

  function renderGroups() {
    $("groupCards").innerHTML = model.groups.map(group => {
      const members = groupMembers(group);
      if (!group.size) return `<article class="group-card" style="--group-color:${groupColor(group)}"><header><h3>${esc(groupName(group))}</h3><span>0 ${units}</span></header><p>No ${units} meet this cutoff.</p></article>`;
      const shown = countyMode && !expandedGroups.has(group.id) ? members.slice(0, 12) : [...members];
      if (members.includes(state.selected) && !shown.includes(state.selected)) shown.push(state.selected);
      return `<article class="group-card${state.group === String(group.id) ? " active" : ""}" style="--group-color:${groupColor(group)}">
      <header><h3>${group.id}. ${groupName(group)}</h3><span>${members.length} ${units}${countyMode && state.region !== "all" ? " in this state" : ""}</span></header>
      <p>On average${countyMode ? " nationwide" : ""}: <strong>${Math.round(group.mean_democratic_share)}% Democratic</strong> and <strong>${Math.round(100-group.mean_democratic_share)}% Republican</strong> across these five elections. ${shift(group.change_2008_2024_pp)}</p>
      <div class="state-buttons" role="group" aria-label="${units} in group ${group.id}">${shown.map(name => `<button type="button" data-state="${esc(name)}" aria-pressed="${name === state.selected}">${esc(name)}</button>`).join("")}</div>
      ${members.length > shown.length ? `<button class="show-members" type="button" data-expand="${group.id}">Show all ${members.length} counties</button>` : !members.length ? "<p>No counties in this state belong to this group.</p>" : ""}</article>`;
    }).join("");
    $("sensitivityRows").innerHTML = model.leave_one_election_out.map(item => `<tr><th scope="row">${item.omitted_year}</th><td>${item.adjusted_rand.toFixed(3)}</td></tr>`).join("");
  }

  function render() {
    model = getModel();
    $("methodology").value = state.method;
    $("similarityDetails").hidden = state.method === "bands";
    $("bandsDetails").hidden = state.method !== "bands";
    document.querySelectorAll(".ward-tree-export").forEach(link => { link.hidden = state.method === "bands"; });
    const dotLink = document.querySelector('a[href^="county-dots.html"]');
    if (dotLink) {
      const params = new URLSearchParams({k:state.k,colors:state.colors,county:state.selected});
      if (state.method === "bands") params.set("method","bands");
      dotLink.href = `county-dots.html?${params}`;
    }
    $("methodSummary").textContent = state.method === "bands" ? "Political bands use fixed cutoffs for average support across five elections. Swing means close between the parties on average. Group sizes follow the results." : "Voting similarity groups places with similar results across all five elections. Group sizes follow the patterns in the data.";
    $("bandThresholdRows").innerHTML = state.method === "bands" ? model.groups.map(group => `<tr><th scope="row">${esc(group.label)}</th><td>${group.threshold}</td></tr>`).join("") : "";
    const nextDownloadKey = `${state.method}:${state.k}`;
    if (downloadKey !== nextDownloadKey) {
      if (downloadUrl) URL.revokeObjectURL(downloadUrl);
      downloadUrl = state.method === "bands" ? URL.createObjectURL(new Blob([ElectionVotingMethods.csv(data,state.k)],{type:"text/csv;charset=utf-8"})) : null;
      $("modelDownload").href = downloadUrl || `../data/${dataFile.replace(".json",".csv")}`;
      $("modelDownload").textContent = state.method === "bands" ? "Download bands" : "Download data";
      $("modelDownload").download = state.method === "bands" ? `us_${unit}_political_bands_${state.k}.csv` : dataFile.replace(".json",".csv");
      downloadKey = nextDownloadKey;
    }
    $("clusterCount").value = state.k;
    $("colorMode").value = state.colors;
    $("partyColorKey").hidden = state.colors !== "party";
    if (countyMode) {
      $("regionFilter").value = state.region;
      $("stateSelect").innerHTML = visibleNames().map(name => `<option value="${esc(name)}">${esc(name)}</option>`).join("");
    }
    $("stateSelect").value = state.selected;
    $("groupFilter").innerHTML = `<option value="all">All groups</option>` + model.groups.map(group => `<option value="${group.id}">${group.id}. ${groupName(group)} · ${group.size} ${units}</option>`).join("");
    $("groupFilter").value = state.group;
    if (mapRegion !== state.region) mapShapes(geography);
    renderModels(); renderMap(); renderSelected(); renderProfiles(); renderGroups();
    $("clusterStatus").textContent = `${state.k} groups · ${state.selected} selected · ${state.group === "all" ? `all ${fmt.format(visibleNames().length)} ${units} shown` : `Group ${state.group} highlighted`}. Percentages count votes for Democrats and Republicans only.`;
    document.title = `${state.selected} · ${state.k} ${unit} voting groups · Election Explorer`;
  }

  async function start() {
    try {
      const responses = await Promise.all([fetch(`../data/${dataFile}`), fetch(`../data/${boundaryFile}`)]);
      if (responses.some(response => !response.ok)) throw new Error("Voting data unavailable");
      const [models, geo] = await Promise.all(responses.map(response => response.json()));
      geography = geo;
      data = models; data.places = countyMode ? data.counties : data.states;
      Object.values(data.models).forEach(item => item.groups.forEach(group => { group.members = countyMode ? group.counties : group.states; }));
      names = Object.keys(data.places).sort();
      if (names.length !== (countyMode ? data.county_count : 50)) throw new Error("Incomplete coverage");
      if (countyMode) {
        $("countyCount").textContent = fmt.format(names.length);
        $("regionFilter").innerHTML = '<option value="all">All available states</option>' + [...new Set(names.map(name => data.places[name].state))].sort().map(region => `<option>${esc(region)}</option>`).join("");
        $("regionFilter").disabled = false;
        $("regionFilter").onchange = event => {
          state.region = event.target.value;
          expandedGroups.clear();
          if (!visibleNames().includes(state.selected)) state.selected = visibleNames()[0];
          if (state.group !== "all" && model.assignments[state.selected].group !== Number(state.group)) {
            const members = groupMembers(model.groups.find(group => group.id === Number(state.group)));
            if (members.length) state.selected = members[0];
            else state.group = "all";
          }
          render(); writeUrl();
        };
      }
      $("stateSelect").innerHTML = names.map(name => `<option value="${esc(name)}">${esc(name)}</option>`).join("");
      $("stateSelect").disabled = false; $("groupFilter").disabled = false;
      $("clusterContent").hidden = false;
      readUrl(); render(); writeUrl(true);
      $("clusterCount").onchange = event => setK(Number(event.target.value));
      $("methodology").onchange = event => { state.method = event.target.value; state.group = "all"; expandedGroups.clear(); render(); writeUrl(); };
      $("colorMode").onchange = event => { state.colors = event.target.value; render(); writeUrl(); };
      $("stateSelect").onchange = event => selectState(event.target.value);
      $("groupFilter").onchange = event => selectGroup(event.target.value);
      $("resetClusters").onclick = () => { state = {k:4,selected:defaultPlace,group:"all",region:"all",colors:"groups",method:"similarity"}; expandedGroups.clear(); render(); writeUrl(); };
      $("modelCards").onclick = event => { const target = event.target.closest("[data-k]"); if (target) setK(Number(target.dataset.k)); };
      $("clusterLegend").onclick = event => { const target = event.target.closest("[data-group]"); if (target) selectGroup(target.dataset.group); };
      $("groupCards").onclick = event => {
        const expand = event.target.closest("[data-expand]");
        if (expand) { expandedGroups.add(Number(expand.dataset.expand)); renderGroups(); return; }
        const target = event.target.closest("[data-state]"); if (target) selectState(target.dataset.state);
      };
      $("clusterMap").onclick = event => { const target = event.target.closest("[data-state]"); if (target) selectState(target.dataset.state); };
      $("clusterMap").onkeydown = event => {
        const target = event.target.closest("[data-state]");
        if (!target) return;
        if (["Enter", " "].includes(event.key)) { event.preventDefault(); selectState(target.dataset.state); }
        if (["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key)) {
          event.preventDefault();
          const available = visibleNames();
          const index = available.indexOf(target.dataset.state);
          const direction = ["ArrowRight", "ArrowDown"].includes(event.key) ? 1 : -1;
          const next = available[(index + direction + available.length) % available.length];
          [...$("clusterMap").querySelectorAll("[data-state]")].find(path => path.dataset.state === next).focus();
        }
      };
      window.addEventListener("popstate", () => { readUrl(); render(); });
      window.addEventListener("resize", () => requestAnimationFrame(renderProfiles));
    } catch (error) {
      $("clusterContent").hidden = true;
      $("clusterStatus").textContent = "Could not load the voting data. Reload this page to try again.";
      console.error(error);
    }
  }
  start();
})();
