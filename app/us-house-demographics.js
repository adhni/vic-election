/* House election comparison using fixed 2024 demographics. Bismillah. */
(() => {
  "use strict";
  const ns = "http://www.w3.org/2000/svg";
  const defaults = { view: false, metric: "bachelors_plus_pct", sample: "baseline", party: "democratic", xRange: "full", yRange: "full", outcome: "2024" };
  let state = { ...defaults };
  let context = {};
  let callbacks;
  let data = null;
  let promise = null;
  let controller = null;
  let requestId = 0;
  let error = "";
  let geometryKey = "";
  let swingRankingKey = "";
  let points = [];
  let graph = null;
  let dom;

  function supported() {
    return ["us-house-2022", "us-house-2024"].includes(context.electionKey) && context.official && context.ready;
  }

  function isActive() { return Boolean(supported() && state.view); }

  function readLocation() {
    const params = new URLSearchParams(location.search);
    state = {
      view: params.get("view") === "demographics",
      metric: params.get("demographic") || defaults.metric,
      sample: params.get("demographicSample") === "sensitivity" ? "sensitivity" : "baseline",
      party: params.get("demographicParty") === "republican" ? "republican" : "democratic",
      xRange: params.get("demographicX") === "fit" ? "fit" : "full",
      yRange: params.get("demographicY") === "fit" ? "fit" : "full",
      outcome: ["2022-matched", "2024-matched", "change"].includes(params.get("demographicOutcome")) ? params.get("demographicOutcome") : params.get("year") === "us-house-2022" ? "2022-matched" : "2024"
    };
    if (data && !data.metrics[state.metric]) state.metric = defaults.metric;
  }

  function writeUrlState(params) {
    ["view", "demographic", "demographicSample", "demographicParty", "demographicX", "demographicY", "demographicOutcome"].forEach(key => params.delete(key));
    if (!["us-house-2022", "us-house-2024"].includes(context.electionKey) || !context.official || !state.view) return;
    params.set("view", "demographics");
    if (state.metric !== defaults.metric) params.set("demographic", state.metric);
    if (state.sample !== defaults.sample) params.set("demographicSample", state.sample);
    if (state.party !== defaults.party) params.set("demographicParty", state.party);
    if (state.xRange !== defaults.xRange) params.set("demographicX", state.xRange);
    if (state.yRange !== defaults.yRange) params.set("demographicY", state.yRange);
    if (state.outcome !== defaults.outcome) params.set("demographicOutcome", state.outcome);
  }

  function finite(value) { return value !== "" && value !== undefined && value !== null && Number.isFinite(Number(value)); }

  function partyLabel() { return state.party === "republican" ? "Republican" : "Democratic"; }

  function matched() { return state.outcome !== "2024"; }
  function changing() { return state.outcome === "change"; }
  function outcomeLabel() {
    return changing() ? `${partyLabel()} share change, 2024 − 2022 (pp)`
      : `${partyLabel()} two-party vote share${matched() ? " · " + state.outcome.slice(0, 4) : ""} (%)`;
  }
  function outcomeFormat(value) {
    return finite(value) ? (changing() && value > 0 ? "+" : "") + value.toFixed(1) + (changing() ? " pp" : "%") : "Not comparable";
  }
  function voteShare(row) {
    if (matched() && row.comparison_eligible !== "true") return null;
    const field = changing() ? "democratic_share_change_pp"
      : matched() ? `democratic_two_party_share_pct_${state.outcome.slice(0, 4)}` : "democratic_two_party_share_pct";
    if (!finite(row[field])) return null;
    const democratic = Number(row[field]);
    return state.party === "republican" ? (changing() ? -democratic : 100 - democratic) : democratic;
  }

  function format(value, metric = state.metric) {
    if (!finite(value)) return "Not published";
    const unit = data.metrics[metric].unit;
    if (unit.startsWith("USD")) return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(Number(value));
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: unit === "people" || unit === "households" ? 0 : 1 }).format(Number(value))
      + (unit === "percent" ? "%" : unit === "years" ? " years" : "");
  }

  function pearson(x, y) {
    if (x.length < 3) return null;
    const mx = x.reduce((a, b) => a + b, 0) / x.length;
    const my = y.reduce((a, b) => a + b, 0) / y.length;
    let covariance = 0, vx = 0, vy = 0;
    x.forEach((value, index) => {
      const dx = value - mx, dy = y[index] - my;
      covariance += dx * dy;
      vx += dx * dx;
      vy += dy * dy;
    });
    return vx && vy ? Math.max(-1, Math.min(1, covariance / Math.sqrt(vx * vy))) : null;
  }

  function ranks(values) {
    const order = values.map((_, index) => index).sort((a, b) => values[a] - values[b]);
    const output = [];
    for (let start = 0; start < order.length;) {
      let end = start + 1;
      while (end < order.length && values[order[end]] === values[order[start]]) end += 1;
      for (let index = start; index < end; index += 1) output[order[index]] = (start + 1 + end) / 2;
      start = end;
    }
    return output;
  }

  function statistics(rows) {
    const x = rows.map(row => Number(row[state.metric]));
    const y = rows.map(voteShare);
    const states = new Map();
    rows.forEach((row, index) => {
      if (!states.has(row.state)) states.set(row.state, []);
      states.get(row.state).push(index);
    });
    const sx = [...x], sy = [...y];
    states.forEach(indices => {
      const mx = indices.reduce((sum, index) => sum + x[index], 0) / indices.length;
      const my = indices.reduce((sum, index) => sum + y[index], 0) / indices.length;
      indices.forEach(index => { sx[index] -= mx; sy[index] -= my; });
    });
    return [pearson(x, y), pearson(ranks(x), ranks(y)), pearson(sx, sy)];
  }

  function sampleRows() {
    if (matched()) return data.rows.filter(row => row[state.sample === "sensitivity" ? "comparison_sensitivity_eligible" : "comparison_eligible"] === "true");
    return data.rows.filter(row => row.two_party_analysis_eligible === "true"
      && (state.sample === "baseline" || (row.multiple_major_party_candidates === "false" && row.ranked_choice_state === "false")));
  }

  // Map direction always uses Democratic change, independently of the chart's party.
  const swingColors = { democraticStrong: "#2166ac", democratic: "#9ecae1", neutral: "#f1efeb", republican: "#efaaa3", republicanStrong: "#b51f24", excluded: "#8b9098" };
  function flipLabel(row) {
    if (row?.seat_flipped !== "true") return "";
    const party = row.elected_party_2024 === "Democratic" ? "Democrat" : row.elected_party_2024;
    return `Flipped to ${party}`;
  }
  function flipBadge(row) {
    const badge = document.createElement("span");
    badge.className = `house-flip-badge${row.elected_party_2024 === "Republican" ? " house-flip-republican" : ""}`;
    badge.textContent = flipLabel(row);
    badge.title = `2022 → 2024: ${row.elected_party_2022} → ${row.elected_party_2024}`;
    return badge;
  }
  function swingLegend() {
    return [[swingColors.democraticStrong, "Toward D ≥5 pp"], [swingColors.democratic, "Toward D 0.5–5 pp"],
      [swingColors.neutral, "Less than 0.5 pp"], [swingColors.republican, "Toward R 0.5–5 pp"],
      [swingColors.republicanStrong, "Toward R ≥5 pp"], [swingColors.excluded, "Not comparable"]];
  }
  function swingVisual(name) {
    const row = data?.byName.get(name);
    const eligible = row && row[state.sample === "sensitivity" ? "comparison_sensitivity_eligible" : "comparison_eligible"] === "true";
    if (!eligible) {
      let detail = !row ? (error ? "Comparison unavailable; open Demographics to retry." : "Loading comparison…")
        : row.boundary_unchanged_verified !== "true" ? "State plan changed; district not individually verified."
        : ["Alaska", "Maine"].includes(row.state) ? "Ranked-choice count bases not standardized."
        : row.comparison_eligible !== "true" ? "Both years need reported votes and named candidates for both parties."
        : "Multiple major-party candidates in at least one year.";
      return { color: swingColors.excluded, fill: swingColors.excluded, label: "Not comparable", detail };
    }
    const delta = Number(row.democratic_share_change_pp), magnitude = Math.abs(delta);
    const color = magnitude < .5 ? swingColors.neutral : delta > 0
      ? (magnitude >= 5 ? swingColors.democraticStrong : swingColors.democratic)
      : (magnitude >= 5 ? swingColors.republicanStrong : swingColors.republican);
    return { color, fill: color,
      label: delta === 0 ? "No change in two-party share" : `${magnitude.toFixed(1)} pp toward ${delta > 0 ? "Democrats" : "Republicans"}`,
      detail: `Democratic share: ${Number(row.democratic_two_party_share_pct_2022).toFixed(1)}% in 2022 → ${Number(row.democratic_two_party_share_pct_2024).toFixed(1)}% in 2024${flipLabel(row) ? " · " + flipLabel(row) : ""}` };
  }
  function showSwing() {
    state.view = true;
    state.outcome = "change";
    state.yRange = "fit";
    render();
  }
  function renderSwingRankings() {
    dom.swingRankings.classList.toggle("hidden", !changing());
    if (!changing()) return;
    const key = `${state.sample}|${state.party}`;
    if (key === swingRankingKey) {
      dom.swingLists.querySelectorAll("button").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.district === context.district)));
      return;
    }
    swingRankingKey = key;
    const rows = sampleRows();
    const maximumSwing = Math.max(...rows.map(row => Math.abs(Number(row.democratic_share_change_pp))), 1);
    dom.swingRankingNote.textContent = `${rows.length} comparable districts · ${partyLabel()} two-party shares shown · Bars share one scale: ← Democratic · Republican →. Includes districts missing the selected demographic.`;
    dom.swingLists.replaceChildren(...["Democrats", "Republicans"].map((direction, index) => {
      const section = document.createElement("section"), title = document.createElement("h4");
      title.textContent = `Toward ${direction}`;
      section.className = index === 0 ? "house-swing-democratic" : "house-swing-republican";
      section.append(title);
      const list = document.createElement("ol");
      rows.filter(row => index === 0 ? Number(row.democratic_share_change_pp) > 0 : Number(row.democratic_share_change_pp) < 0)
        .sort((a, b) => Math.abs(Number(b.democratic_share_change_pp)) - Math.abs(Number(a.democratic_share_change_pp)) || a.district.localeCompare(b.district))
        .slice(0, 5).forEach(row => {
          const item = document.createElement("li"), button = document.createElement("button");
          const name = document.createElement("strong"), detail = document.createElement("span");
          const share = year => state.party === "republican" ? 100 - Number(row[`democratic_two_party_share_pct_${year}`]) : Number(row[`democratic_two_party_share_pct_${year}`]);
          name.textContent = row.district;
          if (flipLabel(row)) name.append(document.createTextNode(" "), flipBadge(row));
          detail.textContent = `${share(2022).toFixed(1)}% → ${share(2024).toFixed(1)}% · ${outcomeFormat(voteShare(row))}`;
          button.type = "button";
          button.dataset.district = row.district;
          button.setAttribute("aria-pressed", String(row.district === context.district));
          const track = document.createElement("span"), bar = document.createElement("span");
          const width = Math.abs(Number(row.democratic_share_change_pp)) / maximumSwing * 50;
          track.className = "house-swing-track";
          track.setAttribute("aria-hidden", "true");
          bar.style.width = `${width}%`;
          bar.style.left = `${index === 0 ? 50 - width : 50}%`;
          track.append(bar);
          button.append(name, detail, track);
          button.onclick = () => callbacks.onSelect(row.district);
          item.append(button);
          list.append(item);
        });
      section.append(list);
      return section;
    }));
  }

  function populate() {
    dom.metric.replaceChildren(...Object.entries(data.metrics).map(([key, metric]) => new Option(metric.label, key)));
    dom.district.replaceChildren(...data.rows.map(row => new Option(row.district, row.district)));
    dom.metric.disabled = false;
  }

  async function load() {
    if (data || promise) return;
    error = "";
    const id = ++requestId;
    controller = new AbortController();
    const signal = controller.signal;
    promise = Promise.all([
      fetch(callbacks.assetPath("data/us_2024_house_analysis.csv"), { signal }).then(response => {
        if (!response.ok) throw new Error("District demographics could not be loaded.");
        return response.text();
      }),
      fetch(callbacks.assetPath("data/us_2024_house_analysis_metadata.json"), { signal }).then(response => {
        if (!response.ok) throw new Error("Demographic definitions could not be loaded.");
        return response.json();
      }),
      fetch(callbacks.assetPath("data/us_house_2022_2024_comparison.csv"), { signal }).then(response => {
        if (!response.ok) throw new Error("Election comparison could not be loaded.");
        return response.text();
      })
    ]).then(([text, metadata, comparisonText]) => {
      if (id !== requestId || signal.aborted) return;
      const rows = callbacks.parseCSV(text);
      const comparison = callbacks.parseCSV(comparisonText);
      const comparisonByCode = new Map(comparison.map(row => [row.constituency_code, row]));
      if (comparison.length !== 435 || comparisonByCode.size !== 435 || rows.some(row => !comparisonByCode.has(row.constituency_code)
        || comparisonByCode.get(row.constituency_code).district !== row.district)) throw new Error("Comparison districts do not match.");
      rows.forEach(row => Object.assign(row, comparisonByCode.get(row.constituency_code)));
      const codes = new Set(rows.map(row => row.constituency_code));
      const names = new Set(context.districtNames);
      if (rows.length !== 435 || codes.size !== 435 || metadata.congress !== 119 || !metadata.demographic_metrics?.[defaults.metric]
        || rows.some(row => row.election_key !== "us-house-2024" || !names.has(row.district))) {
        throw new Error("Demographic data does not match these election districts.");
      }
      data = { rows, metrics: metadata.demographic_metrics, byName: new Map(rows.map(row => [row.district, row])) };
      if (!data.metrics[state.metric]) state.metric = defaults.metric;
      populate();
    }).catch(reason => {
      if (id === requestId && reason.name !== "AbortError") error = "Demographics could not be loaded. Check your connection and retry.";
    }).finally(() => {
      if (id !== requestId) return;
      promise = null;
      controller = null;
      render();
      callbacks.onDataChange();
    });
  }

  function exclusionNote(row) {
    if (matched() && row.comparison_eligible !== "true") {
      if (row.boundary_unchanged_verified !== "true") return "Not plotted: this state's congressional plan changed. This district has not been individually verified as unchanged.";
      if (["Alaska", "Maine"].includes(row.state)) return "Not plotted: ranked-choice count bases have not been standardized across years.";
      return "Not plotted: both years need named Democratic and Republican candidates with positive reported votes.";
    }
    if (matched() && state.sample === "sensitivity" && row.comparison_sensitivity_eligible !== "true") return "Not plotted: multiple major-party candidates in at least one year.";
    if (row.votes_reported !== "true") return "Not plotted: candidate vote totals were not reported for this unopposed contest.";
    if (row.two_party_analysis_eligible !== "true") return "Not plotted: this contest does not include both named major-party candidates.";
    if (state.sample === "sensitivity" && (row.multiple_major_party_candidates === "true" || row.ranked_choice_state === "true")) return "Not plotted in the stricter sample. This district remains available on the map and in the results.";
    if (!finite(row[state.metric])) return "Not plotted: this demographic estimate was not published for the district.";
    return "";
  }

  function renderSelection() {
    const row = data.byName.get(context.district);
    dom.selection.classList.toggle("hidden", !row);
    if (!row) return;
    dom.district.value = row.district;
    dom.flip.classList.toggle("hidden", !flipLabel(row));
    dom.flip.replaceChildren();
    if (flipLabel(row)) dom.flip.append(flipBadge(row), document.createTextNode(" · 2022 → 2024"));
    dom.values.textContent = `${format(row[state.metric])} · ${outcomeLabel()}: ${outcomeFormat(voteShare(row))}`;
    if (matched() && row.comparison_eligible === "true") {
      const share = year => state.party === "republican" ? 100 - Number(row[`democratic_two_party_share_pct_${year}`]) : Number(row[`democratic_two_party_share_pct_${year}`]);
      const delta = share(2024) - share(2022);
      const metric = document.createElement("span"), cards = document.createElement("span");
      metric.className = "house-selected-metric";
      metric.textContent = `${data.metrics[state.metric].label}: ${format(row[state.metric])}`;
      cards.className = "house-share-cards";
      [["2022:", `${share(2022).toFixed(1)}%`], ["2024:", `${share(2024).toFixed(1)}%`], ["Change:", `${delta > 0 ? "+" : ""}${delta.toFixed(1)} pp`]].forEach(([label, value], index) => {
        const card = document.createElement("span"), caption = document.createElement("span"), number = document.createElement("strong");
        caption.textContent = `${label} ${index < 2 ? partyLabel() + " share" : partyLabel() + " share change"}`;
        number.textContent = value;
        if (index === 2) card.className = Number(row.democratic_share_change_pp) > 0 ? "house-change-democratic" : Number(row.democratic_share_change_pp) < 0 ? "house-change-republican" : "";
        card.append(caption, number);
        cards.append(card);
      });
      dom.values.replaceChildren(metric, cards);
    }
    dom.note.textContent = exclusionNote(row) || `2024 elected member: ${row.elected_member} · ${row.elected_party}`;
    const definition = data.metrics[state.metric];
    const moe = row[`${state.metric}_moe`];
    dom.uncertainty.textContent = !finite(row[state.metric]) ? "The estimate and its uncertainty are unavailable; no value has been imputed."
      : !finite(moe) ? "A margin of error is not available for this estimate."
      : `${definition.label}: ${format(row[state.metric])}, with a 90% margin of error of ±${definition.unit === "percent" ? Number(moe).toFixed(1) + " percentage points" : format(moe)}. ${Number(moe) === 0 ? "Zero sampling uncertainty does not rule out nonsampling error. " : ""}Population measured: ${definition.source_universes.join("; ")}. ${definition.denominator.length || definition.numerator.length > 1 ? "This derived margin of error is an approximation." : "This is the published margin of error."}`;
    dom.chart.querySelectorAll(".house-scatter-point").forEach(point => {
      const selected = point.dataset.district === row.district;
      point.setAttribute("aria-pressed", String(selected));
      point.setAttribute("r", selected ? "7" : point.classList.contains("house-seat-flipped") ? "5" : "4");
      if (!dom.chart.contains(document.activeElement)) point.setAttribute("tabindex", selected || (!points.some(p => p.row.district === row.district) && point.dataset.index === "0") ? "0" : "-1");
    });
    dom.chart.querySelectorAll(".house-seat-flipped").forEach(point => point.parentNode.appendChild(point));
    const selected = dom.chart.querySelector('[aria-pressed="true"]');
    if (selected) selected.parentNode.appendChild(selected);
  }

  function svgElement(tag, attributes, text) {
    const element = document.createElementNS(ns, tag);
    Object.entries(attributes || {}).forEach(([name, value]) => element.setAttribute(name, value));
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function tickFormat(value) {
    if (data.metrics[state.metric].unit.startsWith("USD")) return "$" + new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value);
    return new Intl.NumberFormat("en-US", { notation: Math.abs(value) >= 10000 ? "compact" : "standard", maximumFractionDigits: 1 }).format(value);
  }

  function axisRange(values, fit, percentage, segments, signed = false) {
    const minimum = Math.min(...values), maximum = Math.max(...values);
    if (signed && !fit) return { low: -100, high: 100, ticks: [-100, -50, 0, 50, 100] };
    if (!fit && percentage) {
      return { low: 0, high: 100, ticks: segments >= 4 ? [0, 25, 50, 75, 100] : [0, 50, 100] };
    }
    const padding = (maximum - minimum) * .05 || Math.max(Math.abs(minimum) * .02, 1);
    let low = fit ? (signed ? minimum - padding : Math.max(0, minimum - padding)) : 0;
    let high = fit ? maximum + padding : maximum;
    if (percentage) high = Math.min(100, high);
    if (signed) { low = Math.max(-100, low); high = Math.min(100, high); }
    if (high === low) high = low + 1;
    const size = (high - low) / segments;
    const magnitude = 10 ** Math.floor(Math.log10(size));
    const step = [1, 2, 2.5, 5, 10].find(value => value * magnitude >= size) * magnitude;
    if (!fit) high = Math.ceil(high / step) * step;
    const ticks = [];
    for (let value = Math.ceil(low / step) * step; value <= high + step * 1e-8; value += step) {
      ticks.push(Number(value.toPrecision(12)));
    }
    return { low, high, ticks: ticks.length >= 2 ? ticks : [low, high] };
  }

  function draw(rows) {
    if (!isActive() || !data) return;
    const width = dom.chart.clientWidth;
    if (width < 1) return;
    const key = `${state.outcome}|${state.metric}|${state.sample}|${state.party}|${state.xRange}|${state.yRange}|${width}`;
    if (key === geometryKey) { renderSelection(); return; }
    geometryKey = key;
    dom.tooltip.classList.add("hidden");
    const height = Math.max(300, Math.min(560, width * .68));
    const left = 38, right = width - 18, top = 12, bottom = height - 30;
    const values = rows.map(row => Number(row[state.metric]));
    if (!values.length) {
      points = [];
      graph = null;
      dom.chart.textContent = "No published estimates are available for this measure in the selected sample.";
      renderSelection();
      return;
    }
    const xRange = axisRange(values, state.xRange === "fit", data.metrics[state.metric].unit === "percent", width >= 600 ? 4 : 3);
    const yRange = axisRange(rows.map(voteShare), state.yRange === "fit", !changing(), 4, changing());
    const reference = changing() ? 0 : 50;
    const x = value => left + (value - xRange.low) / (xRange.high - xRange.low) * (right - left);
    const y = value => bottom - (value - yRange.low) / (yRange.high - yRange.low) * (bottom - top);
    graph = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, width, height, role: "group", "data-x-min": xRange.low, "data-x-max": xRange.high, "data-y-min": yRange.low, "data-y-max": yRange.high, "aria-label": `${rows.length} congressional districts: ${data.metrics[state.metric].label} and ${outcomeLabel()}` });
    graph.append(svgElement("desc", {}, "Use arrow keys to move between dots, then Enter to select a district. The district selector below also includes districts excluded from the plot."));
    yRange.ticks.forEach(value => {
      graph.append(svgElement("line", { x1: left, x2: right, y1: y(value), y2: y(value), class: value === reference ? "house-scatter-midline" : "house-scatter-grid" }));
      graph.append(svgElement("text", { x: left - 8, y: y(value) + 4, "text-anchor": "end" }, String(Number(value.toFixed(2)))));
    });
    if (yRange.low <= reference && yRange.high >= reference && !yRange.ticks.includes(reference)) {
      graph.append(svgElement("line", { x1: left, x2: right, y1: y(reference), y2: y(reference), class: "house-scatter-midline" }));
    }
    xRange.ticks.forEach((value, index) => {
      graph.append(svgElement("text", { x: x(value), y: height - 7, "text-anchor": index === 0 ? "start" : index === xRange.ticks.length - 1 ? "end" : "middle" }, tickFormat(value)));
    });
    points = rows.map((row, index) => ({ row, index, x: x(Number(row[state.metric])), y: y(voteShare(row)) }));
    points.forEach(point => {
      const label = `${point.row.district}: ${format(point.row[state.metric])}; ${outcomeLabel()}: ${outcomeFormat(voteShare(point.row))}${flipLabel(point.row) ? " · " + flipLabel(point.row) : ""}`;
      const circle = svgElement("circle", { cx: point.x, cy: point.y, r: point.row.seat_flipped === "true" ? 5 : 4, class: `house-scatter-point${point.row.seat_flipped === "true" ? " house-seat-flipped" : ""}`, role: "button", "data-district": point.row.district, "data-index": point.index, "aria-label": label, "aria-pressed": "false", tabindex: "-1" });
      if (changing()) circle.style.fill = swingVisual(point.row.district).color;
      graph.append(circle);
    });
    dom.chart.replaceChildren(graph);
    dom.axis.textContent = data.metrics[state.metric].label + (data.metrics[state.metric].unit === "percent" ? " (%)" : "");
    renderSelection();
  }

  function nearest(event, radius = 18) {
    if (!graph) return null;
    const box = graph.getBoundingClientRect();
    const x = (event.clientX - box.left) / box.width * Number(graph.getAttribute("width"));
    const y = (event.clientY - box.top) / box.height * Number(graph.getAttribute("height"));
    let best = null, distance = radius * radius;
    points.forEach(point => {
      const next = (point.x - x) ** 2 + (point.y - y) ** 2;
      if (next < distance) { best = point; distance = next; }
    });
    return best;
  }

  function showTooltip(point) {
    if (!point || !graph) { dom.tooltip.classList.add("hidden"); return; }
    dom.tooltip.textContent = `${point.row.district}\n${format(point.row[state.metric])} · ${outcomeLabel()}: ${outcomeFormat(voteShare(point.row))}${flipLabel(point.row) ? " · " + flipLabel(point.row) : ""}`;
    dom.tooltip.classList.remove("hidden");
    const box = graph.getBoundingClientRect(), parent = dom.panel.getBoundingClientRect();
    const px = box.left - parent.left + point.x;
    dom.tooltip.style.left = Math.max(12, Math.min(parent.width - dom.tooltip.offsetWidth - 12, px - dom.tooltip.offsetWidth / 2)) + "px";
    dom.tooltip.style.top = Math.max(8, box.top - parent.top + point.y - dom.tooltip.offsetHeight - 12) + "px";
  }

  function render() {
    if (!dom) return;
    const active = isActive();
    dom.controls.classList.toggle("hidden", !supported());
    dom.panel.classList.toggle("hidden", !active);
    dom.swingRankings.classList.toggle("hidden", !active || !changing());
    dom.panel.classList.toggle("house-swing-view", changing());
    dom.grid.classList.toggle("house-demographics-view", active);
    dom.resultsButton.setAttribute("aria-pressed", String(!active));
    dom.demographicsButton.setAttribute("aria-pressed", String(active));
    if (!active) {
      if (supported() && context.mapMode === "house-swing" && !data && !error) void load();
      return;
    }
    dom.content.classList.toggle("hidden", !data);
    dom.retry.classList.toggle("hidden", !error);
    dom.chart.setAttribute("aria-busy", String(!data && !error));
    dom.sample.value = state.sample;
    dom.party.value = state.party;
    dom.xRange.value = state.xRange;
    dom.yRange.value = state.yRange;
    dom.yLabel.textContent = outcomeLabel();
    dom.outcome.querySelector('[value="2024"]').disabled = context.electionKey === "us-house-2022";
    dom.outcome.value = state.outcome;
    dom.comparisonNote.textContent = matched() ? `2024 ACS demographics held fixed · Same matched districts for both years and change · Map and full results show ${context.electionKey === "us-house-2022" ? "2022" : "2024"}` : "2024 ACS demographics and 2024 election results";
    dom.panel.classList.toggle("house-republican", state.party === "republican");
    if (!data) {
      dom.status.textContent = error || "Loading district demographics…";
      if (!error) void load();
      return;
    }
    dom.metric.value = state.metric;
    const sample = sampleRows();
    const rows = sample.filter(row => finite(row[state.metric]) && finite(voteShare(row)));
    dom.status.textContent = `${rows.length} districts · ${435 - sample.length} excluded by sample · ${sample.length - rows.length} missing this measure`;
    const values = statistics(rows);
    dom.statistics.replaceChildren(...["National r", "Spearman ρ", "Within-state r"].map((label, index) => {
      const span = document.createElement("span"), strong = document.createElement("strong");
      span.append(document.createTextNode(label));
      strong.textContent = values[index] === null ? "Unavailable" : values[index].toFixed(3);
      strong.dataset.statistic = ["pearson", "spearman", "within-state"][index];
      span.append(strong);
      return span;
    }));
    draw(rows);
    renderSwingRankings();
  }

  function update(nextContext) {
    context = nextContext;
    if (context.electionKey === "us-house-2022" && state.outcome === "2024") state.outcome = "2022-matched";
    if (!supported() && controller) {
      requestId += 1;
      controller.abort();
      controller = null;
      promise = null;
    }
    render();
  }

  function setup(options) {
    callbacks = options;
    const ids = { controls: "houseViewControls", grid: "explorerGrid", panel: "houseDemographicsPanel", resultsButton: "houseResultsView", demographicsButton: "houseDemographicsView", metric: "houseDemographicMetric", sample: "houseDemographicSample", party: "houseDemographicParty", outcome: "houseDemographicOutcome", comparisonNote: "houseDemographicComparisonNote", xRange: "houseDemographicXRange", yRange: "houseDemographicYRange", yLabel: "houseDemographicYLabel", status: "houseDemographicStatus", retry: "houseDemographicRetry", content: "houseDemographicContent", statistics: "houseDemographicStatistics", chart: "houseDemographicChart", axis: "houseDemographicAxis", selection: "houseDemographicSelection", district: "houseDemographicDistrict", values: "houseDemographicSelectedValues", flip: "houseDemographicFlip", note: "houseDemographicSelectedNote", uncertainty: "houseDemographicUncertaintyText", fullResult: "houseDemographicFullResult", swingRankings: "houseSwingRankings", swingRankingNote: "houseSwingRankingNote", swingLists: "houseSwingLists", tooltip: "houseDemographicTooltip" };
    dom = Object.fromEntries(Object.entries(ids).map(([key, id]) => [key, document.getElementById(id)]));
    readLocation();
    dom.resultsButton.onclick = () => { state.view = false; render(); callbacks.onUrlChange(); };
    dom.demographicsButton.onclick = () => { state.view = true; render(); callbacks.onUrlChange(); };
    dom.metric.onchange = () => { state.metric = dom.metric.value; render(); callbacks.onUrlChange(); };
    dom.sample.onchange = () => { state.sample = dom.sample.value; render(); callbacks.onDataChange(); callbacks.onUrlChange(); };
    dom.outcome.onchange = () => { state.outcome = dom.outcome.value; render(); callbacks.onSwingChange(changing()); callbacks.onUrlChange(); };
    dom.party.onchange = () => { state.party = dom.party.value; render(); callbacks.onUrlChange(); };
    dom.xRange.onchange = () => { state.xRange = dom.xRange.value; render(); callbacks.onUrlChange(); };
    dom.yRange.onchange = () => { state.yRange = dom.yRange.value; render(); callbacks.onUrlChange(); };
    dom.district.onchange = () => callbacks.onSelect(dom.district.value);
    dom.retry.onclick = () => { error = ""; render(); };
    dom.fullResult.onclick = callbacks.onFullResult;
    dom.chart.addEventListener("click", event => {
      const target = event.target.closest(".house-scatter-point");
      const point = target ? points[Number(target.dataset.index)] : nearest(event, 24);
      if (point) callbacks.onSelect(point.row.district);
    });
    dom.chart.addEventListener("pointermove", event => showTooltip(nearest(event)));
    dom.chart.addEventListener("pointerleave", () => dom.tooltip.classList.add("hidden"));
    dom.chart.addEventListener("focusin", event => {
      if (event.target.matches(".house-scatter-point")) showTooltip(points[Number(event.target.dataset.index)]);
    });
    dom.chart.addEventListener("focusout", () => dom.tooltip.classList.add("hidden"));
    dom.chart.addEventListener("keydown", event => {
      const target = event.target.closest(".house-scatter-point");
      if (!target) return;
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        callbacks.onSelect(target.dataset.district);
        return;
      }
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const index = event.key === "Home" ? 0 : event.key === "End" ? points.length - 1
        : (Number(target.dataset.index) + (event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : 1) + points.length) % points.length;
      dom.chart.querySelectorAll(".house-scatter-point").forEach(point => point.setAttribute("tabindex", point.dataset.index === String(index) ? "0" : "-1"));
      dom.chart.querySelector(`[data-index="${index}"]`).focus();
    });
    let frame;
    const resize = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => { if (isActive() && data) draw(sampleRows().filter(row => finite(row[state.metric]) && finite(voteShare(row)))); });
    });
    resize.observe(dom.chart);
    window.addEventListener("popstate", () => { readLocation(); render(); });
  }

  window.houseDemographics = { setup, update, isActive, writeUrlState, showSwing, swingVisual, swingLegend };
})();
