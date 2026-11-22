/* Source join and numerical checks for all demographic scatter choices. */
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path"),vm=require("node:vm"),crypto=require("node:crypto");
const {execFileSync}=require("node:child_process");
const root=path.resolve(__dirname,"..");
const context={window:{}};
vm.runInNewContext(fs.readFileSync(path.join(root,"app/county-demographics.js"),"utf8"),context);
const helper=context.window.ElectionCountyDemographics;
const demographics=JSON.parse(fs.readFileSync(path.join(root,"data/us_county_cluster_demographics.json"),"utf8"));
const data=JSON.parse(fs.readFileSync(path.join(root,"data/us_county_presidential_clusters.json"),"utf8"));
const source=JSON.parse(execFileSync(process.env.PYTHON || (fs.existsSync(path.join(root,".venv/bin/python")) ? path.join(root,".venv/bin/python") : "python3"),["-c","import csv,json,sys; print(json.dumps({r['constituency_code']:r for r in csv.DictReader(open(sys.argv[1]))}))",path.join(root,"data/us_2024_county_demographics.csv")],{encoding:"utf8",maxBuffer:10*1024*1024}));
assert.equal(demographics.metric_keys.length,42);
assert.equal(demographics.area_count,3103);
for (const [file,digest] of Object.entries(demographics.source_sha256)) assert.equal(crypto.createHash("sha256").update(fs.readFileSync(path.join(root,file))).digest("hex"),digest);
let missing=0;
for (const [name,record] of Object.entries(data.counties)) {
  for (const key of demographics.metric_keys) {
    const raw=source[record.constituency_code][key];
    const expected=raw==="" ? null : Number(raw);
    assert.equal(helper.demographicValue(demographics,data.counties,name,key),expected);
    if (expected===null) missing++;
    else assert(Number.isFinite(expected));
  }
  for (const outcome of Object.keys(helper.outcomes)) {
    const values=record.democratic_share;
    let expected;
    if (outcome.startsWith("change-")) {
      const parts=outcome.split("-");
      expected=values[data.years.indexOf(Number(parts[2]))]-values[data.years.indexOf(Number(parts[1]))];
    } else expected=outcome==="average" ? values.reduce((a,b)=>a+b,0)/values.length : values[data.years.indexOf(Number(outcome))];
    assert.equal(helper.votingValue(record,data.years,outcome,"democratic"),expected);
    assert.equal(helper.votingValue(record,data.years,outcome,"republican"),outcome.startsWith("change-") ? -expected : 100-expected);
  }
}
assert.equal(missing,Object.values(demographics.missing_by_metric).reduce((a,b)=>a+b,0));
const fake={metric_keys:["test"],values_by_code:{zero:[0],missing:[null]}};
assert.equal(helper.demographicValue(fake,{Zero:{constituency_code:"zero"}},"Zero","test"),0);
assert.equal(helper.demographicValue(fake,{Missing:{constituency_code:"missing"}},"Missing","test"),null);
assert.equal(helper.format(33.25,{unit:"percent"}),"33.3%");
assert.equal(helper.format(72481,{unit:"USD_2024"}),"$72,481");
assert.equal(helper.format(null,{unit:"percent"}),"Not available");
for (const value of [0,1,2,5,6,9,10,61,100,250001,9700000]) assert(helper.niceMax(value)>=value);
console.log(`PASS all 130,326 demographic joins, ${missing} missing estimates, 11 voting outcomes for both parties, zero/missing handling, formatting and source hashes`);
