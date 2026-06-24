#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import time
import zipfile
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.parse import urljoin

import geopandas as gpd
import pandas as pd
import requests
from bs4 import BeautifulSoup
from shapely.geometry import mapping


BASE = "https://pastvtr.elections.nsw.gov.au"
UA = "Mozilla/5.0 (compatible; vic-election-preference-explorer/0.1; +https://github.com/)"

LONG_FIELDS = [
    "district",
    "district_url",
    "distribution_url",
    "elected_member",
    "elected_party",
    "enrolment",
    "formal_votes",
    "informal_votes",
    "total_votes",
    "turnout_pct",
    "majority",
    "round_number",
    "row_type",
    "excluded_candidate",
    "excluded_party",
    "candidate",
    "candidate_party",
    "votes",
]

SUMMARY_FIELDS = [
    "district",
    "district_url",
    "distribution_url",
    "elected_member",
    "elected_party",
    "enrolment",
    "formal_votes",
    "informal_votes",
    "total_votes",
    "turnout_pct",
    "majority",
    "primary_leader",
    "primary_leader_party",
    "primary_leader_votes",
    "winner",
    "winner_party",
    "winner_final_votes",
    "runner_up",
    "runner_up_party",
    "runner_up_final_votes",
    "final_margin",
    "preference_changed_result",
    "winner_transfer_gain",
]


@dataclass
class DistrictLinks:
    district: str
    district_url: str
    distribution_url: str


def clean_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return re.sub(r"\s+", " ", str(value)).strip()


def clean_int(value: object) -> int | None:
    text = clean_text(value)
    if not text or text == "-":
        return None
    match = re.search(r"-?\d[\d,]*", text)
    if not match:
        return None
    return int(match.group(0).replace(",", ""))


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    return session


def fetch_text(session: requests.Session, url: str, path: Path, refresh: bool = False, pause: float = 0.1) -> str:
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8")
    time.sleep(pause)
    response = session.get(url, timeout=60)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(response.text, encoding="utf-8")
    return response.text


def fetch_bytes(session: requests.Session, url: str, path: Path, refresh: bool = False, pause: float = 0.1) -> bytes:
    if path.exists() and not refresh:
        return path.read_bytes()
    time.sleep(pause)
    response = session.get(url, timeout=120)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return response.content


def read_html_tables(html: str) -> list[pd.DataFrame]:
    return pd.read_html(StringIO(html))


def discover_districts(
    session: requests.Session,
    results_url: str,
    raw_dir: Path,
    expected_districts: int,
    refresh: bool = False,
) -> list[DistrictLinks]:
    html = fetch_text(session, results_url, raw_dir / "results.html", refresh=refresh, pause=0)
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if len(tables) < 2:
        raise SystemExit("NSW results page did not contain the district results table")

    districts: list[DistrictLinks] = []
    for tr in tables[1].find_all("tr")[1:]:
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue
        district = re.sub(r"\s+\*+$", "", clean_text(tds[0].get_text(" ")))
        district_url = ""
        distribution_url = ""
        if tds[1].find("a", href=True):
            district_url = urljoin(BASE, tds[1].find("a", href=True)["href"])
        if tds[2].find("a", href=True):
            distribution_url = urljoin(BASE, tds[2].find("a", href=True)["href"])
        if district and district_url and distribution_url:
            districts.append(DistrictLinks(district=district, district_url=district_url, distribution_url=distribution_url))

    if len(districts) != expected_districts:
        raise SystemExit(f"Expected {expected_districts} NSW districts, found {len(districts)}")
    return districts


def parse_first_preferences(html: str) -> tuple[dict[str, object], list[dict[str, object]], dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text("\n", strip=True)
    enrolled_match = re.search(r"Electors Enrolled.*?:\s*([\d,]+)", page_text)
    enrolment = clean_int(enrolled_match.group(1)) if enrolled_match else None

    tables = read_html_tables(html)
    if len(tables) < 2:
        raise SystemExit("Expected first preference summary page to contain vote summary and venue tables")

    summary_df, venue_df = tables[0], tables[1]
    candidate_rows: list[dict[str, object]] = []
    candidate_parties: dict[str, str] = {}
    formal_votes = None

    for _, row in summary_df.iterrows():
        candidate = clean_text(row.iloc[0])
        if not candidate:
            continue
        votes = clean_int(row.iloc[2] if len(row) > 2 else None)
        if candidate.upper().startswith("TOTAL FORMAL"):
            formal_votes = votes
            continue
        if votes is None:
            continue
        party = clean_text(row.iloc[1] if len(row) > 1 else "") or "Independent"
        candidate_parties[candidate] = party
        candidate_rows.append({
            "candidate": candidate,
            "candidate_party": party,
            "votes": votes,
        })

    venue_label_col = venue_df.columns[0]
    total_row = venue_df[venue_df[venue_label_col].map(clean_text) == "Total Votes / Ballot Papers"]
    if total_row.empty:
        raise SystemExit("Could not find NSW total votes row in first preference venue table")
    total_row = total_row.iloc[0]

    formal_total = clean_int(total_row.get("Total Formal"))
    informal_votes = clean_int(total_row.get("Informal"))
    total_votes = clean_int(total_row.get("Total Votes/ Ballot Papers"))
    turnout_pct = round((total_votes or 0) / enrolment * 100, 2) if enrolment and total_votes else None

    meta = {
        "enrolment": enrolment,
        "formal_votes": formal_total if formal_total is not None else formal_votes,
        "informal_votes": informal_votes,
        "total_votes": total_votes,
        "turnout_pct": turnout_pct,
    }
    return meta, candidate_rows, candidate_parties


def resolve_candidate(label: object, candidate_names: list[str]) -> str:
    text = clean_text(label)
    if not text:
        return ""
    for candidate in candidate_names:
        if text == candidate or text.startswith(candidate + " ") or text.startswith(candidate + "(") or text.startswith(candidate + " ("):
            return candidate
        if text.startswith("ELECTED " + candidate):
            return candidate
    return ""


def district_cache_key(district_url: str, district_name: str) -> str:
    path = urlparse(district_url).path
    match = re.search(r"/la/([^/]+)/cc/", path, flags=re.I)
    if match:
        return match.group(1)
    return re.sub(r"[^a-z0-9]+", "-", district_name.strip().lower()).strip("-")


def parse_distribution(
    html: str,
    candidate_parties: dict[str, str],
) -> tuple[list[dict[str, object]], dict[str, int], int | None]:
    tables = read_html_tables(html)
    if not tables:
        raise SystemExit("Expected distribution page to contain a distribution table")

    df = tables[0]
    if len(df) < 3:
        raise SystemExit("Distribution table is shorter than expected")

    candidate_names = sorted(candidate_parties, key=len, reverse=True)
    header_exclusions = [clean_text(value) for value in df.iloc[0].tolist()]
    data_rows = df.iloc[2:].reset_index(drop=True)

    header_labels = [clean_text(value) for value in df.iloc[1].tolist()]
    round_pairs: list[tuple[int, int]] = []
    col = 2
    while col + 1 < len(df.columns):
        transfer_header = header_labels[col]
        progressive_header = header_labels[col + 1]
        if transfer_header != "Votes Distributed" or progressive_header != "Progressive Totals":
            break
        round_pairs.append((col, col + 1))
        col += 2

    if not round_pairs:
        raise SystemExit("Could not derive NSW distribution rounds")

    long_rows: list[dict[str, object]] = []
    final_totals: dict[str, int] = {}

    absolute_majority = None
    for _, row in data_rows.iterrows():
        if clean_text(row.iloc[0]) == "Absolute Majority":
            absolute_majority = clean_int(row.iloc[1])
            break

    for round_number, (transfer_col, progressive_col) in enumerate(round_pairs, start=1):
        excluded = resolve_candidate(header_exclusions[transfer_col], candidate_names)
        excluded_party = candidate_parties.get(excluded, "")
        row_type = "final" if round_number == len(round_pairs) else "progressive"

        for _, row in data_rows.iterrows():
            label = clean_text(row.iloc[0])
            if label.startswith("Total ") or label in {"Exhausted Votes", "Informal", "Absolute Majority"}:
                continue
            candidate = resolve_candidate(label, candidate_names)
            if not candidate:
                continue

            transfer_votes = clean_int(row.iloc[transfer_col])
            if candidate != excluded and transfer_votes not in (None, 0):
                long_rows.append({
                    "round_number": round_number,
                    "row_type": "transfer",
                    "excluded_candidate": excluded,
                    "excluded_party": excluded_party,
                    "candidate": candidate,
                    "candidate_party": candidate_parties.get(candidate, "Independent"),
                    "votes": transfer_votes,
                })

            progressive_votes = clean_int(row.iloc[progressive_col])
            if candidate != excluded and progressive_votes not in (None, 0):
                if row_type == "final":
                    final_totals[candidate] = progressive_votes
                long_rows.append({
                    "round_number": round_number,
                    "row_type": row_type,
                    "excluded_candidate": excluded,
                    "excluded_party": excluded_party,
                    "candidate": candidate,
                    "candidate_party": candidate_parties.get(candidate, "Independent"),
                    "votes": progressive_votes,
                })

    if len(final_totals) < 2:
        raise SystemExit("Final distribution totals did not leave at least two candidates")

    return long_rows, final_totals, absolute_majority


def build_rows_for_district(session: requests.Session, raw_dir: Path, links: DistrictLinks, refresh: bool = False) -> tuple[list[dict[str, object]], dict[str, object]]:
    slug = district_cache_key(links.district_url, links.district)
    fp_html = fetch_text(session, links.district_url, raw_dir / "districts" / f"{slug}_fp.html", refresh=refresh)
    dop_html = fetch_text(session, links.distribution_url, raw_dir / "districts" / f"{slug}_dop.html", refresh=refresh)

    fp_meta, first_rows, candidate_parties = parse_first_preferences(fp_html)
    distribution_rows, final_totals, majority = parse_distribution(dop_html, candidate_parties)

    primary_sorted = sorted(first_rows, key=lambda row: (-int(row["votes"]), str(row["candidate"])))
    final_sorted = sorted(final_totals.items(), key=lambda item: (-item[1], item[0]))
    winner, winner_votes = final_sorted[0]
    runner_up, runner_up_votes = final_sorted[1]
    elected_party = candidate_parties.get(winner, "Independent")
    final_margin = winner_votes - runner_up_votes

    meta = {
        "district": links.district,
        "district_url": links.district_url,
        "distribution_url": links.distribution_url,
        "elected_member": winner,
        "elected_party": elected_party,
        "enrolment": fp_meta["enrolment"] or "",
        "formal_votes": fp_meta["formal_votes"] or "",
        "informal_votes": fp_meta["informal_votes"] or "",
        "total_votes": fp_meta["total_votes"] or "",
        "turnout_pct": fp_meta["turnout_pct"] if fp_meta["turnout_pct"] is not None else "",
        "majority": majority if majority is not None else "",
    }

    long_rows: list[dict[str, object]] = []
    for row in first_rows:
        long_rows.append({
            **meta,
            "round_number": 0,
            "row_type": "first",
            "excluded_candidate": "",
            "excluded_party": "",
            **row,
        })
    for row in distribution_rows:
        long_rows.append({**meta, **row})

    winner_first_votes = next((int(row["votes"]) for row in first_rows if row["candidate"] == winner), 0)
    summary_row = {
        **meta,
        "primary_leader": primary_sorted[0]["candidate"],
        "primary_leader_party": primary_sorted[0]["candidate_party"],
        "primary_leader_votes": primary_sorted[0]["votes"],
        "winner": winner,
        "winner_party": elected_party,
        "winner_final_votes": winner_votes,
        "runner_up": runner_up,
        "runner_up_party": candidate_parties.get(runner_up, "Independent"),
        "runner_up_final_votes": runner_up_votes,
        "final_margin": final_margin,
        "preference_changed_result": str(primary_sorted[0]["candidate"] != winner),
        "winner_transfer_gain": winner_votes - winner_first_votes,
    }
    return long_rows, summary_row


def ensure_boundary_dataset(
    session: requests.Session,
    raw_dir: Path,
    boundary_zip_url: str,
    boundary_zip_name: str,
    boundary_extract_dir: str,
    boundary_dataset_relpath: str,
    refresh: bool = False,
) -> Path:
    zip_path = raw_dir / boundary_zip_name
    extract_dir = raw_dir / boundary_extract_dir
    fetch_bytes(session, boundary_zip_url, zip_path, refresh=refresh, pause=0)
    dataset_path = extract_dir / boundary_dataset_relpath
    if dataset_path.exists() and not refresh:
        return dataset_path
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    if not dataset_path.exists():
        raise SystemExit(f"Expected boundary dataset not found after extraction: {dataset_path}")
    return dataset_path


def build_boundaries(dataset_path: Path, out_path: Path, district_names: list[str], boundary_source_url: str) -> None:
    gdf = gpd.read_file(dataset_path)
    if gdf.crs is None:
        raise SystemExit("NSW boundary shapefile has no CRS")
    if str(gdf.crs).upper() != "EPSG:4326":
        gdf = gdf.to_crs(4326)

    name_field = next((column for column in gdf.columns if column.lower() in {"districtna", "name"}), None)
    if not name_field:
        raise SystemExit(f"Could not find district name field in NSW boundaries: {list(gdf.columns)}")

    by_upper = {name.upper(): name for name in district_names}
    features = []
    seen: set[str] = set()
    for _, row in gdf.iterrows():
        raw_name = clean_text(row[name_field]).upper()
        district = by_upper.get(raw_name)
        if not district:
            raise SystemExit(f"NSW boundary district does not match results: {raw_name}")
        geom = row.geometry
        if geom is None or geom.is_empty:
            raise SystemExit(f"{district}: empty geometry")
        if not geom.is_valid:
            geom = geom.buffer(0)
        if geom.is_empty:
            raise SystemExit(f"{district}: empty geometry after repair")
        features.append({
            "type": "Feature",
            "properties": {
                "district": district,
                "source": boundary_source_url,
            },
            "geometry": mapping(geom),
        })
        seen.add(district)

    missing = sorted(set(district_names) - seen)
    if missing:
        raise SystemExit(f"Missing NSW boundary districts: {missing}")

    features.sort(key=lambda feature: feature["properties"]["district"])
    out_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(
    default_raw_dir: str = "tmp/nsw_2023",
    default_results_url: str = f"{BASE}/SG2301/LA/results",
    default_boundary_zip_url: str = "https://elections.nsw.gov.au/getmedia/cb9324ee-078f-405b-b4e9-0b95d4e6cefe/2021-gda-94.zip",
    default_boundary_zip_name: str = "2021-gda-94.zip",
    default_boundary_extract_dir: str = "2021-gda-94",
    default_boundary_dataset_relpath: str = "2021GDA94/StateElectoralDistrict2021_GDA94_region.shp",
    default_prefix: str = "nsw_2023",
    default_expected_districts: int = 93,
) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=Path(default_raw_dir))
    parser.add_argument("--out", type=Path, default=Path("data"))
    parser.add_argument("--results-url", default=default_results_url)
    parser.add_argument("--boundary-zip-url", default=default_boundary_zip_url)
    parser.add_argument("--boundary-zip-name", default=default_boundary_zip_name)
    parser.add_argument("--boundary-extract-dir", default=default_boundary_extract_dir)
    parser.add_argument("--boundary-dataset-relpath", default=default_boundary_dataset_relpath)
    parser.add_argument("--prefix", default=default_prefix)
    parser.add_argument("--expected-districts", type=int, default=default_expected_districts)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    session = make_session()
    districts = discover_districts(
        session,
        args.results_url,
        args.raw_dir,
        args.expected_districts,
        refresh=args.refresh,
    )

    all_long_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for index, links in enumerate(districts, start=1):
        print(f"[{index:02d}/{len(districts)}] {links.district}")
        long_rows, summary_row = build_rows_for_district(session, args.raw_dir, links, refresh=args.refresh)
        all_long_rows.extend(long_rows)
        summary_rows.append(summary_row)

    summary_rows.sort(key=lambda row: str(row["district"]))
    all_long_rows.sort(key=lambda row: (str(row["district"]), int(row["round_number"]), str(row["row_type"]), str(row["candidate"])))

    pref_path = args.out / f"{args.prefix}_preferences_long.csv"
    summary_path = args.out / f"{args.prefix}_district_summary.csv"
    boundary_path = args.out / f"{args.prefix}_district_boundaries.geojson"
    write_csv(pref_path, all_long_rows, LONG_FIELDS)
    write_csv(summary_path, summary_rows, SUMMARY_FIELDS)

    dataset_path = ensure_boundary_dataset(
        session,
        args.raw_dir,
        args.boundary_zip_url,
        args.boundary_zip_name,
        args.boundary_extract_dir,
        args.boundary_dataset_relpath,
        refresh=args.refresh,
    )
    build_boundaries(dataset_path, boundary_path, [district.district for district in districts], args.boundary_zip_url)

    print(f"Wrote {pref_path}")
    print(f"Wrote {summary_path}")
    print(f"Wrote {boundary_path}")


if __name__ == "__main__":
    main()
