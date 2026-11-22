/* County map geometry, using the same inset layout as the county explorer. */
(() => {
  "use strict";
  const esc = value => String(value).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  function walk(coords,visit) {
    if (typeof coords?.[0] === "number") visit(coords);
    else (coords || []).forEach(part => walk(part,visit));
  }
  function draw(svg,geo,records,region="all") {
    const features=geo.features.filter(feature => {
      const record=records[feature.properties.district];
      return record && (region === "all" || record.state === region);
    });
    const hawaii=feature => records[feature.properties.district].state === "Hawaii";
    const regions=region === "all" ? [
      {features:features.filter(f => !hawaii(f)),box:[25,15,910,425]},
      {features:features.filter(hawaii),box:[320,465,150,85],label:"Hawaii"}
    ] : [{features,box:[25,20,910,510],label:region === "Hawaii" ? "Hawaii" : ""}];
    const paths=[];
    for (const area of regions.filter(area => area.features.length)) {
      const polygons=area.features.map(feature => ({name:feature.properties.district,
        polygons:(feature.geometry.type === "Polygon" ? [feature.geometry.coordinates] : feature.geometry.coordinates)
          .filter(polygon => area.label !== "Hawaii" || polygon[0].some(([lon,lat]) => lon > -161 && lat < 23))}));
      let west=Infinity,east=-Infinity,south=Infinity,north=-Infinity;
      polygons.forEach(feature => walk(feature.polygons,([lon,lat]) => {
        west=Math.min(west,lon);east=Math.max(east,lon);south=Math.min(south,lat);north=Math.max(north,lat);
      }));
      const [x,y,w,h]=area.box;
      const aspect=Math.cos((south+north)/2*Math.PI/180);
      const scale=Math.min(w/((east-west)*aspect),h/(north-south));
      const ox=x+(w-(east-west)*aspect*scale)/2,oy=y+(h-(north-south)*scale)/2;
      polygons.forEach(feature => {
        const path=feature.polygons.map(polygon => polygon.map(ring => ring.map(([lon,lat],i) => `${i ? "L" : "M"}${(ox+(lon-west)*aspect*scale).toFixed(2)},${(oy+(north-lat)*scale).toFixed(2)}`).join("")+"Z").join("")).join("");
        paths.push(`<path class="county-map-shape" data-county="${esc(feature.name)}" d="${path}" role="button" tabindex="-1" aria-pressed="false"></path>`);
      });
      if (area.label && region === "all") paths.push('<text class="county-map-inset" x="320" y="575">Hawaii</text>');
    }
    const expected=Object.values(records).filter(record => region === "all" || record.state === region).length;
    if (features.length !== expected || paths.filter(path => path.startsWith("<path")).length !== expected) throw new Error("Incomplete county map coverage");
    svg.innerHTML=paths.join("");
    return new Map([...svg.querySelectorAll(".county-map-shape")].map(node => [node.dataset.county,node]));
  }
  window.ElectionCountyMap={draw};
})();
