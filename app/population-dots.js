/* Fixed-budget population dots. Allocation never changes voting groups. */
(() => {
  "use strict";
  const cache = new WeakMap();
  function apportion(entries,budget) {
    if (!Number.isSafeInteger(budget) || budget < 0) throw new Error("Invalid dot budget");
    if (entries.some(([,weight]) => !Number.isSafeInteger(weight) || weight < 0)) throw new Error("Invalid population weight");
    const total=entries.reduce((sum,[,weight]) => sum+weight,0);
    const result=Object.fromEntries(entries.map(([key]) => [key,0]));
    if (!budget) return result;
    if (!total) throw new Error("Cannot allocate dots without population");
    if (!Number.isSafeInteger(total*budget)) throw new Error("Population exceeds exact allocation range");
    const ranked=entries.map(([key,weight]) => {
      result[key]=Math.floor(weight*budget/total);
      return {key,remainder:(weight*budget)%total};
    }).sort((a,b) => b.remainder-a.remainder || (String(a.key)<String(b.key) ? -1 : String(a.key)>String(b.key) ? 1 : 0));
    const remaining=budget-Object.values(result).reduce((sum,value) => sum+value,0);
    for (let i=0;i<remaining;i++) result[ranked[i].key]++;
    return result;
  }
  function distribution(model,counties,population) {
    if (cache.has(model)) return cache.get(model);
    const residents={};
    for (const [name,county] of Object.entries(counties)) {
      const value=population.population_by_code[county.constituency_code];
      if (!Number.isSafeInteger(value) || value <= 0) throw new Error(`Population missing for ${name}`);
      residents[name]=value;
    }
    const totalPopulation=Object.values(residents).reduce((sum,value) => sum+value,0);
    if (totalPopulation!==population.total_population || Object.keys(counties).length!==population.dot_budget) throw new Error("Population coverage mismatch");
    const groups=model.groups.map(group => {
      const members=group.members || group.counties;
      return {id:group.id,members,population:members.reduce((sum,name) => sum+residents[name],0)};
    });
    const groupDots=apportion(groups.map(group => [group.id,group.population]),population.dot_budget);
    const allocations={};
    for (const group of groups) {
      group.dots=groupDots[group.id];
      Object.assign(allocations,apportion(group.members.map(name => [name,residents[name]]),group.dots));
    }
    const result={residents,groups,allocations,totalPopulation,totalDots:population.dot_budget,peoplePerDot:totalPopulation/population.dot_budget};
    cache.set(model,result);
    return result;
  }
  window.ElectionPopulationDots={apportion,distribution};
})();
