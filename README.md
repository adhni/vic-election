# International Election Results Explorer

A static HTML data app for exploring lower-house elections across several countries plus Indonesian, Philippine, and Mexican presidential elections.

The app is map-first and party/bloc-first:

- winner map with Labor, Coalition, Greens, Independent, and Other grouping
- zoomable/pannable seat boundary map for the selected election year
- election-wide rankings for closest seats, largest margins, changed results, and winner transfer gains
- paired country and election selectors, with Australian elections grouped by federal or state/territory jurisdiction
- seat search, seat picker, bloc filter, close-seat filter, and preference-changed filter
- first preference, transfer round, progressive chart, and raw row views
- exact party and candidate detail preserved inside each seat
- New Zealand candidate-vote and party-vote views with separate general and Māori electorate map layers
- United Kingdom constituency results and winner-party maps for the 2024, 2019, and 2017 general elections
- Malaysian constituency results and winner-party maps for the 2022, 2018, and 2013 general elections (GE15–GE13)
- Singapore electoral-division results, GRC team membership, and winner-party maps for the 2025, 2020, and 2015 general elections
- Canadian riding results and winner-party maps for the 2025 and 2021 federal elections
- Indian constituency results and winner-party map for the 2024 Lok Sabha election
- German Erststimme and Zweitstimme results for all 299 constituencies in the 2025, 2021, and 2017 Bundestag elections
- Netherlands, Norway, and Sweden parliamentary results mapped by municipality for two elections each
- Japanese single-member constituency results and winner-party maps for the 2026 and 2024 House elections
- United States congressional-district results and winner-party map for the 2024 House election
- Indonesian presidential results for 2024, 2019, and 2014, with election-year province and kabupaten/kota views
- Separate Philippine presidential and vice-presidential results for 2022, mapped by domestic province/city certificate of canvass
- Mexican presidential results for 2024, mapped across all 300 federal electoral districts

No build step is needed. It is plain HTML/CSS/JavaScript.

## Open the app

Live site:

```text
https://adhni.github.io/vic-election/
```

Serve the folder locally so the CSV and GeoJSON files can auto-load:

```bash
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000/
```

The app auto-loads the selected election:

```text
data/vic_2022_preferences_long.csv
data/vic_2022_district_boundaries.geojson
```

Victorian state election options use the same naming pattern:

```text
data/vic_2014_preferences_long.csv
data/vic_2018_preferences_long.csv
data/vic_2014_district_boundaries.geojson # shared 2012-2013 redivision map for 2014 and 2018
data/vic_2010_preferences_long.csv
data/vic_2010_district_boundaries.geojson
data/vic_2006_preferences_long.csv
data/vic_2006_district_boundaries.geojson
```

NSW state coverage currently includes `2023`, `2019`, `2015`, and `2011`:

```text
data/nsw_2023_preferences_long.csv
data/nsw_2023_district_summary.csv
data/nsw_2023_district_boundaries.geojson
data/nsw_2019_preferences_long.csv
data/nsw_2019_district_summary.csv
data/nsw_2019_district_boundaries.geojson
data/nsw_2015_preferences_long.csv
data/nsw_2015_district_summary.csv
data/nsw_2015_district_boundaries.geojson
data/nsw_2011_preferences_long.csv
data/nsw_2011_district_summary.csv
data/nsw_2011_district_boundaries.geojson
```

Queensland state coverage currently includes `2024` and `2020`:

```text
data/qld_2024_preferences_long.csv
data/qld_2024_district_summary.csv
data/qld_2024_district_boundaries.geojson
data/qld_2020_preferences_long.csv
data/qld_2020_district_summary.csv
data/qld_2020_district_boundaries.geojson
```

South Australia state coverage currently includes `2022` and `2018`:

```text
data/sa_2022_preferences_long.csv
data/sa_2022_district_summary.csv
data/sa_2022_district_boundaries.geojson
data/sa_2018_preferences_long.csv
data/sa_2018_district_summary.csv
data/sa_2018_district_boundaries.geojson
```

Western Australia state coverage currently includes `2025` and `2021`:

```text
data/wa_2025_preferences_long.csv
data/wa_2025_district_summary.csv
data/wa_2025_district_boundaries.geojson
data/wa_2021_preferences_long.csv
data/wa_2021_district_summary.csv
data/wa_2021_district_boundaries.geojson
```

Northern Territory coverage currently includes `2024` and `2020`:

```text
data/nt_2024_preferences_long.csv
data/nt_2024_district_summary.csv
data/nt_2024_district_boundaries.geojson
data/nt_2020_preferences_long.csv
data/nt_2020_district_summary.csv
data/nt_2020_district_boundaries.geojson
```

Tasmania state coverage currently includes the multi-member House of Assembly `2025`, `2024`, and `2021` elections:

```text
data/tas_2025_preferences_long.csv
data/tas_2025_district_summary.csv
data/tas_2025_district_boundaries.geojson
data/tas_2024_preferences_long.csv
data/tas_2024_district_summary.csv
data/tas_2024_district_boundaries.geojson
data/tas_2021_preferences_long.csv
data/tas_2021_district_summary.csv
data/tas_2021_district_boundaries.geojson
```

New Zealand coverage currently includes the `2023` and `2020` general elections. Each shows all 65 general and 7 Māori electorates, candidate and party votes, the nationwide MMP result, and a General/Māori map-layer toggle:

```text
data/nz_2023_mmp.csv
data/nz_2023_electorate_boundaries.geojson
data/nz_2020_mmp.csv
data/nz_2020_electorate_boundaries.geojson
```

Electorate MPs are elected by first past the post, so preference-round and transfer-gain views are hidden for these elections. In 2023, Port Waikato is retained as a cancelled electorate contest with its valid party vote; the later by-election is not merged into the general-election result.

United Kingdom coverage currently includes the 2024, 2019, and 2017 general elections, each with all 650 House of Commons constituencies across England, Scotland, Wales, and Northern Ireland:

```text
data/uk_2024_fpp.csv
data/uk_2024_constituency_boundaries.geojson
data/uk_2019_fpp.csv
data/uk_2019_constituency_boundaries.geojson
data/uk_2017_fpp.csv
data/uk_2017_constituency_boundaries.geojson
```

The UK election uses first past the post, so preference-transfer views are hidden. Each candidate result is stored once; the app reconstructs the identical final standing in memory. Results come from UK Parliament and boundaries from the Office for National Statistics.

Malaysia coverage currently includes the 2022 GE15, 2018 GE14, and 2013 GE13 elections, each with all 222 Dewan Rakyat constituencies:

```text
data/malaysia_2022_fpp.csv
data/malaysia_2022_parliamentary_boundaries.geojson
data/malaysia_2018_fpp.csv
data/malaysia_2018_parliamentary_boundaries.geojson
data/malaysia_2013_fpp.csv
data/malaysia_2013_parliamentary_boundaries.geojson
```

Malaysia also uses first past the post, so preference-transfer views are hidden. GE15 uses official SPR result files; GE14 and GE13 use the CC0 Malaysian Election Corpus to retain complete candidate and turnout metadata where SPR's older export is incomplete. Each map combines the Peninsular, Sabah, and Sarawak delimitation datasets in force for that election.

Singapore coverage currently includes the 2025, 2020, and 2015 general elections, preserving their different SMC/GRC maps and 97-, 93-, and 89-member Parliaments:

```text
data/singapore_2025_fpp.csv
data/singapore_2025_electoral_boundaries.geojson
data/singapore_2020_fpp.csv
data/singapore_2020_electoral_boundaries.geojson
data/singapore_2015_fpp.csv
data/singapore_2015_electoral_boundaries.geojson
```

The app treats each GRC party slate as one contest entry while preserving all elected team members. Party summaries count MPs rather than divisions. Candidate/team votes come from the Elections Department Singapore final results, turnout metadata from the official Statements of Poll, and boundaries from data.gov.sg. Marine Parade–Braddell Heights is retained as uncontested with no invented poll totals.

Canada coverage currently includes the 2025 and 2021 federal elections, covering every House of Commons riding across the ten provinces and three territories:

```text
data/canada_2025_fpp.csv
data/canada_2025_federal_boundaries.geojson
data/canada_2021_fpp.csv
data/canada_2021_federal_boundaries.geojson
```

Canada uses first past the post, so preference-transfer views are hidden. The datasets preserve all 1,959 candidates across 343 ridings in 2025 and all 2,010 candidates across 338 ridings in 2021, with exact valid and rejected ballot totals, calculated turnout, province/territory metadata, and election-specific riding codes. Results and matching boundaries for both elections come from Elections Canada.

India coverage currently includes the 2024 Lok Sabha election, with all 543 parliamentary constituencies across the states and union territories:

```text
data/india_2024_fpp.csv
data/india_2024_parliamentary_boundaries.geojson
```

India uses first past the post, so preference-transfer views are hidden. The dataset preserves all 8,360 candidates and 542 NOTA options. Candidate totals and turnout metadata are reconciled against the Election Commission of India's final statistical report. Esri India's 2024 parliamentary layer supplies the matching election-specific boundaries and an independent winner/margin check outside Assam, whose layer attributes are shifted between the newly delimited seats. Surat is retained as an uncontested return with no invented votes or turnout.

Germany coverage includes the 2025, 2021, and 2017 Bundestag elections, with official Erststimme and Zweitstimme totals for all 299 constituencies:

```text
data/germany_2025_bundestag.csv
data/germany_2025_constituency_boundaries.geojson
data/germany_2021_bundestag.csv
data/germany_2021_constituency_boundaries.geojson
data/germany_2017_bundestag.csv
data/germany_2017_constituency_boundaries.geojson
```

The 2021 option uses the certified totals after the partial Berlin repeat vote in 2024. For 2025, the app separately identifies the Erststimme leader and whether that leader actually received a constituency mandate under the new Zweitstimme-coverage rule; 23 local leaders did not. The displayed vote choices use the official result file's party or independent-group labels.

See [`docs/germany_bundestag.md`](docs/germany_bundestag.md) for sources, validation, and boundary attribution.

Japan coverage includes the 8 February 2026 and 27 October 2024 House of Representatives elections, with all 289 single-member constituency contests:

```text
data/japan_2026_house_fpp.csv
data/japan_2024_house_fpp.csv
data/japan_2022_house_constituency_schematic.geojson
```

Japan uses parallel voting: these views cover the 289 first-past-the-post constituency seats, while the separate regional proportional ballot elects another 176 members. Candidate figures are validated against the Ministry of Internal Affairs and Communications result publications. The 2024 transcription is also reconciled by constituency and candidate-vote total with Yukiyanai's public academic dataset. The official national party summary allocates a tiny number of ambiguous ballots fractionally; the candidate tables publish whole-vote figures, which the app preserves and explicitly discloses. District turnout and invalid-ballot metadata are not invented.

Both elections use the constituency allocation introduced by the 2022 redistribution. The compact shared map is derived from the Wikimedia/NHK post-redistribution SVG and retains its metropolitan insets. It is a schematic discovery map, not a legal-boundary GIS layer.

Thailand coverage includes the 8 February 2026 general election, with all 400 single-member constituency contests and all 3,527 candidates across 77 provinces:

```text
data/thailand_2026_fpp.csv
data/thailand_2026_constituency_cartogram.geojson
```

Thailand used parallel voting: 400 constituency MPs were elected by first past the post and 100 party-list MPs were allocated from a separate nationwide ballot. This view covers the constituency ballot; it does not present the party-list vote as if it were a district contest. Results come from the Thai PBS English machine feed backed by ECT data. The final outstanding Suphan Buri 2 seat, certified on 8 April after a recount, is updated to the final 500-member House result, giving Bhumjaithai 173 constituency seats and 192 seats overall. Its post-recount non-candidate ballot and turnout fields remain unavailable instead of being invented.

The map is Thai PBS's equal-area 400-seat constituency cartogram. Every cell opens the corresponding result, but the cells are explicitly labelled as a cartogram and are not legal electoral-boundary polygons.

France coverage includes both rounds of the 2022, 2017, 2012, and 2007 presidential elections:

```text
data/france_{year}_president_round_{1|2}_department_fpp.csv
data/france_{year}_president_round_{1|2}_region_fpp.csv
data/france_{year}_department_boundaries.geojson
data/france_{year}_region_boundaries.geojson
```

Each contest can switch between departments/department-equivalent overseas territories and regions. Results are definitive French Ministry of the Interior returns. The 2007 and 2012 maps preserve the pre-2016 metropolitan region structure, while 2017 and 2022 use the later regions. French citizens voting abroad contribute to the official national shares but are not assigned a false map polygon. Overseas areas are moved into compact schematic insets so metropolitan France remains legible; the inset positions and scales are explicitly disclosed as non-geographic.

Portugal and Spain coverage includes two recent legislative elections from each country:

```text
data/portugal_{2025|2024}_legislative_fpp.csv
data/portugal_{2025|2024}_legislative_boundaries.geojson
data/spain_{2023|2019}_congress_fpp.csv
data/spain_{2023|2019}_congress_boundaries.geojson
```

These are multi-member closed-list proportional elections, not FPTP contests. The compact app rows use its local-leader view to map and rank the party list with the most votes in each electoral district or constituency; the district panel separately shows the number of seats allocated, and the national summary shows the actual Parliament seat totals. Portugal uses the Ministry of Internal Administration's official results and domestic inset map. Its four foreign-constituency seats remain in the 230-seat national summary without being assigned false domestic polygons. Spain uses the Central Electoral Board's certified BOE tables and Eurostat GISCO province geometry. The corrected November 2019 BOE tables are used, including the Zaragoza Más País–Chunta Aragonesista–Equo correction.

Northern Europe coverage includes two parliamentary elections from each of the Netherlands, Norway, and Sweden:

```text
data/netherlands_{2025|2023}_house_fpp.csv
data/netherlands_{2025|2023}_house_boundaries.geojson
data/norway_{2025|2021}_storting_fpp.csv
data/norway_{2025|2021}_storting_boundaries.geojson
data/sweden_{2022|2018}_riksdag_fpp.csv
data/sweden_{2022|2018}_riksdag_boundaries.geojson
```

These views map and rank the locally leading party across 342 Dutch, 356/357 Norwegian, and 290 Swedish municipalities. Municipalities do not allocate national MPs: the national Parliament chips show the actual 150-, 169-, and 349-seat outcomes. Results come from the Kiesraad, Valgdirektoratet, and Valmyndigheten, with annual Eurostat GISCO LAU geometry. Dutch Caribbean public-body and postal-vote totals remain in the certified national outcome but are not placed on a false mainland polygon.

Philippines coverage includes the separate presidential and vice-presidential ballots held on 9 May 2022:

```text
data/philippines_2022_president_fpp.csv
data/philippines_2022_vice_president_fpp.csv
data/philippines_2022_coc_boundaries.geojson
```

Both offices were elected independently by nationwide plurality. The app therefore provides two linked election options rather than presenting Marcos and Duterte as a single combined ballot. Each map uses 107 domestic reporting areas: 81 province-level certificates of canvass and 26 separately canvassed cities/NCR units. The Special Geographic Area COC is combined with Cotabato because its 63 barangays cannot be separated from the official municipal geometry. Absentee and overseas votes appear in the official national shares but are not falsely drawn as domestic map areas.

Local candidate figures follow the pinned congressional COC table and boundaries are dissolved from the Philippine Statistics Authority municipal layer. Invalid/blank ballots and turnout are available nationally but not consistently by mapped COC area, so the app does not invent local turnout. The published detailed COC transcription has small arithmetic differences from the adopted national resolution for several minor candidates; local figures are preserved as published, while the national cards use Resolution of Both Houses No. 1. The builder locks the exact known differences so they cannot change silently.

Mexico coverage includes the presidential election held on 2 June 2024:

```text
data/mexico_2024_president_fpp.csv
data/mexico_2024_federal_district_boundaries.geojson
```

The map covers all 300 federal electoral districts and shows the locally leading presidential candidate in each district. Claudia Sheinbaum led in 275 districts and Xóchitl Gálvez in 25; the districts are analytical reporting areas and do not elect separate presidents. The dataset aggregates INE's final district-computation polling-place records, combines each coalition's separate and joint party ballot columns into its presidential candidacy, and reconciles candidate, non-registered, null, total-ballot, nominal-list, and turnout fields exactly. Official national shares include special-vote records that are not assigned to a mapped district. Boundaries are the matching 300-district layer from INE's national electoral geographic framework.

South Korea coverage includes the presidential elections held on 3 June 2025 and 9 March 2022:

```text
data/south_korea_2025_president_fpp.csv
data/south_korea_2025_municipal_boundaries.geojson
data/south_korea_2022_president_fpp.csv
data/south_korea_2022_municipal_boundaries.geojson
```

Both views show the locally leading presidential candidate across all municipality/election-commission reporting areas, while making clear that the president is elected by one nationwide plurality vote. The result files are official National Election Commission polling-district returns aggregated to 252 areas in 2025 and 250 areas in 2022. The maps use Statistics Korea SGIS municipal geometry. For 2025, Hwaseong's two commission areas are combined into its municipal polygon; for 2022, the builder restores the former unified Bucheon reporting area and Gunwi's election-time placement in North Gyeongsang.

United States coverage currently includes the 2024 House election, covering all 435 voting congressional districts across the 50 states:

```text
data/us_2024_house_fpp.csv
data/us_2024_congressional_boundaries.geojson
```

The dataset parses the U.S. House Clerk's official candidate totals and reconciles every district against its published recapitulation. New York and Connecticut fusion-party lines are combined with their candidates, Maine's duplicated continuing-ballot subtotal is excluded, and all unopposed returns are retained without invented votes. Alaska's published lines are first-choice totals, while Maine's 2nd district reports the final continuing candidates; transfer rounds are not reconstructed. Registered-voter and turnout values remain unavailable because the nationwide Clerk publication does not provide a consistent electorate denominator. Boundaries are the Census Bureau's 119th Congress cartographic districts used for the 2024 election cycle; Alaska's Aleutian coordinates are unwrapped across the antimeridian for the app's map projection. DC and territorial delegate districts are outside this 435-seat scope.

Indonesia coverage includes the 2024, 2019, and 2014 presidential elections at both province and kabupaten/kota level:

```text
data/indonesia_2024_president_province_fpp.csv
data/indonesia_2024_province_boundaries.geojson
data/indonesia_2024_president_kabupaten_kota_fpp.csv
data/indonesia_2024_kabupaten_kota_boundaries.geojson
data/indonesia_2019_president_province_fpp.csv
data/indonesia_2019_province_boundaries.geojson
data/indonesia_2019_president_kabupaten_kota_fpp.csv
data/indonesia_2014_president_province_fpp.csv
data/indonesia_2014_province_boundaries.geojson
data/indonesia_2014_president_kabupaten_kota_fpp.csv
data/indonesia_2014_kabupaten_kota_boundaries.geojson
```

Use the map's **Province / Kabupaten-Kota** switch to move between all 38 provinces and all 514 local areas. Province totals are certified results from KPU Decision 360/2024. The structured kabupaten/kota rows preserve KPU administrative codes and are sourced from a CC0 Wikimedia table whose rows link to KPU's Sirekap recapitulation JSON. KPU's Satu Peta boundary endpoints supply both geographic levels. The app describes winners as local vote leaders because these areas do not elect separate presidents.

The published Papua Tengah kabupaten/kota rows sum to 1,035,277 valid votes, which is 67,005 below KPU's certified province total of 1,102,282. The app uses the certified total in the province view, preserves the published local figures without redistributing the difference, and shows this disclosure on every affected detail page.

The 2019 view preserves the election's 34-province hierarchy and all 514 local reporting areas. Local totals reconcile exactly to the province totals. The compact 2024 local boundary file is reused because no kabupaten/kota split occurred between the elections; renamed areas use their current display labels, while every row retains its 2019 province membership. The 2019 province polygons are dissolved from that historical hierarchy, including the pre-split Papua and Papua Barat provinces.

The 2014 province view uses certified KPU totals for 33 reporting provinces, with North Kalimantan included in East Kalimantan as it was in the official recapitulation. Its 497-area local view aggregates KawalPemilu's archived KPU C1-scan digitisation, covering 98.24% of the certified domestic valid vote. Missing votes are not estimated; four Papua units with no digitised candidate totals are explicitly shown as unavailable. Seventeen modern child districts are dissolved into their election-time parent polygons, so later administrative splits never receive copied historical votes.

Australia-wide federal `2025`, `2022`, `2019`, and `2016` options use authoritative Australian Electoral Commission House results and matching national AEC federal division boundary datasets:

```text
data/federal_2025_au_preferences_long.csv
data/federal_2025_au_district_summary.csv
data/federal_2025_au_division_boundaries.geojson
data/federal_2022_au_preferences_long.csv
data/federal_2022_au_district_summary.csv
data/federal_2022_au_division_boundaries.geojson
data/federal_2019_au_preferences_long.csv
data/federal_2019_au_district_summary.csv
data/federal_2019_au_division_boundaries.geojson
data/federal_2016_au_preferences_long.csv
data/federal_2016_au_district_summary.csv
data/federal_2016_au_division_boundaries.geojson
```

These national files replace the former duplicate Victoria-only copies for the same four years. Select the Australia-wide election to access Victorian divisions alongside the rest of the country.

Victoria-only federal options remain available for `2013`, `2010`, and `2007`, where Australia-wide datasets have not yet been added. For `2016`, `2019`, `2022`, and `2025`, use the Australia-wide option, which already contains every Victorian division:

```text
data/federal_2013_vic_preferences_long.csv
data/federal_2013_vic_district_summary.csv
data/federal_2013_vic_division_boundaries.geojson
data/federal_2010_vic_preferences_long.csv
data/federal_2010_vic_district_summary.csv
data/federal_2010_vic_division_boundaries.geojson
data/federal_2007_vic_preferences_long.csv
data/federal_2007_vic_district_summary.csv
```

The 2007 and 2010 Victoria-only federal entries share the byte-identical AEC 2010 boundary file instead of storing a duplicate copy.

If the generated CSV is unavailable, embedded sample districts are used. Manual CSV upload is available under **Data tools**.

The rankings panel is election-scoped rather than filter-scoped. It updates when the election selector changes, and clicking any ranking row opens that district or division in the existing detail view.

## Data Files

```text
data/vic_2022_preferences_long.csv        # long preference-count rows, 87 districts
data/vic_2022_district_summary.csv        # district-level result summary
data/vic_2022_district_boundaries.geojson # 2022 district boundary polygons
data/vic_2018_preferences_long.csv        # 2018 long preference-count rows
data/vic_2018_district_summary.csv        # 2018 district-level result summary
data/vic_2014_preferences_long.csv        # 2014 long preference-count rows
data/vic_2014_district_summary.csv        # 2014 district-level result summary
data/vic_2014_district_boundaries.geojson # shared 2014 and 2018 district boundary polygons
data/vic_2010_preferences_long.csv        # 2010 long preference-count rows
data/vic_2010_district_summary.csv        # 2010 district-level result summary
data/vic_2010_district_boundaries.geojson # 2001 state assembly district boundary polygons
data/vic_2006_preferences_long.csv        # 2006 long preference-count rows
data/vic_2006_district_summary.csv        # 2006 district-level result summary
data/vic_2006_district_boundaries.geojson # 2001 state assembly district boundary polygons
data/nsw_2023_preferences_long.csv        # NSWEC 2023 Legislative Assembly long preference-count rows
data/nsw_2023_district_summary.csv        # NSWEC 2023 district-level result summary
data/nsw_2023_district_boundaries.geojson # NSW 2021 redistribution boundaries used at the 2023 election
data/nsw_2019_preferences_long.csv        # NSWEC 2019 Legislative Assembly long preference-count rows
data/nsw_2019_district_summary.csv        # NSWEC 2019 district-level result summary
data/nsw_2019_district_boundaries.geojson # NSW 2013 redistribution boundaries used at the 2019 election
data/nsw_2015_preferences_long.csv        # NSWEC 2015 Legislative Assembly long preference-count rows
data/nsw_2015_district_summary.csv        # NSWEC 2015 district-level result summary
data/nsw_2015_district_boundaries.geojson # NSW 2013 redistribution boundaries used at the 2015 election
data/nsw_2011_preferences_long.csv        # NSWEC 2011 Legislative Assembly first-preference and final preferred rows
data/nsw_2011_district_summary.csv        # NSWEC 2011 district-level result summary
data/nsw_2011_district_boundaries.geojson # historical 2011 NSW district polygons adapted from the Terria ABS 2011 SED tiles
data/qld_2024_preferences_long.csv        # ECQ 2024 Legislative Assembly long preference-count rows
data/qld_2024_district_summary.csv        # ECQ 2024 district-level result summary
data/qld_2024_district_boundaries.geojson # Queensland 2017 redistribution boundaries used at the 2024 election
data/qld_2020_preferences_long.csv        # ECQ 2020 Legislative Assembly long preference-count rows
data/qld_2020_district_summary.csv        # ECQ 2020 district-level result summary
data/qld_2020_district_boundaries.geojson # Queensland 2017 redistribution boundaries used at the 2020 election
data/sa_2022_preferences_long.csv         # ECSA 2022 House of Assembly first-preference and final distribution rows
data/sa_2022_district_summary.csv         # ECSA 2022 House of Assembly district-level result summary
data/sa_2022_district_boundaries.geojson  # Data SA 2022 state electorate boundaries
data/wa_2025_preferences_long.csv         # WAEC 2025 Assembly first-preference and final preferred rows
data/wa_2025_district_summary.csv         # WAEC 2025 Assembly district-level result summary
data/wa_2025_district_boundaries.geojson  # Landgate 2023 distribution boundaries used at the 2025 election
data/wa_2021_preferences_long.csv         # WAEC 2021 Assembly first-preference and final preferred rows
data/wa_2021_district_summary.csv         # WAEC 2021 Assembly district-level result summary
data/wa_2021_district_boundaries.geojson  # ABS 2021 SED approximation of the WA 2019 distribution
data/nt_2024_preferences_long.csv         # NTEC 2024 Legislative Assembly first-preference and final TCP rows
data/nt_2024_district_summary.csv         # NTEC 2024 electorate-level result summary
data/nt_2024_district_boundaries.geojson  # ABS 2024 NT State Electoral Division boundaries
data/nt_2020_preferences_long.csv         # NTEC 2020 Legislative Assembly first-preference and final TCP rows
data/nt_2020_district_summary.csv         # NTEC 2020 electorate-level result summary
data/nt_2020_district_boundaries.geojson  # ABS 2021 NT State Electoral Division boundaries
data/tas_2025_preferences_long.csv        # TEC 2025 House of Assembly Hare-Clark first and final count rows
data/tas_2025_district_summary.csv        # TEC 2025 division-level elected member summary
data/tas_2025_district_boundaries.geojson # Tasmania House divisions filtered from AEC March 2025 federal boundaries
data/tas_2024_preferences_long.csv        # TEC 2024 House of Assembly Hare-Clark first and final count rows
data/tas_2024_district_summary.csv        # TEC 2024 division-level elected member summary
data/tas_2024_district_boundaries.geojson # Tasmania House divisions filtered from AEC March 2025 federal boundaries
data/tas_2021_preferences_long.csv        # TEC 2021 House of Assembly Hare-Clark first and final count rows
data/tas_2021_district_summary.csv        # TEC 2021 division-level elected member summary
data/tas_2021_district_boundaries.geojson # Tasmania House divisions filtered from AEC 2019 federal boundaries
data/nz_2023_mmp.csv                       # NZ Electoral Commission candidate and party votes for all 72 electorates
data/nz_2023_electorate_boundaries.geojson # Stats NZ 2020 general and Māori boundaries used for the 2023 election
data/uk_2024_fpp.csv                       # UK Parliament candidate results for all 650 constituencies
data/uk_2024_constituency_boundaries.geojson # ONS July 2024 Westminster constituency boundaries
data/uk_2019_fpp.csv                       # UK Parliament 2019 candidate results for all 650 constituencies
data/uk_2019_constituency_boundaries.geojson # ONS December 2019 Westminster constituency boundaries
data/uk_2017_fpp.csv                       # UK Parliament 2017 candidate results for all 650 constituencies
data/uk_2017_constituency_boundaries.geojson # ONS December 2019 layer for the unchanged 2017 constituencies
data/malaysia_2022_fpp.csv                 # SPR Malaysia GE15 candidate results for all 222 constituencies
data/malaysia_2022_parliamentary_boundaries.geojson # GE15 parliamentary boundaries from three delimitation sets
data/malaysia_2018_fpp.csv                 # ElectionData.MY GE14 results for all 222 constituencies
data/malaysia_2018_parliamentary_boundaries.geojson # GE14 parliamentary boundaries from three delimitation sets
data/malaysia_2013_fpp.csv                 # ElectionData.MY GE13 results for all 222 constituencies
data/malaysia_2013_parliamentary_boundaries.geojson # GE13 parliamentary boundaries from three delimitation sets
data/singapore_2025_fpp.csv                # ELD GE2025 candidate/team results for all 33 electoral divisions
data/singapore_2025_electoral_boundaries.geojson # data.gov.sg 2025 SMC and GRC boundaries
data/singapore_2020_fpp.csv                # ELD GE2020 candidate/team results for all 31 electoral divisions
data/singapore_2020_electoral_boundaries.geojson # data.gov.sg 2020 SMC and GRC boundaries
data/singapore_2015_fpp.csv                # ELD GE2015 candidate/team results for all 29 electoral divisions
data/singapore_2015_electoral_boundaries.geojson # data.gov.sg 2015 SMC and GRC boundaries
data/canada_2025_fpp.csv                   # Elections Canada GE2025 results for all 343 ridings
data/canada_2025_federal_boundaries.geojson # Elections Canada 45th-election riding boundaries
data/canada_2021_fpp.csv                   # Elections Canada GE2021 results for all 338 ridings
data/canada_2021_federal_boundaries.geojson # Elections Canada 44th-election riding boundaries
data/thailand_2026_fpp.csv                  # ECT/Thai PBS candidate results for all 400 constituency seats
data/thailand_2026_constituency_cartogram.geojson # Thai PBS equal-area seat cartogram (not legal boundaries)
data/japan_2026_house_fpp.csv                # Japan 2026 single-member constituency candidate results
data/japan_2024_house_fpp.csv                # Japan 2024 single-member constituency candidate results
data/japan_2022_house_constituency_schematic.geojson # Shared post-2022 schematic with metro insets
data/france_2022_president_round_1_department_fpp.csv # French presidential department/territory results (pattern repeated for 8 contests)
data/france_2022_president_round_1_region_fpp.csv # matching election-time region results
data/france_2022_department_boundaries.geojson # compact department/territory map with overseas insets
data/france_2022_region_boundaries.geojson # compact election-time region map
data/netherlands_2025_house_fpp.csv         # Kiesraad party-list totals for 342 municipalities
data/netherlands_2025_house_boundaries.geojson # Eurostat GISCO municipality boundaries
data/norway_2025_storting_fpp.csv           # Valgdirektoratet party totals for 357 municipalities
data/norway_2025_storting_boundaries.geojson # Eurostat GISCO municipality boundaries
data/sweden_2022_riksdag_fpp.csv            # Valmyndigheten results aggregated to 290 municipalities
data/sweden_2022_riksdag_boundaries.geojson # Eurostat GISCO municipality boundaries
data/philippines_2022_president_fpp.csv     # presidential candidate totals for 107 domestic COC map areas
data/philippines_2022_vice_president_fpp.csv # vice-presidential candidate totals for the same areas
data/philippines_2022_coc_boundaries.geojson # PSA municipal geometry dissolved to province/city COC areas
data/indonesia_2024_president_province_fpp.csv # KPU certified presidential totals for 38 provinces
data/indonesia_2024_province_boundaries.geojson # KPU Satu Peta province boundaries
data/indonesia_2024_president_kabupaten_kota_fpp.csv # presidential totals for all 514 kabupaten/kota
data/indonesia_2024_kabupaten_kota_boundaries.geojson # simplified KPU Satu Peta kabupaten/kota boundaries
data/indonesia_2019_president_province_fpp.csv # KPU presidential totals for the 34 election-time provinces
data/indonesia_2019_province_boundaries.geojson # province polygons dissolved to the 2019 hierarchy
data/indonesia_2019_president_kabupaten_kota_fpp.csv # all 514 local presidential recapitulations
data/indonesia_2014_president_province_fpp.csv # KPU certified totals for 33 reporting provinces
data/indonesia_2014_province_boundaries.geojson # province polygons dissolved to the 2014 hierarchy
data/indonesia_2014_president_kabupaten_kota_fpp.csv # 497 KawalPemilu C1 archive aggregates
data/indonesia_2014_kabupaten_kota_boundaries.geojson # election-time local units with later splits dissolved
data/federal_2025_au_preferences_long.csv         # AEC 2025 federal House preference rows, Australia-wide
data/federal_2025_au_district_summary.csv         # AEC 2025 federal House division summary, Australia-wide
data/federal_2025_au_division_boundaries.geojson  # AEC March 2025 national federal division polygons
data/federal_2022_au_preferences_long.csv         # AEC 2022 federal House preference rows, Australia-wide
data/federal_2022_au_district_summary.csv         # AEC 2022 federal House division summary, Australia-wide
data/federal_2022_au_division_boundaries.geojson  # AEC 2021 national federal division polygons used at 2022 election
data/federal_2019_au_preferences_long.csv         # AEC 2019 federal House preference rows, Australia-wide
data/federal_2019_au_district_summary.csv         # AEC 2019 federal House division summary, Australia-wide
data/federal_2019_au_division_boundaries.geojson  # AEC 2019 national federal division polygons
data/federal_2016_au_preferences_long.csv         # AEC 2016 federal House preference rows, Australia-wide
data/federal_2016_au_district_summary.csv         # AEC 2016 federal House division summary, Australia-wide
data/federal_2016_au_division_boundaries.geojson  # AEC 2016 election-period national division polygons assembled from official jurisdiction files
data/federal_2013_vic_preferences_long.csv        # AEC 2013 federal House preference rows, Victoria only
data/federal_2013_vic_district_summary.csv        # AEC 2013 federal House division summary, Victoria only
data/federal_2013_vic_division_boundaries.geojson # AEC December 2010 federal division polygons, Victoria
data/federal_2010_vic_preferences_long.csv        # AEC 2010 federal House preference rows, Victoria only
data/federal_2010_vic_district_summary.csv        # AEC 2010 federal House division summary, Victoria only
data/federal_2010_vic_division_boundaries.geojson # AEC 2010 national federal division polygons, Victoria features
data/federal_2007_vic_preferences_long.csv        # AEC 2007 federal House preference rows, Victoria only
data/federal_2007_vic_district_summary.csv        # AEC 2007 federal House division summary, Victoria only
data/sample_melbourne_preferences_long.csv
```

Boundary data is election-year-specific. The 2022 election used boundaries from the 2020-2021 redivision, so earlier elections such as 2006, 2010, 2014, and 2018 need their own boundary file.

NSW 2023 uses the official NSW Electoral Commission 2021 redistribution district shapefile, which is the boundary set in force for the 25 March 2023 election.

NSW 2019 uses the official NSW Electoral Commission 2013 redistribution boundary dataset, published as MapInfo MID/MIF files and used at the 23 March 2019 election.

NSW 2015 uses the same official NSW Electoral Commission 2013 redistribution boundary dataset, which was also in force for the 28 March 2015 election.

NSW 2011 result rows are generated from the official NSWEC district summary pages under `SGE2011/la_index.htm`. Those pages expose final first-preference tables and final two-candidate-preferred tables but not machine-readable round-by-round distributions, so the app stores first and final rows for each district. The 2011 boundary file is adapted from the Terria/NationalMap `FID_SED_2011_AUST` historical ABS State Electoral Division vector tiles at zoom 6, filtered to the 93 NSW districts used at the 26 March 2011 election.

Queensland 2024 and 2020 result rows are generated from the Electoral Commission of Queensland public results JSON service under `resultsdata.elections.qld.gov.au`, using `SGE2024` and `state2020` district `primary` and `preference` count files. Both elections use the official Queensland Spatial `State electoral boundary 2017` REST layer because the 2017 redistribution remained in force for the 31 October 2020 and 26 October 2024 state general elections.

Tasmania 2025 and 2024 result rows are generated from Tasmanian Electoral Commission final House of Assembly result workbooks for Bass, Braddon, Clark, Franklin, and Lyons. Tasmania uses Hare-Clark STV, so each division elects seven members; the app stores first-preference rows and final-count rows, plus quota, elected order, and candidate status fields. The boundary files are filtered from the AEC March 2025 national federal division boundary file because Tasmanian House of Assembly divisions share the names and boundaries of the five Tasmanian federal divisions.

2014 and 2018 boundary data is adapted from Geoscape Administrative Boundaries, August 2018 archive, State Electoral Boundaries February 2018, via data.gov.au's previous versions package. It is licensed under Creative Commons Attribution 4.0. These boundaries come from the 2012-2013 state redivision, which came into operation for the 2014 State election and remained in place until the writ for the 2022 State election.

2006 and 2010 boundary data is adapted from the Victorian Government / VEC Vicmap Admin State Assembly Polygon 2001 WFS dataset. These 88 Legislative Assembly districts are the pre-2014 boundaries used for the 2006 and 2010 State elections.

## Folder Structure

```text
.
├── index.html
├── app/
│   └── index.html
├── data/
├── scripts/
│   ├── build_aec_federal.py
│   ├── build_india_federal.py
│   ├── build_france_presidential.py
│   ├── build_indonesia_historical_presidential.py
│   ├── build_indonesia_presidential.py
│   ├── build_philippines_2022.py
│   ├── build_us_house.py
│   ├── scrape_vec_2022_preferences.py
│   ├── validate_federal.py
│   ├── validate_france_presidential.py
│   ├── validate_india_federal.py
│   ├── validate_indonesia_historical_presidential.py
│   ├── validate_indonesia_presidential.py
│   ├── validate_philippines_2022.py
│   ├── validate_us_house.py
│   └── validate_vec_csv.py
├── docs/
│   └── data_notes.md
├── .github/workflows/
│   └── scrape-vec-data.yml
├── requirements.txt
├── START_HERE.md
└── codex_prompt.md
```

`index.html` and `app/index.html` are kept in sync.

## Election Definitions

Election options are driven by the in-app `electionDefinitions` list in `index.html` and `app/index.html`. Each entry defines the key, label, election type, jurisdiction, year, source, preference CSV, and boundary GeoJSON. The election selector is generated from this list. Indonesia additionally uses a `geographies` map so one election can switch between its province and kabupaten/kota datasets.

When adding an election, add the data files, add one election definition to both HTML entry points, then run:

```bash
python scripts/smoke_static_app.py
```

The smoke test reads `electionDefinitions` from the HTML files and validates that the configured CSV and boundary files exist, load, and match by district name.
It also checks that the compact rankings UI markers are present in both HTML entry points.
For elections configured as `fpp` or `mmp-fpp`, it requires compact candidate rows with no duplicated `final` copies.

## Asset size guardrails

Static hosting and browser parsing depend on keeping boundary geometry compact. CI rejects an individual boundary file over 15 MiB or a total `data/` directory over 190 MiB:

```bash
python scripts/check_repository_sizes.py
```

Oversized boundary sources are simplified with shared-topology preservation. The first pass retains 20% of weighted vertices; the already-simplified Australia-wide federal maps use a guarded 70% second pass. The invalid source rings in the shared Victoria 2014/2018 map are cleaned before retaining 5%. The optimizer verifies identical feature order and properties, valid non-empty output, and a maximum relative feature-area change of 0.5% before replacing anything:

```bash
./.venv/bin/python scripts/optimize_boundary_geojson.py --write
```

The optimizer pins Mapshaper `0.7.45` through `npx` and skips files already below the 8 MiB optimized ceiling, preventing repeated simplification. Victoria 2014 and 2018 use the same 2012-2013 redivision, so both election definitions point to one repaired and optimized boundary file instead of storing duplicate geometry.

First-past-the-post CSVs are also compacted structurally. Candidate totals are stored once as `first` rows and the browser creates the identical final standing in memory. This removes about 7 MiB of duplicate rows across New Zealand, the UK, Malaysia, Singapore, Canada, and India without changing any displayed result.

## CSV Format

The app expects long CSV rows:

```csv
district,elected_member,elected_party,enrolment,formal_votes,informal_votes,total_votes,turnout_pct,majority,round_number,row_type,excluded_candidate,excluded_party,candidate,candidate_party,votes
```

`row_type` should be one of:

```text
first
transfer
progressive
final
```

For `fpp` and `mmp-fpp` election definitions, store each candidate only once as a round-zero `first` row. Do not duplicate those unchanged totals as `final` rows; the app supplies that final standing at load time. Preferential and multi-member count datasets continue to store their real published final rows.

## Run The Scraper

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/scrape_vec_2022_preferences.py --year 2022 --out data --keep-going
python scripts/validate_vec_csv.py data/vic_2022_preferences_long.csv
```

To rebuild and validate India 2024 (the builder downloads its public source files):

```bash
python scripts/build_india_federal.py
python scripts/validate_india_federal.py
```

To rebuild and validate the United States House 2024 dataset (the builder downloads the official Clerk and Census files):

```bash
./.venv/bin/python scripts/build_us_house.py
./.venv/bin/python scripts/validate_us_house.py
```

For historical state elections:

```bash
python scripts/scrape_vec_2022_preferences.py --year 2014 --out data --keep-going
python scripts/validate_vec_csv.py data/vic_2014_preferences_long.csv
python scripts/scrape_vec_2022_preferences.py --year 2018 --out data --keep-going
python scripts/validate_vec_csv.py data/vic_2018_preferences_long.csv
python scripts/scrape_vec_2022_preferences.py --year 2010 --out data --keep-going
python scripts/build_vic_2010_boundaries.py --out data/vic_2010_district_boundaries.geojson
python scripts/validate_state_vic.py --csv data/vic_2010_preferences_long.csv --boundaries data/vic_2010_district_boundaries.geojson --expected-districts 88 --label VIC-2010
python scripts/scrape_vec_2022_preferences.py --year 2006 --out data --keep-going
python scripts/build_vic_2010_boundaries.py --year 2006 --out data/vic_2006_district_boundaries.geojson
python scripts/validate_state_vic.py --csv data/vic_2006_preferences_long.csv --boundaries data/vic_2006_district_boundaries.geojson --expected-districts 88 --label VIC-2006
```

For NSW 2023:

```bash
python scripts/build_nsw_state_2023.py --out data
python scripts/validate_state_vic.py --csv data/nsw_2023_preferences_long.csv --boundaries data/nsw_2023_district_boundaries.geojson --expected-districts 93 --label NSW-2023 --max-gap-ratio 0.005
```

For NSW 2019:

```bash
python scripts/build_nsw_state_2019.py --out data
python scripts/validate_state_vic.py --csv data/nsw_2019_preferences_long.csv --boundaries data/nsw_2019_district_boundaries.geojson --expected-districts 93 --label NSW-2019 --max-gap-ratio 0.005
```

For NSW 2015:

```bash
python scripts/build_nsw_state_2015.py --out data
python scripts/validate_state_vic.py --csv data/nsw_2015_preferences_long.csv --boundaries data/nsw_2015_district_boundaries.geojson --expected-districts 93 --label NSW-2015 --max-gap-ratio 0.005
```

For South Australia House of Assembly:

```bash
python scripts/build_sa_state.py
python scripts/validate_state_vic.py --csv data/sa_2022_preferences_long.csv --boundaries data/sa_2022_district_boundaries.geojson --expected-districts 47 --label SA-2022 --max-gap-ratio 0.005
python scripts/build_sa_state.py --year 2018
python scripts/validate_state_vic.py --csv data/sa_2018_preferences_long.csv --boundaries data/sa_2018_district_boundaries.geojson --expected-districts 47 --label SA-2018 --max-gap-ratio 0.005
```

For Western Australia Legislative Assembly:

```bash
python scripts/build_wa_state.py --year 2025
python scripts/validate_state_vic.py --csv data/wa_2025_preferences_long.csv --boundaries data/wa_2025_district_boundaries.geojson --expected-districts 59 --label WA-2025 --max-gap-ratio 0.005 --validate-vote-totals
python scripts/build_wa_state.py --year 2021
python scripts/validate_state_vic.py --csv data/wa_2021_preferences_long.csv --boundaries data/wa_2021_district_boundaries.geojson --expected-districts 59 --label WA-2021 --max-gap-ratio 0.005 --validate-vote-totals
```

For Northern Territory Legislative Assembly:

```bash
python scripts/build_nt_state.py --year 2024
python scripts/validate_state_vic.py --csv data/nt_2024_preferences_long.csv --boundaries data/nt_2024_district_boundaries.geojson --expected-districts 25 --label NT-2024 --max-gap-ratio 0.005 --validate-vote-totals
python scripts/build_nt_state.py --year 2020
python scripts/validate_state_vic.py --csv data/nt_2020_preferences_long.csv --boundaries data/nt_2020_district_boundaries.geojson --expected-districts 25 --label NT-2020 --max-gap-ratio 0.005 --validate-vote-totals
```

For Tasmania House of Assembly:

```bash
python scripts/build_tas_state_2025.py
python scripts/validate_tas_state.py --csv data/tas_2025_preferences_long.csv --boundaries data/tas_2025_district_boundaries.geojson
python scripts/build_tas_state_2024.py
python scripts/validate_tas_state.py --csv data/tas_2024_preferences_long.csv --boundaries data/tas_2024_district_boundaries.geojson
python scripts/build_tas_state_2021.py
python scripts/validate_tas_state.py --csv data/tas_2021_preferences_long.csv --boundaries data/tas_2021_district_boundaries.geojson --expected-members 5
```

For the 2025 Australia-wide federal dataset, download the official AEC event `31496` files into `tmp/aec_2025_au`, unzip the national boundary ZIP there, then run:

```bash
python3 scripts/build_aec_federal.py --year 2025 --event-id 31496 --scope au --raw-dir tmp/aec_2025_au --out data --shp tmp/aec_2025_au/AUS_ELB_region.shp --gis-source https://www.aec.gov.au/Electorates/files/2025/AUS-March-2025-esri.zip
python3 scripts/validate_vec_csv.py data/federal_2025_au_preferences_long.csv
python3 scripts/validate_federal.py --csv data/federal_2025_au_preferences_long.csv --boundaries data/federal_2025_au_division_boundaries.geojson --aec-dop tmp/aec_2025_au/HouseDopByDivisionDownload-31496.csv --expected-divisions 150 --scope au
```

For the 2022 Australia-wide federal dataset, download the official AEC files for event `27966` into `tmp/aec_2022_au`, unzip the national boundary ZIP there, then run:

```bash
python3 scripts/build_aec_federal.py --year 2022 --event-id 27966 --scope au --raw-dir tmp/aec_2022_au --out data --shp tmp/aec_2022_au/2021_ELB_region.shp --gis-source https://www.aec.gov.au/Electorates/gis/files/2021-Cwlth_electoral_boundaries_ESRI.zip
python3 scripts/validate_vec_csv.py data/federal_2022_au_preferences_long.csv
python3 scripts/validate_federal.py --csv data/federal_2022_au_preferences_long.csv --boundaries data/federal_2022_au_division_boundaries.geojson --aec-dop tmp/aec_2022_au/HouseDopByDivisionDownload-27966.csv --expected-divisions 151 --scope au
```

For the 2019 Australia-wide federal dataset, download the official AEC files for event `24310` into `tmp/aec_2019_au`, unzip `national-esri-fe2019.zip` there, then run:

```bash
python3 scripts/build_aec_federal.py --year 2019 --event-id 24310 --scope au --raw-dir tmp/aec_2019_au --out data --shp tmp/aec_2019_au/COM_ELB_region.shp --gis-source https://www.aec.gov.au/Electorates/gis/files/national-esri-fe2019.zip
python3 scripts/validate_vec_csv.py data/federal_2019_au_preferences_long.csv
python3 scripts/validate_federal.py --csv data/federal_2019_au_preferences_long.csv --boundaries data/federal_2019_au_division_boundaries.geojson --aec-dop tmp/aec_2019_au/HouseDopByDivisionDownload-24310.csv --expected-divisions 151 --scope au
```

For the 2016 Australia-wide federal dataset, download the official AEC files for event `20499` into `tmp/aec_2016_au`, place the official jurisdiction boundary ZIPs in `tmp/aec_2016_au_sources`, then run:

```bash
python3 scripts/build_aec_federal_2016_au.py --raw-dir tmp/aec_2016_au --source-dir tmp/aec_2016_au_sources --extract-dir tmp/aec_2016_au_extract --out data
python3 scripts/validate_vec_csv.py data/federal_2016_au_preferences_long.csv
python3 scripts/validate_federal.py --csv data/federal_2016_au_preferences_long.csv --boundaries data/federal_2016_au_division_boundaries.geojson --aec-dop tmp/aec_2016_au/HouseDopByDivisionDownload-20499.csv --expected-divisions 150 --scope au
```

For the 2013 federal Victoria dataset, download the official AEC files for event `17496` into `tmp/aec_2013_vic`, use the AEC `vic-esri-24122010.zip` boundary shapefile, then run:

```bash
python3 scripts/build_aec_vic.py --year 2013 --event-id 17496 --raw-dir tmp/aec_2013_vic --out data --shp "tmp/aec_2016_vic/vic-esri-24122010/vic 24122010.shp" --prj tmp/aec_2016_vic/vic-esri-24122010/vic24122010.prj --gis-source https://www.aec.gov.au/Electorates/gis/files/vic-esri-24122010.zip
python3 scripts/validate_vec_csv.py data/federal_2013_vic_preferences_long.csv
python3 scripts/validate_federal.py --csv data/federal_2013_vic_preferences_long.csv --boundaries data/federal_2013_vic_division_boundaries.geojson --aec-dop tmp/aec_2013_vic/HouseDopByDivisionDownload-17496.csv --expected-divisions 37 --scope vic
```

For the 2010 federal Victoria dataset, download the official AEC files for event `15508` into `tmp/aec_2010_vic`, unzip the AEC `national-esri-2010.zip` boundary shapefile, then run:

```bash
python3 scripts/build_aec_vic.py --year 2010 --event-id 15508 --raw-dir tmp/aec_2010_vic --out data --shp tmp/aec_2010_vic/national-esri-2010/COM_ELB_2010_region.shp --gis-source https://www.aec.gov.au/Electorates/gis/files/national-esri-2010.zip
python3 scripts/validate_vec_csv.py data/federal_2010_vic_preferences_long.csv
python3 scripts/validate_federal.py --csv data/federal_2010_vic_preferences_long.csv --boundaries data/federal_2010_vic_division_boundaries.geojson --aec-dop tmp/aec_2010_vic/HouseDopByDivisionDownload-15508.csv --expected-divisions 37 --scope vic
```

For the 2007 federal Victoria dataset, download the official AEC files for event `13745` into `tmp/aec_2007_vic`, unzip the AEC `national-esri-2010.zip` boundary shapefile there, then run:

```bash
python3 scripts/build_aec_vic.py --year 2007 --event-id 13745 --raw-dir tmp/aec_2007_vic --out data --shp tmp/aec_2007_vic/national-esri-2010/COM_ELB_2010_region.shp --gis-source https://www.aec.gov.au/Electorates/gis/files/national-esri-2010.zip
python3 scripts/validate_vec_csv.py data/federal_2007_vic_preferences_long.csv
python3 scripts/validate_federal.py --csv data/federal_2007_vic_preferences_long.csv --boundaries data/federal_2010_vic_division_boundaries.geojson --aec-dop tmp/aec_2007_vic/HouseDopByDivisionDownload-13745.csv --expected-divisions 37 --scope vic
```

To rebuild and validate Indonesia's presidential election files:

```bash
python3 scripts/build_indonesia_presidential.py
python3 scripts/validate_indonesia_presidential.py
python3 scripts/build_indonesia_historical_presidential.py
python3 scripts/validate_indonesia_historical_presidential.py
```

The builder downloads the 514-row structured result table and KPU Satu Peta boundaries, matches every result and polygon by administrative code, and uses pinned Mapshaper topology simplification. The validator requires 38 certified province results, 514 kabupaten/kota, three candidate-pair rows per area, valid matching polygons, the published winner counts, and exactly the disclosed Papua Tengah aggregate difference.

The historical builder downloads the preserved 2019 KPU recapitulation and KawalPemilu 2014 C1 archive, repairs three known malformed 2019 province arrays from certified recapitulations, and constructs election-year geography from the compact KPU local boundaries. Its validator requires exact 2019 local-to-province reconciliation, 34/514 areas in 2019, 33/497 areas in 2014, valid matching polygons, the documented 2014 archive coverage, and the absence of post-hierarchy split districts from the 2014 results.

To rebuild and validate Thailand's 2026 constituency election files:

```bash
python3 scripts/build_thailand_2026.py
python3 scripts/validate_thailand_2026.py
```

The builder downloads pinned English master data and the 18 March ECT official result snapshot from Thai PBS, preserves the earlier ECT enrolment denominator for turnout, and extracts the 400 keyed cells from Thai PBS's nationwide cartogram asset. The later-certified Suphan Buri 2 candidate result is included with a mandatory disclosure and without unavailable post-recount turnout metadata.

To rebuild and validate Japan's 2026 and 2024 House constituency files:

```bash
python3 scripts/build_japan_house.py
python3 scripts/validate_japan_house.py --year 2026
python3 scripts/validate_japan_house.py --year 2024
```

The builder checksum-pins the official Ministry candidate publications, the structured candidate transcription, an independent 2024 academic audit, and the post-2022 schematic source. It requires all 289 constituencies, exact candidate and winner counts, national whole-vote totals, and a one-to-one result/map match.

To rebuild and validate the Philippines 2022 executive-election files:

```bash
python3 scripts/build_philippines_2022.py
python3 scripts/validate_philippines_2022.py
```

The builder parses a pinned transcription of the congressional canvass, requires its 173 COC rows to retain the documented relationship to the adopted national totals, folds the Special Geographic Area into Cotabato only for mapping, and dissolves official PSA municipal polygons into 107 non-duplicated domestic reporting areas. The validator checks every candidate set, vote total, local winner, margin, reporting code, region, and matching valid geometry.

To rebuild and validate the Mexico 2024 presidential-election files:

```bash
python3 scripts/build_mexico_2024.py
python3 scripts/validate_mexico_2024.py
```

The builder downloads checksum-pinned final INE computation and cartography archives, aggregates polling-place records to the 300 federal districts, and simplifies the official polygons for the static app. The validator requires all 900 candidate rows, exact mapped totals and turnout, 32-state coverage, unique district codes, the 275–25 local-leader split, and matching valid boundaries.

To rebuild and validate the South Korea presidential-election files:

```bash
python3 scripts/build_south_korea_presidential.py
python3 scripts/validate_south_korea_presidential.py
```

The builder downloads checksum-pinned NEC returns for both elections and the official SGIS municipal layer, aggregates every polling district, reconciles all candidate, invalid-ballot, turnout, and electorate totals, and applies the documented historical geography adjustments. The validator checks exact national totals, all 17 first-level regions, local winners and margins, unique area codes, valid matching polygons, and no material overlaps.

To rebuild and validate all eight French presidential-election round views:

```bash
python3 scripts/build_france_presidential.py
python3 scripts/validate_france_presidential.py
```

The builder downloads checksum-pinned definitive Ministry result tables and a version-pinned data.gouv.fr administrative boundary release. It parses published department and region tables directly where available, aggregates the official 2012 commune workbook, locks national candidate totals, and emits election-time region maps with compact overseas insets. The validator checks all 16 CSV views, candidate sets, ballot arithmetic, turnout, winners, margins, area codes, matching valid geometry, and polygon overlaps.

To rebuild the two Portuguese and two Spanish legislative elections:

```bash
python3 scripts/build_iberian_elections.py
python3 scripts/smoke_static_app.py
```

The builder checksum-pins Portugal's 40 domestic district results and official inset maps, Spain's certified BOE result and turnout tables, and Eurostat GISCO geometry. It requires exact ballot arithmetic and the 226 Portuguese domestic plus 350 Spanish constituency seat allocations before writing output. The static smoke adds one-to-one CSV/map, party-vote, ballot-total, and mapped-seat validation for all four elections.

To rebuild the two Dutch, two Norwegian, and two Swedish parliamentary elections:

```bash
python3 scripts/build_northern_europe_elections.py
python3 scripts/smoke_static_app.py
```

The builder checksum-pins the Dutch and Swedish publications plus each annual Eurostat GISCO LAU archive, and locks Norway's official API control totals. It validates every municipality's party-vote and ballot arithmetic before emitting the six compact local-leader views.

The VEC scraper writes:

```text
data/vic_2022_preferences_long.csv
data/vic_2022_district_summary.csv
```

If any districts fail, the scraper also writes:

```text
data/vic_2022_scrape_errors.csv
```

## Current Status

The app currently validates against:

- 6,082 preference rows
- 87 districts
- 87 boundary features
- no missing vote rows

The Indonesia Presidential 2024 option validates against:

- 38 certified province results and matching province boundaries
- all 514 kabupaten/kota, 1,542 candidate-pair rows, and 514 matching local boundaries
- 36 province wins for Prabowo–Gibran and 2 for Anies–Muhaimin
- the single disclosed 67,005-vote Papua Tengah local-to-province difference

The Indonesia Presidential 2019 and 2014 options validate against:

- 34 provinces and all 514 kabupaten/kota for 2019, with exact local-to-province reconciliation
- 33 reporting provinces and 497 election-time kabupaten/kota for 2014
- certified 2014 province totals, 98.24% archived domestic C1 coverage, and four explicitly unavailable Papua local results
- historical province membership and dissolved parent polygons for later administrative splits

The Philippines President and Vice President 2022 options validate against:

- 107 matching domestic province/city COC map areas for each separate ballot
- 1,070 presidential rows for 10 candidates and 963 vice-presidential rows for 9 candidates
- 89 local Marcos wins and 99 local Duterte wins, with all other area winners reconciled
- matching PSA-derived geometry, unique reporting codes, candidate totals, margins, and the documented COC-detail arithmetic differences

The Mexico President 2024 option validates against:

- all 300 federal electoral districts and 900 candidate rows across all 32 states
- exact mapped candidate, null/non-registered, ballot, nominal-list, turnout, and margin totals
- 275 local Sheinbaum leads and 25 local Gálvez leads
- matching INE-derived geometry, unique federal district codes, and no material polygon overlaps

The South Korea President 2025 and 2022 options validate against:

- 252 mapped areas and 1,260 candidate rows for 2025
- 250 historical areas and 3,000 candidate rows for 2022
- exact official candidate, invalid-ballot, turnout, electorate, winner, and margin totals
- all 17 first-level regions with matching SGIS-derived geometry and documented historical adjustments

The federal 2019 Australia option validates against:

- 7,412 preference rows
- 151 federal divisions
- 151 boundary features
- matching AEC result and boundary names
- no large boundary overlaps or internal gaps

The federal 2016 Australia option validates against:

- 6,786 preference rows
- 150 federal divisions
- 150 boundary features
- matching AEC result and boundary names
- no large boundary overlaps or internal gaps

The federal 2013 Victoria option validates against:

- 3,303 preference rows
- 37 federal divisions
- 37 boundary features
- matching AEC result and boundary names
- no large boundary overlaps or internal gaps

The federal 2010 Victoria option validates against:

- 1,008 preference rows
- 37 federal divisions
- 37 boundary features
- matching AEC result and boundary names
- no large boundary overlaps or internal gaps

The federal 2007 Victoria option validates against:

- 1,570 preference rows
- 37 federal divisions
- 37 boundary features
- matching AEC result and boundary names
- no large boundary overlaps or internal gaps

The Victorian state 2010 option validates against:

- 2,002 preference rows
- 88 Legislative Assembly districts
- 88 boundary features
- matching result and boundary names
- no large boundary overlaps or internal gaps

The Victorian state 2006 option validates against:

- 1,685 preference rows
- 88 Legislative Assembly districts
- 88 boundary features
- matching result and boundary names
- no large boundary overlaps or internal gaps

The VEC 2006 archive has 49 districts with full distribution pages and 39 districts with result-page-only tables. Gippsland East follows the archived HTML standard distribution; the later VEC report describes an extra statistical distribution.

Best next improvements:

- visual regression screenshot smoke test after each release
- scraper fixture tests for one current VEC page and one historical VEC page
