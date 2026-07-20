#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import requests
from shapely.geometry import mapping, shape


RESULTS_URL = "https://opendata.spr.gov.my/data/keputusan-pru.json"
DELAYED_RESULTS_URL = "https://opendata.spr.gov.my/data/keputusan-prk.json"
HEADLINE_STATS_URL = "https://lake.electiondata.my/results_headline/headline_stats_federal.csv"
HEADLINE_BALLOTS_URL = "https://lake.electiondata.my/results_headline/headline_ballots_federal.csv"
ELECTIONS = {
    2022: {
        "ge": "GE15",
        "boundaries": {"peninsular": 2018, "sabah": 2019, "sarawak": 2015},
    },
    2018: {
        "ge": "GE14",
        "boundaries": {"peninsular": 2018, "sabah": 2003, "sarawak": 2015},
    },
    2013: {
        "ge": "GE13",
        "boundaries": {"peninsular": 2003, "sabah": 2003, "sarawak": 2005},
    },
}
UA = "Mozilla/5.0 (compatible; election-preference-explorer/0.1; +https://github.com/)"

FIELDS = [
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "enrolment", "formal_votes", "informal_votes", "unreturned_votes", "total_votes",
    "turnout_pct", "majority", "round_number", "row_type", "excluded_candidate",
    "excluded_party", "candidate", "candidate_party", "votes", "electorate_type",
    "constituency_code", "contest_status",
]


def download(session: requests.Session, url: str, path: Path, refresh: bool) -> None:
    if path.exists() and not refresh:
        return
    response = session.get(url, timeout=120)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)


def as_int(value: object) -> int:
    text = str(value or "").strip()
    return 0 if not text or text.upper() == "NULL" else int(float(text))


def title_name(value: object) -> str:
    return str(value or "").strip().title()


def code_from_seat(value: object) -> str:
    match = re.search(r"P\.\d{3}", str(value or "").upper())
    return match.group(0) if match else ""


def district_from_seat(value: object) -> str:
    return re.sub(r"^P\.\d{3}\s*", "", str(value or "").strip(), flags=re.I).title()


def election_rows(main_rows: list[dict[str, object]], delayed_rows: list[dict[str, object]], year: int) -> list[dict[str, object]]:
    rows = [
        row for row in main_rows
        if str(row.get("TAHUN PILIHAN RAYA")) == str(year)
        and str(row.get("JenisCalon", "")).lower() == "parlimen"
    ]
    if year == 2022:
        rows.extend(
            row for row in delayed_rows
            if str(row.get("TAHUN PILIHAN RAYA")) == "2022"
            and code_from_seat(row.get("PARLIMEN")) == "P.017"
        )
    return rows


def corpus_rows(
    ballot_rows: list[dict[str, str]], headline_stats: dict[str, dict[str, str]],
    ge: str,
) -> list[dict[str, object]]:
    rows = []
    for row in ballot_rows:
        if row["election"] != ge:
            continue
        code = code_from_seat(row["seat"])
        stats = headline_stats[code]
        rows.append({
            "PARLIMEN": row["seat"],
            "NAMA ATAS KERTAS UNDI": row["name_on_ballot"],
            "SINGKATAN NAMA PARTI BERTANDING": row["party_on_ballot"],
            "BILANGAN UNDI": row["votes"],
            "StatusCalon": "MNG" if row["result"] == "won" else "KLH",
            "MAJORITI": stats["majority"] if row["result"] == "won" else "0",
            "UNDI DITOLAK": stats["votes_rejected"],
            "UNDI TAK KEMBALI": stats["ballots_not_returned"],
            "JumlahPemilih": stats["voters_total"],
            "PERATUS UNDI": stats["voter_turnout"],
            "NEGERI": row["state"].replace("W.P.", "W.P"),
        })
    return rows


def build_rows(
    source_rows: list[dict[str, object]], year: int,
    headline_stats: dict[str, dict[str, str]],
) -> tuple[list[dict[str, object]], dict[str, str]]:
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in source_rows:
        groups[code_from_seat(row.get("PARLIMEN"))].append(row)
    if "" in groups or len(groups) != 222:
        raise SystemExit(f"Expected 222 coded constituencies, found {len(groups)}")

    output: list[dict[str, object]] = []
    district_by_code: dict[str, str] = {}
    for code, rows in sorted(groups.items()):
        district = district_from_seat(rows[0].get("PARLIMEN"))
        district_by_code[code] = district
        candidates = []
        for row in rows:
            raw_name = row.get("NAMA ATAS KERTAS UNDI") or row.get("NAMA KERTAS UNDI")
            candidates.append((title_name(raw_name), str(row.get("SINGKATAN NAMA PARTI BERTANDING") or "BEBAS").strip(), as_int(row.get("BILANGAN UNDI")), row))
        name_counts = Counter(name for name, _, _, _ in candidates)
        results = [
            (f"{name} ({party})" if name_counts[name] > 1 else name, party, votes, row)
            for name, party, votes, row in candidates
        ]
        results.sort(key=lambda item: (-item[2], item[0]))
        winner, winner_party, _, winner_row = results[0]
        status = str(winner_row.get("StatusCalon") or winner_row.get("STATUS") or "").upper()
        if status not in {"MNG", "MENANG"}:
            raise SystemExit(f"{code} {district}: highest-vote candidate is not marked as winner")
        formal = sum(votes for _, _, votes, _ in results)
        rejected = as_int(winner_row.get("UNDI DITOLAK"))
        unreturned = as_int(winner_row.get("UNDI TAK KEMBALI"))
        enrolment = as_int(winner_row.get("JumlahPemilih"))
        total = formal + rejected + unreturned
        stats = headline_stats.get(code)
        if not enrolment and stats:
            enrolment = as_int(stats["voters_total"])
            if (
                formal != as_int(stats["votes_valid"])
                or rejected != as_int(stats["votes_rejected"])
                or unreturned != as_int(stats["ballots_not_returned"])
                or total != as_int(stats["ballots_issued"])
            ):
                raise SystemExit(f"{code} {district}: SPR totals disagree with supplemental statistics")
        official_turnout = float(winner_row.get("PERATUS UNDI") or 0)
        computed_turnout = total / enrolment * 100 if enrolment else 0
        # SPR publishes turnout rounded to one decimal; three seats differ by up to
        # 0.33 points, so retain the turnout derived from its exact ballot totals.
        if abs(computed_turnout - official_turnout) > 0.35:
            raise SystemExit(f"{code} {district}: turnout does not reconcile")
        official_margin = as_int(winner_row.get("MAJORITI"))
        computed_margin = results[0][2] - results[1][2]
        if official_margin and official_margin != computed_margin:
            raise SystemExit(f"{code} {district}: official majority does not match votes")
        state = str(winner_row.get("NEGERI") or "").strip().title()
        base = {
            "district": district,
            "district_url": f"https://opendata.spr.gov.my/katalog?bahagian=penjalanan-pilihan-raya&tab=0&tahun={year}",
            "distribution_url": f"https://opendata.spr.gov.my/katalog?bahagian=penjalanan-pilihan-raya&tab=0&tahun={year}",
            "elected_member": winner,
            "elected_party": winner_party,
            "enrolment": enrolment,
            "formal_votes": formal,
            "informal_votes": rejected,
            "unreturned_votes": unreturned,
            "total_votes": total,
            "turnout_pct": round(computed_turnout, 2),
            "majority": formal // 2 + 1,
            "electorate_type": state,
            "constituency_code": code,
            "contest_status": "official",
        }
        for row_type, round_number in (("first", 0), ("final", 1)):
            output.extend({
                **base,
                "round_number": round_number,
                "row_type": row_type,
                "excluded_candidate": "",
                "excluded_party": "",
                "candidate": name,
                "candidate_party": party,
                "votes": votes,
            } for name, party, votes, _ in results)
    return output, district_by_code


def build_boundaries(sources: list[dict[str, object]], district_by_code: dict[str, str], year: int) -> dict[str, object]:
    features = []
    for source in sources:
        for feature in source.get("features", []):
            properties = feature.get("properties", {})
            code = str(properties.get("code_parlimen") or "").strip().upper()
            district = district_by_code.get(code)
            if not district:
                raise SystemExit(f"Boundary code has no result: {code}")
            geometry = mapping(shape(feature["geometry"]).simplify(0.0015, preserve_topology=True))
            features.append({
                "type": "Feature",
                "properties": {
                    "district": district,
                    "constituency_code": code,
                    "electorate_type": str(properties.get("state") or "").strip(),
                },
                "geometry": geometry,
            })
    if len(features) != 222 or len({f["properties"]["constituency_code"] for f in features}) != 222:
        raise SystemExit("Expected 222 unique boundary features")
    return {"type": "FeatureCollection", "name": f"malaysia_{year}_parliamentary_constituencies", "features": features}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Malaysia Dewan Rakyat FPTP data")
    parser.add_argument("--year", type=int, choices=sorted(ELECTIONS), default=2022)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    config = ELECTIONS[args.year]
    raw_dir = args.raw_dir or Path(f"tmp/malaysia_{args.year}")

    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    main_path = raw_dir / "keputusan-pru.json"
    delayed_path = raw_dir / "keputusan-prk.json"
    stats_path = raw_dir / "headline_stats_federal.csv"
    ballots_path = raw_dir / "headline_ballots_federal.csv"
    download(session, RESULTS_URL, main_path, args.refresh)
    download(session, DELAYED_RESULTS_URL, delayed_path, args.refresh)
    download(session, HEADLINE_STATS_URL, stats_path, args.refresh)
    download(session, HEADLINE_BALLOTS_URL, ballots_path, args.refresh)
    boundary_paths = []
    for label, boundary_year in config["boundaries"].items():
        url = f"https://lake.electiondata.my/maps/delimitations/{label}_{boundary_year}_parlimen.geojson"
        path = raw_dir / f"{label}_{boundary_year}_parlimen.geojson"
        download(session, url, path, args.refresh)
        boundary_paths.append(path)

    with stats_path.open(newline="", encoding="utf-8-sig") as handle:
        headline_stats = {
            code_from_seat(row["seat"]): row
            for row in csv.DictReader(handle)
            if row["election"] == config["ge"].replace("GE", "GE-")
        }
    if args.year in {2018, 2013}:
        with ballots_path.open(newline="", encoding="utf-8-sig") as handle:
            source_rows = corpus_rows(
                list(csv.DictReader(handle)), headline_stats, config["ge"].replace("GE", "GE-")
            )
    else:
        source_rows = election_rows(
            json.loads(main_path.read_text(encoding="utf-8")),
            json.loads(delayed_path.read_text(encoding="utf-8")),
            args.year,
        )
    rows, district_by_code = build_rows(source_rows, args.year, headline_stats)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / f"malaysia_{args.year}_fpp.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    boundaries = build_boundaries(
        [json.loads(path.read_text(encoding="utf-8")) for path in boundary_paths], district_by_code, args.year
    )
    boundary_path = args.out_dir / f"malaysia_{args.year}_parliamentary_boundaries.geojson"
    boundary_path.write_text(json.dumps(boundaries, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {csv_path} ({len(rows)} rows, 222 constituencies)")
    print(f"Wrote {boundary_path} ({len(boundaries['features'])} features)")


if __name__ == "__main__":
    main()
