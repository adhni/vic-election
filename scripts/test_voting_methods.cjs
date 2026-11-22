/* Independent boundary and source-data checks for political bands. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const root = path.resolve(__dirname,"..");
const context = {window:{}};
vm.runInNewContext(fs.readFileSync(path.join(root,"app/voting-methods.js"),"utf8"),context);
const methods = context.window.ElectionVotingMethods;
function expected(value,k) {
  if (k===2) return value<50 ? 1 : 2;
  if (k===3) return value<45 ? 1 : value<=55 ? 2 : 3;
  if (k===7) return value<30 ? 1 : value<40 ? 2 : value<45 ? 3 : value<=55 ? 4 : value<=60 ? 5 : value<=70 ? 6 : 7;
  if (k===4) return value<40 ? 1 : value<50 ? 2 : value<=60 ? 3 : 4;
  return value<40 ? 1 : value<45 ? 2 : value<=55 ? 3 : value<=60 ? 4 : 5;
}
const years=[2008,2012,2016,2020,2024];
const boundaries=[0,29.999999,30,39.999999,40,44.999999,45,49.999999,50,50.000001,55,55.000001,60,60.000001,70,70.000001,100];
const synthetic={years,states:Object.fromEntries(boundaries.map(value => [String(value),{democratic_share:years.map(() => value)}]))};
for (const k of [2,3,4,5,7]) {
  const result=methods.bands(synthetic,k);
  for (const value of boundaries) assert.equal(result.assignments[value].group,expected(value,k));
  const empty=methods.bands({years,states:{Only:{democratic_share:[20,20,20,20,20]}}},k);
  assert.equal(empty.groups.length,k);
  assert.equal(empty.groups[0].size,1);
  assert.equal(empty.groups[1].size,0);
  assert.equal(empty.groups[1].mean_democratic_share,null);
  assert(empty.groups[1].centroid.every(value => value===null));
}
// Raw counts prevent rounded displayed shares from crossing a cutoff.
const rounding={years,states:{Near:{democratic_share:[45,45,45,45,45],votes:Object.fromEntries(years.map(year => [year,{democratic:4499999999,republican:5500000001}]))}}};
assert.equal(methods.bands(rounding,5).assignments.Near.group,2);
// Every election has equal weight, rather than pooling differently sized totals.
const equal={years,states:{Example:{votes:Object.fromEntries(years.map((year,i) => [year,i===0 ? {democratic:90,republican:10} : {democratic:1000,republican:9000}]))}}};
assert.equal(methods.bands(equal,5).assignments.Example.group,1);
for (const geography of ["state","county"]) {
  const data=JSON.parse(fs.readFileSync(path.join(root,`data/us_${geography}_presidential_clusters.json`),"utf8"));
  const places=data.counties || data.states;
  for (const k of [2,3,4,5,7]) {
    const original=JSON.stringify(data.models[k]);
    const result=methods.model(data,k,"bands");
    const counted=new Set();
    for (const [name,record] of Object.entries(places)) {
      const history=years.map(year => 100*record.votes[year].democratic/(record.votes[year].democratic+record.votes[year].republican));
      const average=history.reduce((a,b)=>a+b,0)/5;
      assert.equal(result.assignments[name].group,expected(average,k));
      assert.equal(result.assignments[name].average_democratic_share,average);
    }
    for (const group of result.groups) {
      assert.equal(group.size,group.members.length);
      for (const name of group.members) { assert(!counted.has(name));counted.add(name); }
      if (group.size) {
        const shares=group.members.map(name => years.map(year => 100*places[name].votes[year].democratic/(places[name].votes[year].democratic+places[name].votes[year].republican)));
        for (let i=0;i<5;i++) assert(Math.abs(group.centroid[i]-shares.reduce((total,row)=>total+row[i],0)/shares.length)<1e-10);
      }
    }
    assert.equal(counted.size,Object.keys(places).length);
    assert.equal(JSON.stringify(data.models[k]),original);
    assert.equal(methods.model(data,k,"similarity"),data.models[k]);
    assert.equal(methods.csv(data,k).trim().split("\r\n").length,Object.keys(places).length+1);
    console.log(`PASS ${geography} ${k} bands: exact source assignments, full membership, centroids, export and unchanged similarity model; sizes ${result.groups.map(g=>g.size)}`);
  }
}
console.log("PASS all cutoff boundaries, empty bands, raw-count precision and equal election weighting");
