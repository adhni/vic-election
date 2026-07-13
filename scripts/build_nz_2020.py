#!/usr/bin/env python3
from __future__ import annotations

import build_nz_2023 as builder


builder.ELECTION_YEAR = 2020
builder.RESULT_BASE = "https://archive.electionresults.govt.nz/electionresults_2020/statistics"
builder.MIRROR_BASE = "https://r.jina.ai/https://media.election.net.nz/electionresults_2020/statistics"
builder.CANDIDATE_LIST_URL = "https://en.wikipedia.org/wiki/Candidates_in_the_2020_New_Zealand_general_election_by_electorate"
builder.PARTY_ORDER = [
    "ACT New Zealand",
    "Advance New Zealand",
    "Aotearoa Legalise Cannabis Party",
    "Green Party",
    "HeartlandNZ",
    "Labour Party",
    "Māori Party",
    "National Party",
    "New Conservative",
    "New Zealand First Party",
    "NZ Outdoors Party",
    "ONE Party",
    "Social Credit",
    "Sustainable New Zealand Party",
    "TEA Party",
    "The Opportunities Party",
    "Vision New Zealand",
]
builder.PARTY_NAMES.update({
    "Advance NZ": "Advance New Zealand",
    "HeartlandNZ": "HeartlandNZ",
    "Māori": "Māori Party",
    "New Conservative": "New Conservative",
    "NZ Outdoors": "NZ Outdoors Party",
    "ONE": "ONE Party",
    "Social Credit": "Social Credit",
    "Sustainable NZ": "Sustainable New Zealand Party",
    "TEA": "TEA Party",
})


if __name__ == "__main__":
    builder.main()
