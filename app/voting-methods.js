/* Shared political bands for maps and county dots. Bismillah. */
(() => {
  "use strict";
  const palette = ["#7851a9", "#c57928", "#288b87", "#4267b2", "#bd4c71", "#6b7f30", "#8c564b"];
  const definitions = {
    2: [
      ["Republican", "Below 50%", value => value < 50, 25],
      ["Democratic", "50% or above", () => true, 75]
    ],
    3: [
      ["Republican", "Below 45%", value => value < 45, 30],
      ["Swing / competitive", "45% through 55%", value => value <= 55, 50],
      ["Democratic", "Above 55%", () => true, 70]
    ],
    4: [
      ["Republican", "Below 40%", value => value < 40, 25],
      ["Lean Republican", "40% to below 50%", value => value < 50, 45],
      ["Lean Democratic", "50% through 60%", value => value <= 60, 55],
      ["Democratic", "Above 60%", () => true, 75]
    ],
    5: [
      ["Republican", "Below 40%", value => value < 40, 25],
      ["Lean Republican", "40% to below 45%", value => value < 45, 42.5],
      ["Swing / competitive", "45% through 55%", value => value <= 55, 50],
      ["Lean Democratic", "Above 55% through 60%", value => value <= 60, 57.5],
      ["Democratic", "Above 60%", () => true, 75]
    ],
    7: [
      ["Strong Republican", "Below 30%", value => value < 30, 15],
      ["Republican", "30% to below 40%", value => value < 40, 35],
      ["Lean Republican", "40% to below 45%", value => value < 45, 42.5],
      ["Swing / competitive", "45% through 55%", value => value <= 55, 50],
      ["Lean Democratic", "Above 55% through 60%", value => value <= 60, 57.5],
      ["Democratic", "Above 60% through 70%", value => value <= 70, 65],
      ["Strong Democratic", "Above 70%", () => true, 85]
    ]
  };
  const cache = new WeakMap();
  const mean = values => values.reduce((total,value) => total+value,0)/values.length;
  function shares(data, record) {
    return data.years.map((year,i) => {
      const votes = record.votes?.[year];
      return votes ? 100*votes.democratic/(votes.democratic+votes.republican) : record.democratic_share[i];
    });
  }
  function bands(data,k) {
    if (!definitions[k]) throw new Error("Unsupported band count");
    if (!cache.has(data)) cache.set(data,new Map());
    if (cache.get(data).has(k)) return cache.get(data).get(k);
    const places = data.counties || data.states;
    const groups = definitions[k].map(([label,threshold,,colorShare],i) => ({
      id:i+1,label,threshold,color:palette[i],color_share:colorShare,members:[],size:0,
      centroid:data.years.map(() => null),mean_democratic_share:null,change_2008_2024_pp:null
    }));
    const assignments = {}, values = {};
    for (const name of Object.keys(places).sort()) {
      const history = shares(data,places[name]);
      if (history.some(value => !Number.isFinite(value) || value < 0 || value > 100)) throw new Error("Invalid voting history");
      const average = mean(history);
      const group = groups[definitions[k].findIndex(([, , includes]) => includes(average))];
      assignments[name]={group:group.id,average_democratic_share:average};
      group.members.push(name);values[name]=history;
    }
    for (const group of groups) {
      group.size=group.members.length;
      if (!group.size) continue;
      group.centroid=data.years.map((_,i) => mean(group.members.map(name => values[name][i])));
      group.mean_democratic_share=mean(group.centroid);
      group.change_2008_2024_pp=group.centroid.at(-1)-group.centroid[0];
    }
    const result={k,method:"bands",groups,assignments,leave_one_election_out:[]};
    cache.get(data).set(k,result);
    return result;
  }
  function model(data,k,method="similarity") { return method === "bands" ? bands(data,k) : data.models[k]; }
  function csv(data,k,method="bands") {
    const result=model(data,k,method),places=data.counties || data.states;
    const quote=value => '"'+String(value ?? "").replace(/"/g,'""')+'"';
    const header=["place","state","methodology","groups","group","label","average_democratic_share",...data.years.map(year => `democratic_two_party_share_${year}`)];
    const rows=Object.keys(places).sort().map(name => {
      const group=result.groups[result.assignments[name].group-1],history=shares(data,places[name]);
      return [name,places[name].state || name,method,k,group.id,group.label || `Group ${group.id}`,mean(history),...history];
    });
    return [header,...rows].map(row => row.map(quote).join(",")).join("\r\n")+"\r\n";
  }
  window.ElectionVotingMethods={model,bands,csv,definitions};
})();
