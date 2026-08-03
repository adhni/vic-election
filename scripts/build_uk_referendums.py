#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import requests
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid


EU_RESULT_URL = "https://data.london.gov.uk/download/2y548/52dccf67-a2ab-4f43-a6ba-894aaeef169e/EU-referendum-result-data.csv"
SCOTLAND_REPORT_URL = "https://data.parliament.uk/DepositedPapers/Files/DEP2015-0558/Scottish-independence-referendum-report.pdf"
BOUNDARY_URL = "https://raw.githubusercontent.com/ONSdigital/uk-topojson/main/input/ltla16-bsc.json"
EU_SOURCE_PAGE = "https://www.electoralcommission.org.uk/research-reports-and-data/our-reports-and-data-past-elections-and-referendums/results-and-turnout-eu-referendum"
SCOTLAND_SOURCE_PAGE = "https://www.electoralcommission.org.uk/research-reports-and-data/our-reports-and-data-past-elections-and-referendums/report-scottish-independence-referendum"
BOUNDARY_SOURCE_PAGE = "https://www.data.gov.uk/dataset/759f6fcb-934a-464e-a45c-eced2f5fcf67/local-authority-districts-december-2016-full-clipped-boundaries-in-the-uk-wgs842"

SOURCE_SHA256 = {
    "eu": "8f161fbdf30419e0400fbc8cb09b84da15aee6c3645451ef24e51c2da701e786",
    "scotland": "8a72083588a2b8e37a1445f0b99148098597fee3ee77d1ad562f898cd51aca8e",
    "boundaries": "748d24014abfa9c5cfaf5a0ab7ffb2a1442da0809f17dd50293b89db7c789069",
}

FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code", "contest_status",
    "result_note",
)

SCOTLAND_ELECTORATE = {
    "Aberdeen City": 175_751, "Aberdeenshire": 206_490, "Angus": 93_656,
    "Argyll and Bute": 72_014, "Clackmannanshire": 39_974,
    "Comhairle Nan Eilean Siar": 22_908, "Dumfries and Galloway": 122_052,
    "Dundee": 118_764, "East Ayrshire": 99_682, "East Dunbartonshire": 86_844,
    "East Lothian": 81_947, "East Renfrewshire": 72_993, "City of Edinburgh": 378_039,
    "Falkirk": 122_460, "Fife": 302_165, "Glasgow": 486_296, "Highland": 190_787,
    "Inverclyde": 62_486, "Midlothian": 69_620, "Moray": 75_173,
    "North Ayrshire": 113_941, "North Lanarkshire": 268_738, "Orkney": 17_806,
    "Perth and Kinross": 120_052, "Renfrewshire": 134_745, "Scottish Borders": 95_542,
    "Shetland": 18_516, "South Ayrshire": 94_895, "South Lanarkshire": 261_193,
    "Stirling": 69_043, "West Dunbartonshire": 71_128, "West Lothian": 138_238,
}

SCOTLAND_NAME_ALIASES = {
    "Argyll & Bute": "Argyll and Bute",
    "Comhairle Nan": "Comhairle Nan Eilean Siar",
    "Dumfries &": "Dumfries and Galloway",
    "Dundee City": "Dundee",
    "East": "East Dunbartonshire",
    "Glasgow City": "Glasgow",
    "Na h-Eileanan Siar": "Comhairle Nan Eilean Siar",
    "Orkney Islands": "Orkney",
    "Perth & Kinross": "Perth and Kinross",
    "Shetland Islands": "Shetland",
    "West": "West Dunbartonshire",
}
SCOTLAND_REPORT_NAMES = {
    "Argyll and Bute": "Argyll & Bute",
    "Comhairle Nan Eilean Siar": "Comhairle Nan Eilean Siar",
    "Dumfries and Galloway": "Dumfries & Galloway",
    "Dundee": "Dundee",
    "Glasgow": "Glasgow",
    "Orkney": "Orkney",
    "Perth and Kinross": "Perth & Kinross",
    "Shetland": "Shetland",
}

EXPECTED_EU = {"Remain": 16_141_241, "Leave": 17_410_742, "Rejected": 25_359, "Electorate": 46_500_001}
EXPECTED_SCOTLAND = {"Yes": 1_617_989, "No": 2_001_926, "Rejected": 3_429, "Electorate": 4_283_938}


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> Path:
    if path.exists() and path.stat().st_size and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    with session.get(url, timeout=600, stream=True) as response:
        response.raise_for_status()
        with path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                handle.write(chunk)
    return path


def require_sha256(path: Path, expected: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise SystemExit(f"{path}: source checksum changed to {digest}; expected {expected}")


def integer(value: object) -> int:
    return int(str(value).replace(",", "").replace(".", ""))


def pdf_pages(path: Path, page_numbers: tuple[int, ...]) -> list[str]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return [reader.pages[number].extract_text() or "" for number in page_numbers]
    except ImportError:
        import pdfplumber

        with pdfplumber.open(path) as document:
            return [document.pages[number].extract_text() or "" for number in page_numbers]


def parse_scotland_report(path: Path) -> list[dict[str, object]]:
    text = " ".join(" ".join(pdf_pages(path, (154, 155))).split())
    results = []
    for name in SCOTLAND_ELECTORATE:
        report_name = SCOTLAND_REPORT_NAMES.get(name, name)
        name_guard = r"(?<!East )" if name == "Renfrewshire" else ""
        pattern = re.compile(
            rf"{name_guard}{re.escape(report_name)}\s+(?P<total>[\d,]+)\s+(?P<yes>[\d,]+)\s+"
            r"(?P<no>[\d,]+)\s+(?P<rejected>[\d,]+)\s+(?P<turnout>[\d.]+)%"
        )
        match = pattern.search(text)
        if not match:
            raise SystemExit(f"Scottish report parser could not find {report_name}")
        results.append({
            "district": name,
            "total": integer(match.group("total")),
            "yes": integer(match.group("yes")),
            "no": integer(match.group("no")),
            "rejected": integer(match.group("rejected")),
            "turnout": float(match.group("turnout")),
            "enrolment": SCOTLAND_ELECTORATE[name],
        })
    if len(results) != 32:
        found = sorted(row["district"] for row in results)
        raise SystemExit(f"Scottish report parser found {len(results)} councils: {found}")
    return results


def referendum_rows(
    district: str,
    code: str,
    area_type: str,
    votes: dict[str, int],
    enrolment: int,
    rejected: int,
    source_page: str,
    note: str,
) -> list[dict[str, object]]:
    ranked = sorted(votes.items(), key=lambda item: (-item[1], item[0]))
    formal = sum(votes.values())
    total = formal + rejected
    base = {
        "district": district, "district_url": source_page, "distribution_url": BOUNDARY_SOURCE_PAGE,
        "elected_member": ranked[0][0], "elected_party": ranked[0][0], "enrolment": enrolment,
        "formal_votes": formal, "informal_votes": rejected, "total_votes": total,
        "turnout_pct": round(total / enrolment * 100, 2), "majority": ranked[0][1] - ranked[1][1],
        "round_number": 0, "row_type": "first", "excluded_candidate": "", "excluded_party": "",
        "electorate_type": area_type, "constituency_code": code, "contest_status": "official",
        "result_note": note,
    }
    return [{**base, "candidate": option, "candidate_party": option, "votes": count} for option, count in ranked]


def parse_eu(path: Path) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        source_rows = list(csv.DictReader(handle))
    if len(source_rows) != 382:
        raise SystemExit(f"Expected 382 Brexit counting areas, found {len(source_rows)}")

    area_rows = []
    by_region: dict[str, list[dict[str, str]]] = defaultdict(list)
    lookup = {}
    for source in source_rows:
        remain = integer(source["Remain"])
        leave = integer(source["Leave"])
        rejected = integer(source["Rejected_Ballots"])
        valid = integer(source["Valid_Votes"])
        total = integer(source["Votes_Cast"])
        enrolment = integer(source["Electorate"])
        rejected_reasons = sum(integer(source[field]) for field in (
            "No_official_mark", "Voting_for_both_answers", "Writing_or_mark", "Unmarked_or_void"
        ))
        if remain + leave != valid or valid + rejected != total or rejected_reasons != rejected:
            raise SystemExit(f"Brexit source totals do not reconcile for {source['Area']}")
        if round(total / enrolment * 100, 2) != float(source["Pct_Turnout"]):
            raise SystemExit(f"Brexit source turnout does not reconcile for {source['Area']}")
        code = source["Area_Code"]
        area = source["Area"]
        note = "Official Electoral Commission counting-area result."
        if area == "Gibraltar":
            note += " Gibraltar is shown as a compact schematic inset; its inset size and position are not geographic."
        area_rows.extend(referendum_rows(
            area, code, source["Region"], {"Remain": remain, "Leave": leave},
            enrolment, rejected, EU_SOURCE_PAGE, note,
        ))
        by_region[source["Region"]].append(source)
        lookup[code] = source

    region_rows = []
    for region, members in sorted(by_region.items()):
        code = members[0]["Region_Code"]
        region_rows.extend(referendum_rows(
            region, code, "Referendum region",
            {"Remain": sum(integer(row["Remain"]) for row in members), "Leave": sum(integer(row["Leave"]) for row in members)},
            sum(integer(row["Electorate"]) for row in members),
            sum(integer(row["Rejected_Ballots"]) for row in members), EU_SOURCE_PAGE,
            "Official Electoral Commission regional aggregation. South West includes Gibraltar.",
        ))
    return area_rows, region_rows, lookup


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def clean_geometry(geometry):
    geometry = make_valid(geometry)
    geometry = geometry.simplify(0.0025, preserve_topology=True)
    geometry = make_valid(geometry)
    if geometry.geom_type == "GeometryCollection":
        geometry = unary_union([part for part in geometry.geoms if part.geom_type in {"Polygon", "MultiPolygon"}])
    return geometry


def feature(district: str, code: str, geometry, **extra) -> dict[str, object]:
    properties = {"district": district, "constituency_code": code, **extra}
    return {"type": "Feature", "properties": properties, "geometry": mapping(clean_geometry(geometry))}


def write_geojson(path: Path, features: list[dict[str, object]]) -> None:
    collection = {"type": "FeatureCollection", "features": features}
    path.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def build_boundaries(path: Path, eu_lookup: dict[str, dict[str, str]], output_dir: Path) -> dict[str, str]:
    collection = json.loads(path.read_text(encoding="utf-8"))
    raw_by_code = {item["properties"]["areacd"]: item for item in collection["features"]}
    area_features = []
    geometries = {}
    for code, source in eu_lookup.items():
        if code in raw_by_code:
            geometry = shape(raw_by_code[code]["geometry"])
        elif code == "N92000002":
            geometry = unary_union([
                shape(item["geometry"]) for item in collection["features"]
                if item["properties"]["areacd"].startswith("N09")
            ])
        elif code == "GI":
            geometry = box(-8.15, 49.55, -7.88, 49.78)
        else:
            raise SystemExit(f"No boundary for Brexit counting area {code} ({source['Area']})")
        geometry = make_valid(geometry)
        geometries[code] = geometry
        area_features.append(feature(source["Area"], code, geometry, area_type=source["Region"]))
    write_geojson(output_dir / "uk_2016_eu_referendum_counting_area_boundaries.geojson", area_features)

    region_geometries: dict[str, list] = defaultdict(list)
    region_names = {}
    for code, source in eu_lookup.items():
        region_geometries[source["Region_Code"]].append(geometries[code])
        region_names[source["Region_Code"]] = source["Region"]
    region_features = [
        feature(region_names[code], code, unary_union(parts), area_type="Referendum region")
        for code, parts in sorted(region_geometries.items())
    ]
    write_geojson(output_dir / "uk_2016_eu_referendum_region_boundaries.geojson", region_features)

    scotland_source_by_name = {
        SCOTLAND_NAME_ALIASES.get(item["properties"]["areanm"], item["properties"]["areanm"]): item
        for item in collection["features"] if item["properties"]["areacd"].startswith("S12")
    }
    missing = set(SCOTLAND_ELECTORATE) - set(scotland_source_by_name)
    if missing:
        raise SystemExit(f"Missing Scottish council boundaries: {sorted(missing)}")
    scotland_codes = {}
    scotland_features = []
    for district in SCOTLAND_ELECTORATE:
        item = scotland_source_by_name[district]
        code = item["properties"]["areacd"]
        scotland_codes[district] = code
        scotland_features.append(feature(district, code, shape(item["geometry"]), area_type="Council area"))
    write_geojson(output_dir / "scotland_2014_independence_council_boundaries.geojson", scotland_features)
    return scotland_codes


def validate_source_totals(eu_area_rows: list[dict[str, object]], scotland_results: list[dict[str, object]]) -> None:
    eu_first = eu_area_rows[::2]
    eu_votes = defaultdict(int)
    for row in eu_area_rows:
        eu_votes[row["candidate"]] += int(row["votes"])
    eu_actual = {
        **eu_votes,
        "Rejected": sum(int(row["informal_votes"]) for row in eu_first),
        "Electorate": sum(int(row["enrolment"]) for row in eu_first),
    }
    if dict(eu_actual) != EXPECTED_EU:
        raise SystemExit(f"Brexit national totals do not reconcile: {dict(eu_actual)}")
    for row in scotland_results:
        if int(row["yes"]) + int(row["no"]) + int(row["rejected"]) != int(row["total"]):
            raise SystemExit(f"Scottish report totals do not reconcile for {row['district']}")
        if round(int(row["total"]) / int(row["enrolment"]) * 100, 1) != float(row["turnout"]):
            raise SystemExit(f"Scottish report turnout does not reconcile for {row['district']}")
    scotland_actual = {
        "Yes": sum(int(row["yes"]) for row in scotland_results),
        "No": sum(int(row["no"]) for row in scotland_results),
        "Rejected": sum(int(row["rejected"]) for row in scotland_results),
        "Electorate": sum(int(row["enrolment"]) for row in scotland_results),
    }
    if scotland_actual != EXPECTED_SCOTLAND:
        raise SystemExit(f"Scottish national totals do not reconcile: {scotland_actual}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the 2016 Brexit and 2014 Scottish referendum map datasets")
    parser.add_argument("--raw-dir", type=Path, default=Path("tmp/uk_referendums_sources"))
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers["User-Agent"] = "vic-election-preference-explorer/1.0"
    eu_path = download(session, EU_RESULT_URL, args.raw_dir / "EU-referendum-result-data.csv", args.refresh)
    scotland_path = download(session, SCOTLAND_REPORT_URL, args.raw_dir / "Scottish-independence-referendum-report.pdf", args.refresh)
    boundary_path = download(session, BOUNDARY_URL, args.raw_dir / "ltla16-bsc.json", args.refresh)
    for key, path in (("eu", eu_path), ("scotland", scotland_path), ("boundaries", boundary_path)):
        require_sha256(path, SOURCE_SHA256[key])

    eu_area_rows, eu_region_rows, eu_lookup = parse_eu(eu_path)
    scotland_results = parse_scotland_report(scotland_path)
    validate_source_totals(eu_area_rows, scotland_results)
    scotland_codes = build_boundaries(boundary_path, eu_lookup, args.output_dir)
    scotland_rows = []
    for result in scotland_results:
        scotland_rows.extend(referendum_rows(
            str(result["district"]), scotland_codes[str(result["district"])], "Council area",
            {"Yes": int(result["yes"]), "No": int(result["no"])}, int(result["enrolment"]),
            int(result["rejected"]), SCOTLAND_SOURCE_PAGE,
            "Official Electoral Commission appendix result; electorate reconciles to the Chief Counting Officer's national total.",
        ))

    write_csv(args.output_dir / "uk_2016_eu_referendum_counting_area_fpp.csv", eu_area_rows)
    write_csv(args.output_dir / "uk_2016_eu_referendum_region_fpp.csv", eu_region_rows)
    write_csv(args.output_dir / "scotland_2014_independence_council_fpp.csv", scotland_rows)
    print("Built UK EU referendum 2016 (382 counting areas / 12 regions) and Scotland 2014 (32 councils)")


if __name__ == "__main__":
    main()
