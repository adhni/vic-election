/* Exact fixed-budget population allocation checks against source data. */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");
const crypto=require("node:crypto");
const {execFileSync}=require("node:child_process");
const root=path.resolve(__dirname,"..");
const context={window:{}};
for (const file of ["voting-methods.js","population-dots.js"]) vm.runInNewContext(fs.readFileSync(path.join(root,"app",file),"utf8"),context);
const methods=context.window.ElectionVotingMethods,helper=context.window.ElectionPopulationDots;
const data=JSON.parse(fs.readFileSync(path.join(root,"data/us_county_presidential_clusters.json"),"utf8"));
const population=JSON.parse(fs.readFileSync(path.join(root,"data/us_county_cluster_population.json"),"utf8"));
const source=JSON.parse(execFileSync(process.env.PYTHON || (fs.existsSync(path.join(root,".venv/bin/python")) ? path.join(root,".venv/bin/python") : "python3"),["-c","import csv,json,sys; print(json.dumps({r['constituency_code']:int(r['population']) for r in csv.DictReader(open(sys.argv[1])) if r['population']}))",path.join(root,"data/us_2024_county_demographics.csv")],{encoding:"utf8"}));
assert.equal(population.area_count,3103);
assert.equal(population.dot_budget,3103);
for (const [file,digest] of Object.entries(population.source_sha256)) assert.equal(crypto.createHash("sha256").update(fs.readFileSync(path.join(root,file))).digest("hex"),digest);
for (const county of Object.values(data.counties)) assert.equal(population.population_by_code[county.constituency_code],source[county.constituency_code]);
assert.equal(Object.values(population.population_by_code).reduce((a,b)=>a+b,0),population.total_population);
assert.equal(population.total_population,329880924);
assert.equal(JSON.stringify(helper.apportion([["b",1],["a",1],["c",1]],2)),JSON.stringify({b:1,a:1,c:0}));
assert.equal(Object.values(helper.apportion([["empty",0],["other",0]],0)).reduce((a,b)=>a+b,0),0);
assert.throws(()=>helper.apportion([["empty",0]],10));
assert.throws(()=>helper.apportion([["negative",-1]],10));
assert.throws(()=>helper.apportion([["fraction",1.5]],10));
function verifyQuota(weights,counts,budget) {
  const total=weights.reduce((sum,[,weight])=>sum+weight,0);
  assert.equal(Object.values(counts).reduce((a,b)=>a+b,0),budget);
  if (!budget) return;
  const remainders=[];
  for (const [key,weight] of weights) {
    const floor=Math.floor(weight*budget/total);
    assert(Number.isInteger(counts[key]) && counts[key]>=floor && counts[key]<=floor+1);
    remainders.push({key,remainder:weight*budget%total,extra:counts[key]-floor});
  }
  const withExtra=remainders.filter(row=>row.extra),without=remainders.filter(row=>!row.extra);
  if (withExtra.length && without.length) assert(Math.min(...withExtra.map(row=>row.remainder))>=Math.max(...without.map(row=>row.remainder)));
}
for (const method of ["similarity","bands"]) {
  for (const k of [2,3,4,5,7]) {
    const model=methods.model(data,k,method),original=JSON.stringify(model);
    const result=helper.distribution(model,data.counties,population);
    assert.equal(result.totalDots,3103);
    assert.equal(result.totalPopulation,population.total_population);
    assert.equal(result.peoplePerDot,result.totalPopulation/3103);
    assert.equal(Object.values(result.allocations).reduce((a,b)=>a+b,0),3103);
    const groupWeights=[],groupCounts={};
    for (const group of model.groups) {
      const members=group.members || group.counties;
      const expected=members.reduce((sum,name)=>sum+source[data.counties[name].constituency_code],0);
      const entry=result.groups[group.id-1];
      assert.equal(entry.population,expected);
      assert.equal(members.reduce((sum,name)=>sum+result.allocations[name],0),entry.dots);
      groupWeights.push([group.id,expected]);groupCounts[group.id]=entry.dots;
      verifyQuota(members.map(name=>[name,source[data.counties[name].constituency_code]]),Object.fromEntries(members.map(name=>[name,result.allocations[name]])),entry.dots);
    }
    verifyQuota(groupWeights,groupCounts,3103);
    assert.equal(JSON.stringify(model),original);
    assert.equal(result.allocations["Loving County, Texas"],0);
    assert(result.allocations["Los Angeles County, California"]>1);
    console.log(`PASS ${method}, ${k} groups: exact 3,103-dot total, source populations, whole-dot rounding and unchanged groups; dots ${result.groups.map(group=>group.dots)}`);
  }
}
console.log("PASS population source coverage/hashes, stable rounding ties, zero/fraction/negative inputs and all ten population allocations");
