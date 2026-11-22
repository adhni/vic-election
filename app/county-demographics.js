/* Coordinate and unit helpers for the county demographic scatterplot. */
(() => {
  "use strict";
  const outcomes = {
    "2024": "2024 support", "2020": "2020 support", "2016": "2016 support", "2012": "2012 support", "2008": "2008 support",
    average:"Average support · 2008–2024", "change-2020-2024":"Swing · 2020 → 2024", "change-2016-2020":"Swing · 2016 → 2020",
    "change-2012-2016":"Swing · 2012 → 2016", "change-2008-2012":"Swing · 2008 → 2012", "change-2008-2024":"Change · 2008 → 2024"
  };
  const mean = values => values.reduce((a,b) => a+b,0)/values.length;
  function demographicValue(demographics,counties,name,key) {
    const value=demographics.values_by_code[counties[name].constituency_code]?.[demographics.metric_keys.indexOf(key)];
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  }
  function votingValue(record,years,outcome,party="democratic") {
    const values=record.democratic_share;
    let value;
    if (outcome.startsWith("change-")) {
      const [,start,end]=outcome.split("-").map(Number);
      value=values[years.indexOf(end)]-values[years.indexOf(start)];
    } else value=outcome === "average" ? mean(values) : values[years.indexOf(Number(outcome))];
    return party === "republican" ? (outcome.startsWith("change-") ? -value : 100-value) : value;
  }
  function niceMax(value) {
    if (!(value>0)) return 1;
    const power=10**Math.floor(Math.log10(value)),part=value/power;
    return (part<=1 ? 1 : part<=2 ? 2 : part<=5 ? 5 : 10)*power;
  }
  function format(value,metric,tick=false) {
    if (value == null) return "Not available";
    if (metric.unit === "percent") return `${tick ? Number(value.toFixed(1)) : value.toFixed(1)}%`;
    if (metric.unit === "years") return `${Number(value.toFixed(1))}${tick ? "" : " years"}`;
    const currency=metric.unit.startsWith("USD");
    const number=new Intl.NumberFormat("en-US",tick ? {notation:"compact",maximumFractionDigits:1} : {maximumFractionDigits:0}).format(value);
    return `${currency ? "$" : ""}${number}${!tick && metric.unit.endsWith("per_month") ? "/month" : ""}`;
  }
  window.ElectionCountyDemographics={outcomes,demographicValue,votingValue,niceMax,format};
})();
