#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import requests
from shapely import make_valid
from shapely.geometry import mapping, shape
from shapely.ops import unary_union


EVENTS = {
    2025: {
        "event_id": "31496",
        "checksums": {
            "preferences": "084c7f88e18f62db0b1a18099b081c7ae12680240435a5f4c9aa14e92b29efd5",
            "elected": "e1c24bfd933feb8b23ea6e451d07e39f70f7af59a1cf991c0e1e1ced42071c01",
            "informal": "f2f356b903cb1f7f03078162cdabf93244c03e099f49ff2a44c07a62f7cfb7c0",
            "representation": "95da9c5f664d9b1e51cf5a0c8cf8c631e485a3a663115a224ec3259550a6deab",
            "turnout": "a23862f197d2fa231ccad3745c9194d82c95f4e9650022687f99e66c4d6b312a",
        },
        "national": (15_871_189, 567_305, 16_438_494),
    },
    2022: {
        "event_id": "27966",
        "checksums": {
            "preferences": "4a7a82826db6c85314a24aad34097aea275038ed6fd8ae4c4022d0230d1b70cf",
            "elected": "af7a1eacd959687d1da3de71fc47a81968334f38b697467079b55395fc73ca90",
            "informal": "c67de999ab0f72488592509eddc91de8efeb1af189e02b0c222b07cd0bb49f8d",
            "representation": "362566d8f9270cd3b956c13291728cae50a6eb599e06efc0cbd408d78ca487ac",
            "turnout": "4d9c9f2f9b4c0646bccc40722368576c15628b9490d0cca0b8f111a9c1a478d2",
        },
        "national": (15_040_658, 532_003, 15_572_661),
    },
    2019: {
        "event_id": "24310",
        "checksums": {
            "preferences": "7f83bad440862ef42e1a75a86eb696dff898ac6d45aecc34b5f457d3c3480b69",
            "elected": "bd5cea7bd10ed2936fa5f1b59c3f7884e53bd4b715da80d3891789051da9db2f",
            "informal": "1befc394ab43c7532785e19f7acc973d33539a4ae56fa99c4c2d4d290d8fcc14",
            "representation": "4ea764d9af20784fa459369cc49e8efc7d0247724cbda96e99d46da0e30a4619",
            "turnout": "edde795563d5ebd6490cce5cc1c2eee98531fff2d28a2140997bd229e7d6ad12",
        },
        "national": (14_604_925, 579_160, 15_184_085),
    },
}

SOURCE_NAMES = {
    "preferences": "SenateFirstPrefsByStateByGroupByVoteTypeDownload",
    "elected": "SenateSenatorsElectedDownload",
    "informal": "SenateInformalByStateDownload",
    "representation": "SenatePartyRepresentationDownload",
    "turnout": "SenateTurnoutByStateDownload",
}
BOUNDARY_URL = (
    "https://geo.abs.gov.au/arcgis/rest/services/ASGS2021/STE/FeatureServer/1/query"
    "?where=state_code_2021%3C%3D%278%27"
    "&outFields=state_code_2021%2Cstate_name_2021"
    "&returnGeometry=true&outSR=4326&maxAllowableOffset=0.02"
    "&geometryPrecision=4&f=geojson"
)
BOUNDARY_PAGE = "https://geo.abs.gov.au/arcgis/rest/services/ASGS2021/STE/FeatureServer/1"
BOUNDARY_CHECKSUM = "a44983fe8d4f04932a3f4a2a9404cb761583f719c5bcb24d1b7e0c231e26f985"
STATE_CODES = {
    "NSW": ("1", "New South Wales"),
    "VIC": ("2", "Victoria"),
    "QLD": ("3", "Queensland"),
    "SA": ("4", "South Australia"),
    "WA": ("5", "Western Australia"),
    "TAS": ("6", "Tasmania"),
    "NT": ("7", "Northern Territory"),
    "ACT": ("8", "Australian Capital Territory"),
}
FIELDS = (
    "district", "district_url", "distribution_url", "elected_member", "elected_party",
    "elected_members", "elected_parties", "members_to_elect", "quota", "enrolment",
    "formal_votes", "informal_votes", "total_votes", "turnout_pct", "majority",
    "round_number", "row_type", "excluded_candidate", "excluded_party", "candidate",
    "candidate_party", "votes", "electorate_type", "constituency_code",
    "contest_status", "result_note",
)


def download(url: str, path: Path, refresh: bool) -> Path:
    if path.exists() and path.stat().st_size and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=300)
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def require_sha256(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"{path}: checksum changed to {actual}; expected {expected}")


def read_aec(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        next(handle)
        return list(csv.DictReader(handle))


def source_url(event_id: str, key: str) -> str:
    stem = SOURCE_NAMES[key]
    return f"https://results.aec.gov.au/{event_id}/Website/Downloads/{stem}-{event_id}.csv"


def source_paths(
    cache_dir: Path, config: dict[str, object], refresh: bool
) -> dict[str, Path]:
    event_id = str(config["event_id"])
    paths = {}
    for key, checksum in config["checksums"].items():
        path = download(
            source_url(event_id, key),
            cache_dir / f"{event_id}_{SOURCE_NAMES[key]}.csv",
            refresh,
        )
        require_sha256(path, checksum)
        paths[key] = path
    return paths


def build_boundaries(source_path: Path, data_dir: Path) -> None:
    require_sha256(source_path, BOUNDARY_CHECKSUM)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    by_abs_code = {code: ab for ab, (code, _) in STATE_CODES.items()}
    features = []
    for feature in source.get("features", []):
        properties = feature.get("properties", {})
        abs_code = str(properties["state_code_2021"])
        if abs_code not in by_abs_code:
            continue
        state_ab = by_abs_code[abs_code]
        expected_name = STATE_CODES[state_ab][1]
        if properties["state_name_2021"] != expected_name:
            raise SystemExit(f"Unexpected ABS state name for {state_ab}")
        geometry = make_valid(shape(feature["geometry"]))
        geometry = make_valid(geometry.simplify(0.01, preserve_topology=True))
        if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            parts = []
            pending = list(getattr(geometry, "geoms", []))
            while pending:
                part = pending.pop()
                if part.geom_type == "Polygon":
                    parts.append(part)
                else:
                    pending.extend(getattr(part, "geoms", []))
            geometry = make_valid(unary_union(parts))
        if geometry.is_empty or not geometry.is_valid:
            raise SystemExit(f"Invalid boundary for {state_ab}")
        features.append({
            "type": "Feature",
            "properties": {
                "district": expected_name,
                "constituency_code": f"AU-SEN-{state_ab}",
                "state_ab": state_ab,
                "source": BOUNDARY_PAGE,
            },
            "geometry": mapping(geometry),
        })
    if len(features) != 8:
        raise SystemExit(f"Expected 8 state/territory boundaries, got {len(features)}")
    output = {"type": "FeatureCollection", "features": sorted(
        features, key=lambda feature: feature["properties"]["state_ab"]
    )}
    (data_dir / "australia_senate_state_boundaries.geojson").write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def senator_name(row: dict[str, str]) -> str:
    return f"{row['Surname'].strip()}, {row['GivenNm'].strip()}"


def representation_code(year: int, state_ab: str, party_ab: str) -> str:
    if party_ab == "GVIC":
        return "GRN"
    if state_ab in {"NSW", "VIC"} and party_ab in {"LP", "NP"}:
        return "LPNP"
    if year == 2019 and state_ab == "NSW" and party_ab == "ALP":
        return "ALPC"
    return party_ab


def build_election_rows(
    year: int, config: dict[str, object], paths: dict[str, Path]
) -> list[dict[str, object]]:
    event_id = str(config["event_id"])
    preferences: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_aec(paths["preferences"]):
        if int(row["TotalVotes"]) > 0:
            preferences[row["StateAb"]].append(row)
    informal = {row["StateAb"]: row for row in read_aec(paths["informal"])}
    turnout = {row["StateAb"]: row for row in read_aec(paths["turnout"])}
    elected: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_aec(paths["elected"]):
        elected[row["StateAb"]].append(row)
    for rows in elected.values():
        rows.sort(key=lambda row: int(row["ElectedOrder"]))

    elected_party_codes = Counter(
        representation_code(year, state_ab, row["PartyAb"])
        for state_ab, state_rows in elected.items()
        for row in state_rows
    )
    representation = {
        row["PartyAb"]: int(row["TOTAL"])
        for row in read_aec(paths["representation"])
        if int(row["TOTAL"])
    }
    if dict(elected_party_codes) != representation:
        raise SystemExit(
            f"{year}: elected senator parties do not match party representation"
        )
    if sum(representation.values()) != 40:
        raise SystemExit(f"{year}: expected 40 senators elected")

    rows: list[dict[str, object]] = []
    national_formal = national_informal = national_total = 0
    for state_ab, (_, state_name) in STATE_CODES.items():
        state_preferences = preferences[state_ab]
        if not state_preferences:
            raise SystemExit(f"{year}: no first preferences for {state_ab}")
        meta = informal[state_ab]
        turn = turnout[state_ab]
        formal = int(meta["FormalVotes"])
        informal_votes = int(meta["InformalVotes"])
        total = int(meta["TotalVotes"])
        enrolment = int(turn["Enrolment"])
        if sum(int(row["TotalVotes"]) for row in state_preferences) != formal:
            raise SystemExit(f"{year} {state_ab}: group/formal mismatch")
        if formal + informal_votes != total or int(turn["Turnout"]) != total:
            raise SystemExit(f"{year} {state_ab}: ballot-total mismatch")
        members_to_elect = 2 if state_ab in {"ACT", "NT"} else 6
        state_elected = elected[state_ab]
        if len(state_elected) != members_to_elect:
            raise SystemExit(
                f"{year} {state_ab}: expected {members_to_elect} elected senators"
            )
        elected_members = "; ".join(senator_name(row) for row in state_elected)
        elected_parties = "; ".join(row["PartyNm"].strip() for row in state_elected)
        ranked_groups = sorted(
            state_preferences,
            key=lambda row: (-int(row["TotalVotes"]), row["GroupNm"]),
        )
        primary_lead = int(ranked_groups[0]["TotalVotes"]) - int(ranked_groups[1]["TotalVotes"])
        base = {
            "district": state_name,
            "district_url": (
                f"https://results.aec.gov.au/{event_id}/Website/"
                f"SenateStateFirstPrefsByGroup-{event_id}-{state_ab}.htm"
            ),
            "distribution_url": (
                f"https://results.aec.gov.au/{event_id}/Website/External/"
                f"SenateStateDop-{event_id}-{state_ab}.pdf"
            ),
            "elected_member": elected_members,
            "elected_party": elected_parties,
            "elected_members": elected_members,
            "elected_parties": elected_parties,
            "members_to_elect": members_to_elect,
            "quota": formal // (members_to_elect + 1) + 1,
            "enrolment": enrolment,
            "formal_votes": formal,
            "informal_votes": informal_votes,
            "total_votes": total,
            "turnout_pct": turn["TurnoutPercentage"],
            "majority": primary_lead,
            "round_number": 0,
            "row_type": "first",
            "excluded_candidate": "",
            "excluded_party": "",
            "electorate_type": "State / territory Senate contest",
            "constituency_code": f"AU-SEN-{state_ab}",
            "contest_status": "official",
            "result_note": (
                "Official AEC first-preference totals by Senate group and final "
                "list of elected senators. Full transfer counts are intentionally "
                "outside this compact view."
            ),
        }
        for group in ranked_groups:
            group_name = group["GroupNm"].strip()
            rows.append({
                **base,
                "candidate": group_name,
                "candidate_party": group_name,
                "votes": int(group["TotalVotes"]),
            })
        national_formal += formal
        national_informal += informal_votes
        national_total += total
    expected = tuple(config["national"])
    actual = (national_formal, national_informal, national_total)
    if actual != expected:
        raise SystemExit(f"{year}: national ballots changed; expected {expected}, got {actual}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Australian Senate 2025, 2022 and 2019 state views."
    )
    parser.add_argument("--cache-dir", type=Path, default=Path("tmp/aus_senate"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)

    boundary_path = download(
        BOUNDARY_URL, args.cache_dir / "states.geojson", args.refresh
    )
    build_boundaries(boundary_path, args.data_dir)
    for year, config in EVENTS.items():
        paths = source_paths(args.cache_dir, config, args.refresh)
        rows = build_election_rows(year, config, paths)
        output = args.data_dir / f"australia_senate_{year}_state_fpp.csv"
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        print(f"{output.name}: 8 contests, {len(rows)} group rows")
    print("Built three Australian Senate election views.")


if __name__ == "__main__":
    main()
