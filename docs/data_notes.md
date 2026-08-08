# Data notes

Source targets:

- Victorian Electoral Commission State Election results pages
- Australian Electoral Commission Federal Election House of Representatives downloads
- Australian Electoral Commission Senate group first-preference, elected-senator, representation, informal-vote, and turnout downloads
- Australian Electoral Commission federal division GIS boundaries
- Australian Bureau of Statistics ASGS 2021 state and territory boundaries
- Tasmanian Electoral Commission House of Assembly result workbooks
- New Zealand Electoral Commission 2023 and 2020 General Election result pages
- Stats NZ 2020 general and Māori electorate boundaries
- UK Parliament 2024, 2019, and 2017 general election candidate results
- ONS July 2024 and December 2019 Westminster parliamentary constituency boundaries
- SPR Malaysia GE15 official candidate results and ElectionData.MY GE14 and GE13 results
- ElectionData.MY parliamentary delimitation boundaries for Peninsular Malaysia, Sabah, and Sarawak
- Elections Department Singapore 2025, 2020, and 2015 final results and Statements of Poll
- data.gov.sg 2025, 2020, and 2015 electoral division boundaries
- Elections Canada 44th and 45th general election official voting results and federal electoral district boundaries
- Election Commission of India 2024 Lok Sabha final statistical reports and constituency results
- Esri India Living Atlas 2024 parliamentary constituency boundaries and winner attributes
- Japan Ministry of Internal Affairs and Communications 2026 and 2024 House constituency results
- Kenichi Yoshinaga structured House candidate archive and Yukiyanai 2024 academic audit
- Wikimedia/NHK post-2022 Japanese House constituency schematic
- U.S. House Clerk official 2016–2024 congressional election statistics
- U.S. Census Bureau 119th Congress cartographic district boundaries
- U.S. Federal Election Commission official 2008–2024 presidential election result workbooks
- MIT Election Data and Science Lab county presidential returns for 2008–2016
- Public U.S. state/media county presidential result compilation for 2020 and 2024
- U.S. Federal Election Commission and MIT Election Data and Science Lab regular Senate returns for 2016–2024
- State-sourced OpenElections files for documented Senate county gaps and decisive regular-seat runoffs
- MIT Election Data and Science Lab state precinct returns for 2016–2024 gubernatorial elections
- Tennessee Secretary of State official 2022 governor county results
- U.S. Census Bureau county and state cartographic boundaries
- Election Commission of Thailand results through the Thai PBS Election 69 English data feed
- Thai PBS Election 69 equal-area constituency cartogram
- Philippine Congress 2022 presidential and vice-presidential canvass and Resolution of Both Houses No. 1
- Philippine Statistics Authority municipal boundary ArcGIS service
- Instituto Nacional Electoral (Mexico) 2024 final district computation database
- Instituto Nacional Electoral national federal-district cartography archive
- National Election Commission of the Republic of Korea presidential polling-district returns for 2025 and 2022
- Statistics Korea SGIS 2025 Q2 municipal boundaries
- Argentina Dirección Nacional Electoral 2023 and 2019 provisional polling-table returns
- Argentina Instituto Geográfico Nacional province boundary archive
- Brazil Tribunal Superior Eleitoral 2022 and 2018 presidential results
- Brazil IBGE official state boundary API
- Taiwan Central Election Commission 2024, 2020, and 2016 presidential results
- Taiwan NLSC/MOI official township and urban-district boundary archive

This repo is built around three levels of data:

## 1. District-level result metadata

Examples:

- elected member
- elected party
- enrolment
- formal votes
- informal votes
- turnout

## 2. Preference distribution rows

The app expects a long table where each row is one candidate's vote value in one count stage.

Important row types:

- `first`: first preference votes
- `transfer`: votes transferred from an excluded candidate
- `progressive`: progressive total after a round
- `final`: final standing after distribution
- `party_vote`: New Zealand's separate MMP party vote within an electorate

## 3. District boundary polygons

The map uses an election-year-specific boundary file:

```text
data/vic_2022_district_boundaries.geojson
```

For earlier elections, use a matching file such as:

```text
data/vic_2014_district_boundaries.geojson # shared by 2014 and 2018
data/vic_2010_district_boundaries.geojson
data/vic_2006_district_boundaries.geojson
```

For Australia-wide federal options, use the matching national AEC federal division file for the election period:

```text
data/federal_2025_au_division_boundaries.geojson
data/federal_2022_au_division_boundaries.geojson
data/federal_2019_au_division_boundaries.geojson
data/federal_2016_au_division_boundaries.geojson
```

Victoria-only federal options are retained only for years without an Australia-wide dataset:

```text
data/federal_2013_vic_division_boundaries.geojson
data/federal_2010_vic_division_boundaries.geojson
```

The 2007 Victoria-only federal entry reuses the byte-identical 2010 AEC boundary file.

Do not reuse 2022 boundaries for earlier elections. The 2022 election used boundaries from the 2020-2021 redivision, 2014 and 2018 share the optimized 2012-2013 redivision file, and 2006 and 2010 used the earlier 2001 Legislative Assembly boundaries.

The shared 2014/2018 boundary file is adapted from Geoscape Administrative Boundaries, August 2018 archive, State Electoral Boundaries February 2018, via data.gov.au's previous versions package. The source is licensed CC-BY-4.0 and the repo file keeps the 88 Legislative Assembly district polygons that match both preference CSVs. These boundaries come from the 2012-2013 state redivision, which came into operation for the 2014 State election and remained in place until the writ for the 2022 State election.

The 2006 and 2010 state boundary files are adapted from the Victorian Government / VEC Vicmap Admin State Assembly Polygon 2001 WFS dataset, `open-data-platform:state_assembly_2001`. The repo files keep the 88 Legislative Assembly district polygons and normalise `district_label` values such as `Gippsland East District` to the app's `district` property.

The Victorian state 2010 result rows are generated from the VEC historical archive under `state2010/state2010resultsummary.html`. The 2010 pages use two source shapes: 44 districts expose full distribution pages, while 44 districts expose first preference plus two-candidate-preferred result tables on the district page. The scraper preserves full transfer/progressive rows where VEC published them and uses the district page's final preferred table where a full distribution page is not linked.

The Victorian state 2006 result rows are generated from the VEC historical archive under `state2006/state2006resultsummary.html`. The 2006 pages use the same legacy HTML shape as 2010: 49 districts expose full distribution pages, while 39 districts expose result-page-only tables. Some full distributions stop when a candidate reaches an absolute majority, so final rows may include more than two candidates. Gippsland East follows the archived HTML standard distribution; the later VEC report describes an extra statistical distribution.

The NSW state 2011 result rows are generated from the official NSWEC district summary archive under `SGE2011/la_index.htm`. Those pages expose final first-preference tables and final two-candidate-preferred tables but not machine-readable round-by-round distributions, so the scraper stores first rows plus final preferred rows for each district. The boundary file is adapted from the Terria/NationalMap historical `FID_SED_2011_AUST` ABS State Electoral Division vector tiles at zoom 6, filtered to the 93 NSW districts used at the 26 March 2011 election.

The Queensland state 2024 result rows are generated from the Electoral Commission of Queensland public results JSON service under `resultsdata.elections.qld.gov.au`, using the `SGE2024` district `primary` and `preference` count files. The boundary file is generated from the official Queensland Spatial `State electoral boundary 2017` ArcGIS REST layer, which the dataset metadata states remains the official state electoral boundary set until the next redistribution.

The Queensland state 2020 result rows are generated from the same Electoral Commission of Queensland JSON service, using the `state2020` district `primary` and `preference` count files. The 2020 boundary file uses the same Queensland Spatial `State electoral boundary 2017` layer because those 93 districts were also in force for the 31 October 2020 election.

The Western Australia 2025 and 2021 Legislative Assembly rows are generated from official WAEC final XML result feeds for enrolment, first preferences, and turnout metadata. Final two-candidate totals come from the certified WAEC Results and Statistics reports because the media XML can retain zeroed election-night indicative pairings rather than the final distribution pairing. Both elections therefore contain official first and final rows without fabricated intermediate exclusions. The 2025 boundaries use Landgate's current MLA layer for the 2023 distribution; the 2021 boundaries use the ABS 2021 State Electoral Division layer filtered to Western Australia, matching all 59 districts from the 2019 distribution.

The Northern Territory 2024 and 2020 Legislative Assembly rows are generated from the official NTEC electorate result summaries. They preserve each candidate's first preferences and the published final two-candidate-preferred totals, plus enrolment, formal, informal, total-counted, and turnout metadata. Intermediate exclusion counts are not inferred. The boundary files use the ABS 2024 and ABS 2021 State Electoral Division layers respectively, filtered to the 25 Northern Territory electorates and normalised to the app's district property.

The Tasmania state 2025 and 2024 result rows are generated from the Tasmanian Electoral Commission final House of Assembly result workbooks for the divisions of Bass, Braddon, Clark, Franklin, and Lyons. Tasmania uses Hare-Clark STV, so each division elects seven members rather than a single winner. The app stores first-preference rows and final-count rows with extra fields for quota, elected order, elected status, and members to elect. The boundary files are filtered from the AEC March 2025 national federal division boundary file because Tasmanian House of Assembly divisions share the names and boundaries of the five Tasmanian federal divisions.

The New Zealand 2023 and 2020 rows are generated from Electoral Commission candidate-vote and party-vote totals for all 72 electorates. The 2020 builder matches each official named candidate total to the public electorate-candidate table rather than assuming both sources use the same row order; the detailed-page vote columns must match the named totals exactly. Party labels are aligned to Wikipedia's public electorate-candidate tables because the Commission's candidate-list CSV currently blocks automated downloads. Candidate voting uses first past the post, so each candidate total is stored once as a `first` row and the app reconstructs the identical final standing; preference-transfer views remain hidden. Port Waikato is marked `cancelled` only in 2023 and retains its party vote; all 72 electorate contests were completed in 2020. The boundary files combine Stats NZ's 65 general and 7 Māori electorate layers used at both elections; the app toggles them because those layers overlap geographically. Stats NZ boundary data is licensed CC BY 4.0.

The United Kingdom 2024, 2019, and 2017 rows are generated from UK Parliament's official general-election candidacies CSVs for all 650 House of Commons constituencies. Candidate totals are checked against each constituency's valid-vote total, official majority, turnout metadata, country split, and nationwide winning-party seat totals. The UK uses first past the post, so each candidate total is stored once and the app reconstructs the unchanged final standing. Boundaries come from the matching ONS July 2024 and December 2019 Westminster constituency ArcGIS layers; 2017 uses the same constituency set as 2019.

The London 2024 entry is generated from London Elects' official Mayor and London Assembly results workbook. It preserves all three ballots at the 14-constituency reporting level: Mayor of London, directly elected Assembly constituency members, and the London-wide Assembly list. Formal, rejected, counted, electorate, turnout, candidate, and list totals reconcile within every constituency and to the London declarations. The complete member file records the 14 direct winners and the 11 London-wide members in official D'Hondt allocation order. The Mayor and London-wide maps show local leaders only; those constituency totals do not award separate mayors or list seats. Boundaries come from the Greater London Authority's official London Assembly Constituencies ArcGIS layer and are simplified without changing the 14 result identifiers.

The Malaysia 2022 rows use the official SPR `keputusan-pru` file plus the delayed P.017 Padang Serai result. The 2018 and 2013 rows use ElectionData.MY's CC0 Malaysian Election Corpus because SPR's historical JSON omits complete electorate metadata; the corpus reconciles all 687 GE14 and 579 GE13 candidate totals with exact seat statistics. All three elections contain 222 constituencies and validate ballots, turnout, margins, states, and party seat totals. Matching CC0 delimitation files are combined per election: GE15 uses Peninsular 2018, Sabah 2019, and Sarawak 2015; GE14 uses Peninsular 2018, Sabah 2003, and Sarawak 2015; GE13 uses Peninsular 2003, Sabah 2003, and Sarawak 2005.

The Singapore 2025, 2020, and 2015 rows are generated from Elections Department final-results pages and every official Statement of Poll. Each SMC candidate is one contest entry; each GRC party team retains its full nominated membership. Ballots, rejected votes, electors, turnout, winners, and elected MP totals reconcile exactly: 97 MPs in 2025, 93 in 2020, and 89 in 2015. Marine Parade–Braddell Heights is retained as uncontested only in 2025. Each election uses its dedicated official data.gov.sg Electoral Boundary dataset.

The Canada 2025 and 2021 rows are generated from Elections Canada's official Tables 11 and 12 for the 45th and 44th general elections. They contain all 1,959 candidates in 343 federal electoral districts for 2025 and all 2,010 candidates in 338 districts for 2021. Candidate votes reconcile against each riding's valid ballots, total ballots reconcile as valid plus rejected ballots, computed margins match the official majority field, and nationwide party seat totals are validated. Canada uses first past the post, so each candidate total is stored once and the app reconstructs the unchanged final standing. Each election uses its matching official Elections Canada boundary archive: the 2025 districts reflect the new representation order, while 2021 retains the earlier 338-district map. Both are reprojected to WGS84, dissolved by five-digit riding code where needed, and topology-preservingly simplified for the static app.

The India 2024 rows use the Election Commission of India's final constituency-wise detailed result report for electors and ballot totals, combined with the ECI-derived constituency candidate CSV published by OpenCity. All 8,360 candidates and 542 NOTA options are retained across 543 Lok Sabha constituencies. Candidate votes reconcile to formal totals, ballot totals reconcile as formal plus informal, and party seat counts and state/union-territory splits are validated. Surat is represented as the sole uncontested return with 1,786,287 electors and zero poll values, following the ECI's published atlas rather than fabricating a contest. Boundaries come from Esri India's 2024 parliamentary layer, which reflects the updated Assam and Jammu and Kashmir delimitation. The builder matches every boundary by state, constituency code, and name, and checks winner/vote/margin attributes outside Assam; the layer's 14 Assam winner attributes are shifted between the newly delimited seats and are deliberately not used as result truth. India uses first past the post, so each candidate/NOTA total is stored once and the app reconstructs the unchanged final standing.

The Japan 2026 and 2024 rows cover all 289 single-member House constituencies under the post-2022 allocation. A checksum-pinned structured candidate transcription is checked against the Ministry of Internal Affairs and Communications candidate publications; the 2024 rows additionally match Yukiyanai's independent public election dataset exactly by constituency and candidate votes. The source's erroneous `2026-10-22` date field is rejected unless it retains that known value, and the builder assigns the official 8 February 2026 election date through the app configuration instead. Winner flags, party seat totals, constituency allocations, candidate counts, and whole-vote national totals are locked in validation.

Japanese national party summaries include tiny fractional allocations for ballots whose intended party is ambiguous, while the official candidate tables publish whole-vote candidate figures. The app preserves those candidate figures and attaches a disclosure rather than inventing candidate fractions. Constituency-level registered-voter and invalid-ballot metadata are unavailable in the candidate publication, so turnout is left unavailable.

Both elections share a compact map extracted from the Wikimedia/NHK SVG for the 2022 redistribution. It has all 289 constituency shapes, including separate metropolitan insets, and matches every result by prefecture allocation and constituency number. Because it is a schematic rather than reusable legal GIS boundaries, that limitation is retained in every GeoJSON feature and shown beside the map.

The Thailand 2026 rows use Thai PBS's English Election 69 machine feed, whose official snapshot is backed by ECT data. It contains all 3,527 candidates in 400 constituencies. Candidate totals reconcile to valid ballots in 399 seats; invalid and explicit no-vote ballots are combined as non-candidate ballots so total ballots reconcile exactly. The official snapshot overwrites its eligible-voter field with ballots cast, so the builder deliberately takes the stable registered-voter denominator from the earlier ECT snapshot and applies it only to the final official ballot total. Suphan Buri 2 was still pending in the 18 March snapshot: ECT certified Natthawut Prasoetsuwan on 8 April after a recount, completing the House and raising Bhumjaithai to 173 constituency seats and 192 seats overall. The winner's 45,267 votes and runner-up's 23,277 votes follow the ECT Form 6/1 figures reported after the recount; remaining candidates follow the final structured table. Unavailable post-recount invalid, no-vote, total-ballot, and turnout metadata are left blank and disclosed in the app.

No reusable 2026 legal-boundary GIS file was available from the result source. The Thailand map therefore uses the nationwide Thai PBS equal-area constituency cartogram embedded in its public result application. The builder extracts all 400 cells by official area code and matches them one-to-one to results. The app and GeoJSON properties explicitly identify these cells as a cartogram rather than legal constituency polygons.

The North Korea 2026 Supreme People's Assembly rows come from the Central Election Committee press release reproduced by Korea News Service. The builder extracts and checksum-pins the normalized list of all 687 constituencies and elected deputies, requiring an uninterrupted sequence from Mangyongdae Constituency No. 1 to Kumgangsan Constituency No. 687. The source reports one registered candidate per constituency and national figures of 99.99% turnout and 99.93% support for the candidates.

The publication does not provide constituency-level vote totals, electorates, margins, or candidate affiliations. Those fields remain unavailable rather than being inferred from the national percentages, and the interface disables margin rankings for this election. No reusable constituency boundary layer is published, so the map is a 687-cell equal-area grid ordered by official constituency number. Every feature and the visible map note identify it as a non-geographic seat grid. The national figures are labelled state-reported and not independently verified.

The Philippines 2022 executive-election rows use the congressional canvass for both offices. President and vice president were chosen independently by nationwide plurality, so the app exposes separate presidential and vice-presidential options that share one map rather than treating the UniTeam campaign as a combined vote. The adopted Resolution of Both Houses No. 1 supplies the official national totals and winner declaration. The map-level rows use a pinned transcription of the individual certificates of canvass (COCs), covering every candidate in 107 domestic result units: 81 province-level COCs and 26 separately canvassed cities or NCR units. Local absentee, detainee, and overseas COCs contribute to the official national shares but have no domestic polygon and are not included in local leader or margin calculations.

The Special Geographic Area was a separate COC for 63 BARMM barangays geographically embedded in Cotabato municipalities. The builder adds its candidate totals to Cotabato only for the map and attaches a disclosure; it does not duplicate those votes elsewhere. Local COCs publish candidate totals but not a consistent invalid/blank-ballot or registered-voter denominator. Consequently each mapped area's `formal_votes` and `total_votes` fields mean the sum of its published candidate votes, while local informal votes and turnout remain unavailable in the UI. The national canvass separately reports 56,028,855 ballots, 53,815,484 valid presidential votes, and 52,346,000 valid vice-presidential votes.

The published detailed COC transcription has a fixed arithmetic discrepancy against the adopted resolution's national totals. Its presidential columns are one vote higher for Mangondato, Abella, De Guzman, Gonzales, and Montemayor; its vice-presidential columns are one vote higher for Serapio and 1,731 higher for David. The builder preserves local COC figures instead of inventing a redistribution, uses the resolution totals for national shares, and asserts those exact differences so any upstream change fails loudly. The leading candidates and all local winner classifications are unaffected.

Map geometry comes from the official PSA municipal boundary service. Every municipal feature is assigned once to its 2022 COC: separately canvassed cities remain distinct, other cities and municipalities dissolve into their province, Manila's sub-municipal pieces dissolve to Manila, and Taguig plus Pateros dissolve to their joint COC. `Compostela Valley` is labelled `Davao de Oro`, while Isabela City and Cotabato City follow the Basilan and Maguindanao COCs used in the canvass. The resulting 107 geometries and codes match both ballot files exactly.

The Mexico 2024 presidential rows come from INE's final `20240608_2030_COMPUTOS` database at 100% of its 170,766 expected polling-place records. The builder aggregates records with a federal district code into all 300 districts. Separate PAN, PRI, and PRD columns and their joint combinations are combined for Xóchitl Gálvez; PVEM, PT, Morena, and their joint combinations are combined for Claudia Sheinbaum; Movimiento Ciudadano is assigned to Jorge Álvarez Máynez. Every polling-place and district total must reconcile as candidate votes plus non-registered and null votes. The mapped districts contain 59,930,858 ballots from a nominal list of 98,245,033; special-vote records without a district code remain outside the map but contribute to the official 60,115,184-ballot national result and national valid-candidate shares.

Mexico's boundaries come from INE's national `MGS_CCL` Shapefile archive, containing exactly the 300 federal districts used by the 2024 electoral framework. They are reprojected from INE's Lambert Conformal Conic definition to WGS84, matched by state and federal district number, topology-preservingly simplified, and emitted with unique `MX2024` codes. Both official source archives are checksum-pinned so an upstream replacement requires explicit review rather than silently changing the generated data.

South Korea's 2025 and 2022 presidential rows come from the National Election Commission's official polling-district result downloads. The builder aggregates the repeated candidate and election-metadata rows into municipality/election-commission areas, requiring formal candidate votes plus invalid ballots to equal total ballots and total ballots plus abstentions to equal the electorate in every area. It also pins the exact national candidate totals before any generated file is written.

The South Korea maps use Statistics Korea's official SGIS 2025 Q2 `sigungu` boundary layer, reprojected to WGS84 and topology-preservingly simplified. Results and geometry are matched by first-level region and Korean municipality name. Hwaseong's two 2025 election-commission areas are combined for its one municipal polygon. For 2022, the three later-restored Bucheon districts are dissolved back into the election-time Bucheon area, and Gunwi is attributed to North Gyeongsang as it was before its 2023 transfer to Daegu. These adjustments prevent present-day administrative geography from being presented as historical fact.

The France 2022, 2017, 2012, and 2007 presidential entries expose each first and second round separately. Candidate, enrolment, ballot, blank/invalid, and expressed-vote figures come from checksum-pinned definitive Ministry of the Interior files on data.gouv.fr. The 2022 delimited files and 2017 workbooks already contain department and region tables. The 2012 Ministry workbook is published by commune, so the builder aggregates its rows to departments and the region structure then in force; the national candidate totals are locked before output. The 2007 workbook again supplies department and region tables directly.

The department view contains metropolitan departments, overseas departments, and department-equivalent overseas reporting territories. French citizens established abroad remain in the official national share cards but have no geographic polygon and are therefore excluded from local leaderboards and maps. Saint-Martin and Saint-Barthélemy share their published combined reporting unit from 2012 onward; in 2007 their geometry is retained with Guadeloupe, matching that workbook's reporting structure.

France's metropolitan regions changed in 2016. The 2007 and 2012 region files therefore use the 22-region metropolitan structure plus the overseas regions applicable in each year; 2017 and 2022 use the 13-region metropolitan structure plus five overseas regions. Boundaries are derived from the version-pinned 2025 data.gouv.fr administrative contours and dissolved to the historical groupings. Overseas geometry is scaled and moved into compact insets near metropolitan France for usability. These inset positions and scales are schematic, a limitation repeated in the app and every result row.

Argentina's 2023 general election and runoff and its 2019 general election come from checksum-pinned provisional polling-table archives published by the Dirección Nacional Electoral. The builder keeps only the presidential office, maps alliance labels to the named presidential candidates for the relevant year, counts each polling table once for enrolment, and aggregates positive and non-candidate ballot types to all 24 provinces. Every generated election is locked to the national candidate totals in its source archive. Argentina held no 2019 runoff because Alberto Fernández passed the constitutional first-round threshold.

Argentina's polygons come from the checksum-pinned IGN province Shapefile. The province codes and names join one-to-one to each CSV. The interactive map clips the geometry to the South American frame, omitting the Antarctic claim and remote South Atlantic islands that would otherwise dominate its extent; the result note discloses that presentation choice. No votes are removed because the election data is already reported at province level.

Brazil's 2022 and 2018 first- and second-round state views use state totals transcribed in pinned result tables attributed to the Tribunal Superior Eleitoral, with national shares fixed to the official TSE totals. The mapped scope is the 26 states plus the Federal District. Overseas votes remain in the national cards but have no false domestic polygon. To keep the static files compact and candid about the source table's published grouping, each first-round view shows the four leading candidates separately and combines all remaining candidacies as `Other candidates`; both runoff candidates are preserved individually.

Brazil's shared boundaries come from IBGE's official minimum-detail state mesh API and are keyed by the 27 official UF codes. The validator requires exact mapped candidate totals from the pinned state tables, correct local winners and margins, unique UF codes, and a one-to-one result/geometry join. Local turnout is not present in the compact state transcription and is therefore not invented.

The Portugal 2025 and 2024 legislative rows come from the official Ministry of Internal Administration election applications. The builder pins one manifest covering the domestic-district list, the official inset map, the national result, and each of the 20 domestic electoral-district result files. Party-list votes plus blank and null ballots must equal ballots cast in every district, and the district mandates must sum to 226. The remaining four seats are elected by the Europe and outside-Europe constituencies; they are included in the locked 230-seat Parliament summary but are not placed on Portugal's domestic map.

Portugal elects multiple MPs in each district by closed-list D'Hondt proportional representation. The app therefore describes its colour and margin as the locally leading party list, not as a single district winner. Map geometry is reconstructed from the official election application's own compact mainland, Azores, and Madeira inset map. It is explicitly identified as an inset presentation rather than reusable legal GIS geometry.

The Spain 2023 and November 2019 Congress rows come from the certified final constituency tables published by the Junta Electoral Central in the *Boletín Oficial del Estado*. The 2019 build reads the original publication's unchanged general turnout table and the later corrected publication's complete party tables; this assigns Zaragoza's 23,196 votes to Más País–Chunta Aragonesista–Equo as directed by the correction. For both years, every constituency's party-list votes must equal the BOE candidature-vote total, valid votes must equal candidature plus blank votes, ballots cast must equal valid plus null votes, and allocated seats must total 350.

Spain's 52 constituency shapes are derived from Eurostat GISCO's checksum-pinned 2021 NUTS 3 layer. The seven Canary Island units are dissolved into Las Palmas and Santa Cruz de Tenerife, while the three Balearic units are dissolved into Illes Balears, matching the electoral constituencies. As in Portugal, map colours and leaderboards represent the locally leading list under a multi-member closed-list D'Hondt system; the national chips show certified Congress seat totals.

The Netherlands 2025 and 2023 House rows come from the Kiesraad's certified municipality-level CSV releases. Every municipality's party-list votes must equal valid votes, and valid plus blank and invalid ballots must equal turnout. The mapped scope is the 342 municipalities of the European Netherlands. Bonaire, Saba, Sint Eustatius, and the postal-vote bureau remain represented in the certified nationwide seat allocation but are excluded from the mainland map rather than being assigned misleading polygons.

The Norway 2025 and 2021 Storting rows come directly from Valgdirektoratet's official result API. The builder follows the API's electoral-district links to all 357 municipalities in 2025 and 356 in 2021, excludes the API's duplicate aggregate `Andre` category, and treats blank plus rejected ballots as non-party ballots. It locks the nationwide valid-vote and 169-seat control totals. Municipalities are an analytical local-result view; Norway allocates constituency and levelling seats through its 19 electoral districts.

The Sweden 2022 Riksdag view aggregates Valmyndigheten's final polling-district workbook to all 290 municipalities; the 2018 view uses its official municipality workbook directly. Party totals reconcile to the published valid-vote field, while blank, other invalid, and unregistered-party ballots reconcile to ballots cast. The national chips use the certified 349-seat outcomes because Riksdag seats are allocated through 29 constituencies and national adjustment seats, not by municipality.

All six maps are derived from checksum-pinned annual Eurostat GISCO LAU TopoJSON archives. The Netherlands elections use the 2024 LAU release, which contains the same 342 municipalities in force for both elections; Norway uses the 2024 and 2021 releases, and Sweden uses the 2022 and 2018 releases. Output coordinates are topology-preservingly simplified and matched to result codes one-to-one. Boundary attribution is Eurostat GISCO / EuroGeographics.

The Finland 2023 and 2019 Parliament rows use Statistics Finland's official StatFin municipality party-vote table. They retain 309 and 311 election-year municipalities respectively and reconcile to 3,095,604 and 3,081,916 valid votes. The table's historical classification groups 2019 voters' associations, including Movement Now candidates, under `Other`. Statistics Finland's municipality turnout table excludes incompatible nonresident-voter components, so the app leaves local turnout and invalid ballots unavailable instead of deriving negative or incomplete values.

The Denmark 2026 and 2022 Folketing rows use the official Statistics Denmark `FVKOM` table. Party votes, valid votes, invalid votes, electorate, and ballots cast reconcile in every mapped area and nationally. The 2026 map contains all 98 municipalities; Christiansø is omitted because the official table records zero registered voters and zero votes there. The 2022 map retains its separately reported 59 valid votes as a 99th local area. Denmark proper elects 175 MPs through larger constituencies and compensatory allocation; the four Faroese and Greenlandic members remain in the 179-seat national summary.

The Austria 2024 and 2019 National Council rows use the Interior Ministry's final result workbooks. They preserve all 2,093 and 2,096 election-year municipalities, with Vienna represented by its single municipality polygon. Three duplicated municipality names are disambiguated by state. The workbooks report many postal ballots in separate regional rows rather than assigning them to municipalities, so map totals cover only municipality-assigned ballots and turnout remains unavailable. The 183-seat Parliament summaries use the complete national results, including postal ballots.

The six matching maps use checksum-pinned 2024 and 2019 Eurostat GISCO LAU archives. Every result code joins one-to-one to its election-year geometry. Invalid polygons introduced by compact coordinate simplification are repaired and revalidated before output.

The United Kingdom EU referendum 2016 view uses the Electoral Commission's complete 382-row counting-area CSV, preserved by the Greater London Authority under the Open Government Licence. Every local option total, rejected ballot count, electorate, turnout, winner, and margin is reconciled, and the area rows aggregate exactly to the 12 official referendum regions and the national result of 17,410,742 Leave votes and 16,141,241 Remain votes.

The 2016 counting-area map uses the ONS-derived December 2016 lower-tier local-authority layer. Its area codes join directly to 380 results. The eleven Northern Ireland local-government districts are dissolved to the single official Northern Ireland counting area. Gibraltar was the remaining separate counting area and is shown as a compact schematic inset; it is included in the South West regional totals, as in the official declaration. Counting areas and regions show local vote leaders only—the referendum had one United Kingdom-wide outcome.

The Scottish independence referendum 2014 view parses the result appendix in the Electoral Commission's official report deposited with Parliament. Its 32 council results reconcile exactly to 1,617,989 Yes votes, 2,001,926 No votes, 3,429 rejected papers, and the Chief Counting Officer's 4,283,938 electorate. Council boundaries come from the same ONS administrative source, whose Scottish council structure matches the referendum counting areas. Council colours show local majorities; the legal outcome was decided by the Scotland-wide total.

The Italy 2022 and 2018 Chamber views map proportional party-list votes across 106 provinces. Italy's Rosatellum system also elects deputies in direct constituencies, so province colours and rankings are analytical local-list leaders rather than province seat winners. Aosta Valley uses a separate direct-seat contest and is omitted from the party-list map; overseas constituencies are likewise retained only in the complete 400-seat and 630-seat Parliament summaries.

The 2022 rows come directly from the Interior Ministry's national municipality CSV. Reporting units split across constituencies are recombined before province aggregation, and party votes plus non-party ballots reconcile to turnout within every province. The 2018 Ministry portal exposed one JSON result per reporting unit; the builder uses checksum-pinned OnData copies preserving those Ministry-format rows, their geographic hierarchy, and the Ministry-to-ISTAT municipality crosswalk. The source contains two known malformed zero/undefined list-vote cells, which are signature-checked rather than silently accepting new malformed values. Compatible 2018 local ballot metadata is unavailable, so turnout is left unavailable instead of inferred. Both maps use the generalized official ISTAT province layer for the relevant election year and join all mapped province codes one-to-one.

The Türkiye presidential views cover the 2023 first round and runoff plus the single-round 2018 and 2014 elections. Rows come from checksum-pinned YSK open-data API responses for all 81 domestic provinces. Every province independently reconciles candidate votes to valid ballots and valid plus invalid ballots to ballots cast; electorate, turnout, local leader, and margin fields are derived only after those equalities pass. The official national shares include overseas and customs votes, but those votes are not assigned to province polygons. Muharrem İnce's 2023 first-round votes remain in the official data because his withdrawal came after ballots were printed.

All four Türkiye views share the current 81-province layer from the Ministry of Agriculture and Forestry's official ArcGIS service. Province IDs match YSK IDs 1–81 one-to-one. The builder requests a compact generalized geometry, repairs only polygon validity introduced by generalisation, and rejects missing, duplicate, empty, or non-polygon province features.

The Taiwan presidential views cover 2024, 2020, and 2016 at the 368-township/urban-district level. The builder reads the Central Election Commission's immutable-theme `tickets` and `profiles` JSON for every county and city. It keeps one row per presidential ticket rather than duplicating its vice-presidential member, signature-locks each complete source bundle, and requires the mapped totals to equal the official national candidate totals exactly. Within every area, ticket votes must equal valid ballots, and valid plus invalid ballots must equal ballots cast before turnout, local leader, and margin metadata are emitted.

All three elections share the official Ministry of the Interior/NLSC township boundary archive. The eight-digit township codes join directly to the CEC geographic codes one-to-one. Geometry is simplified for the static app; distant uninhabited claimed-island components are omitted so they do not collapse the interactive extent, while Taiwan, Penghu, Kinmen, and Matsu remain mapped. This display-only treatment removes no result area or votes.

The South Africa National Assembly views cover 2024, 2019, and 2014 at municipality and province level. The 2024 dataset is explicitly the IEC national ballot; its new regional ballot is not combined with it. The earlier elections use their single National Assembly party ballot. Local colours indicate the party leading in an area, while the national chips preserve the certified 400-seat outcomes under compensatory proportional representation.

The builder checksum-pins the IEC's complete voting-district archives, deduplicates repeated voting-district enrolment and ballot metadata, and requires each voting district's party rows to equal its valid-vote field before aggregation. It parses the IEC's malformed unquoted voting-station commas from the stable right-hand columns in 2019 and selects only `2014 NATIONAL ELECTION` rows from the combined national/provincial 2014 archive. Overseas reporting is excluded from domestic map aggregates rather than assigned false geometry. Municipality codes join one-to-one to official nationwide MDB boundaries: the 2011 layer for 2014 and the technically adjusted 2018 layer for 2019 and 2024; the province view is dissolved from the latter.

The United States House rows for 2016, 2018, 2020, 2022, and 2024 are parsed from the U.S. House Clerk's official Statistics of the Presidential and Congressional Election publications. Every cycle covers all 435 voting districts. Published districts reconcile candidate lines with district recapitulations, including fusion-line aggregation, unopposed returns, ranked-choice reporting, and checksum-locked corrections for PDF footnote markers joined to vote figures. Maine's 2022 2nd district and Louisiana's 2016 3rd/4th and 2020 5th districts store only the decisive round rather than mixing eliminated first-round lines into the final tally. The 2018 North Carolina 9th contest is absent from the Clerk's certified-result publication; the app preserves the State Board's three apparent totals and marks the contest void with no certified winner. The source does not contain a consistent registered-voter denominator, so enrolment and turnout remain unavailable rather than inferred.

Boundaries match the congressional map used in each election: Census cartographic districts for the 115th, 116th, 118th, and 119th Congresses. Census did not publish a national 117th Congress file because only North Carolina changed for 2020, so the builder uses the 116th national file and replaces North Carolina with the archived state remedial plan. Historical maps use the compact 1:20,000,000 files to limit repository growth; 2024 retains its existing 1:5,000,000 file. Alaska's positive-longitude Aleutian coordinates are shifted west of -180 degrees so the app's simple projection stays contiguous. DC and territorial delegate districts are outside the 435-seat scope.

The United States presidential views cover 2024, 2020, 2016, 2012, and 2008. State and District of Columbia totals come from checksum-pinned official Federal Election Commission workbooks and reconcile exactly to the published national totals. The 2008–2016 county rows come from a checksum-pinned snapshot of the MIT Election Data and Science Lab County Presidential Election Returns dataset; this replaces an earlier aggregate file that omitted millions of historical votes. The 2020 and 2024 rows continue to use the public `tonmcg/US_County_Level_Election_Results_08-24` state/media compilation. Both sources are compacted to the Democratic nominee, Republican nominee, and an `Other candidates` residual.

The builder and standalone validator independently aggregate every county file by state and candidate group and compare it with the matching FEC state result. The complete 51-area reconciliation vector is signature-locked for each election, so any changed or newly incomplete state fails CI. Remaining deltas are source-definition differences rather than votes assigned to a missing county: examples include statewide write-ins, Maine UOCAVA votes, Rhode Island's federal precinct, and some fusion-line or candidate-grouping differences. These stay in the official state view rather than being distributed across counties without evidence. Alaska and DC use their official statewide FEC totals in the local view. Kansas City's separately reported totals are combined with Jackson County, Bedford City is combined with Bedford County, and the 2016 Oglala Lakota code is mapped to the shared historical Shannon County boundary. County boundaries use a Census-compatible 2010 vintage for 2008–2016, Census 2019 counties for 2020, and Census 2023 counties/planning regions for 2024; Alaska's antimeridian geometry is normalised. The shared state map contains the 50 states and DC. Map colour intensity reflects winning margin: under 2%, 2–5%, 5–10%, 10–20%, and over 20%, with Democratic wins blue and Republican wins red.

The United States Senate views cover the regular 2024, 2022, 2020, 2018, and 2016 general-election cycles. Concurrent special elections are deliberately excluded, including the other Georgia seat in 2020, the Minnesota and Mississippi specials in 2018, and the California and Oklahoma specials in 2022. State totals use checksum-pinned official FEC workbooks through 2022 and MIT Election Lab's state file in 2024. County/reporting-area rows use checksum-pinned MIT Election Lab returns. Indiana 2018 and Connecticut 2022 are filled from state-sourced OpenElections returns because the corresponding MIT releases omit those local results.

The United States governor views cover all regularly scheduled contests in 2024, 2022, 2020, 2018, and 2016: 106 races across 5,984 mapped county/reporting areas. The builder downloads only participating states from revision- or checksum-pinned MIT Election Data and Science Lab precinct archives. Tennessee's governor rows are absent from the MIT 2022 state file, so its 95 county totals are parsed from the official Secretary of State table instead. Candidate fusion lines are combined and named write-ins are compacted while candidate totals, winners, margins, boundary joins, and the exact county-to-state aggregation are independently validated.

The governor state view is derived from those mapped returns rather than presented as a separate official statewide compilation. Local areas show gubernatorial voting patterns; they do not elect governors. Alaska's 2022 ranked-choice contest lacks safely assignable county codes in the source, so the app uses one disclosed statewide fallback polygon and does not pretend those votes are county results. Registered-voter and turnout fields remain unavailable because the source collection does not provide a consistent denominator across every state and cycle.

The Indonesia 2024 presidential province rows use the certified valid-vote totals in KPU Decision 360/2024, Appendix I. The kabupaten/kota rows use the 514-area CC0 Wikimedia structured table, which preserves KPU administrative codes and links each row to its public Sirekap `hr/ppwp/{province}.json` source. Candidate totals reconcile within every local area. Thirty-seven kabupaten/kota province aggregates match the certified KPU totals exactly; Papua Tengah is lower by 7,524 Anies–Muhaimin votes, 46,859 Prabowo–Gibran votes, and 12,622 Ganjar–Mahfud votes, or 67,005 votes overall. The app shows the certified province result, retains the structured local rows without inventing a redistribution, and displays a disclosure for Papua Tengah.

The matching province and kabupaten/kota polygons come from KPU Satu Peta endpoints, whose map states that it uses Badan Informasi Geospasial reference geography. All 38 province and 514 local polygons are matched to results by two- and four-digit KPU codes. KPU's additional North Sulawesi `7105/7110` inter-regency overlap feature is excluded because it is not a result-reporting area. The national local-area map is simplified with pinned Mapshaper shared topology and repaired only where coordinate rounding leaves an invalid ring.

The Indonesia 2019 local results come from a preserved scrape of KPU's final recapitulation hierarchy. Thirty-one province arrays reconcile directly. The preserved Lampung, DKI Jakarta, and Jawa Barat arrays incorrectly repeat the national province list, so the builder replaces only those arrays with their certified local DC1 recapitulations and requires all 514 local totals to reconcile exactly to the 34 province totals. The local geometry is unchanged from the 514-area 2024 KPU layer and is reused to save repository space; renamed areas use current display labels, but province membership is taken from the 2019 results. The province map dissolves Papua Selatan, Papua Tengah, and Papua Pegunungan back into Papua, and Papua Barat Daya back into Papua Barat.

The Indonesia 2014 province rows use the certified KPU domestic totals for the 33 reporting provinces. North Kalimantan is included in East Kalimantan, following the official recapitulation. The 497 kabupaten/kota rows aggregate the public KawalPemilu archive of digitised KPU polling-station C1 scans. Candidate totals cover 130,562,272 valid votes, or 98.24% of the 132,896,420 certified domestic valid votes; missing scans are not estimated or redistributed, and each local detail page carries that disclosure. Yahukimo, Mamberamo Tengah, Dogiyai, and Intan Jaya have zero digitised candidate totals in the archive and are shown as unavailable rather than assigned a winner. For the map, 17 local governments that appear in the modern KPU boundary layer but not the 2014 reporting hierarchy are dissolved into their historical parents. Renamed areas are matched explicitly. This preserves the 2014 units instead of assigning one old result to several modern children.

All `fpp` and `mmp-fpp` CSVs use this compact single-copy representation. Their validators reject duplicated final rows, while the browser synthesizes a final round from the candidate rows before calculating winners, margins, rankings, maps, and detail views. Preferential and Hare-Clark datasets retain their distinct published final-count rows.

The Australian Senate 2025, 2022, and 2019 views are built from the AEC's official state-by-group first-preference totals, senators-elected list, party-representation summary, informal-vote totals, and turnout totals for event IDs `31496`, `27966`, and `24310`. The builder checksum-pins every input, reconciles group votes to formal totals, requires formal plus informal to equal ballot papers issued, checks turnout, validates the elected order and party representation, and requires exactly 40 senators per election. Six senators were elected in each state and two in each mainland territory under proportional STV.

These compact views do not reconstruct the full transfer distribution. The map therefore colours each state/territory by the group leading first preferences, not by a winner-take-all result; details separately show the final elected senators, their party seat split, and the official Droop quota. The 40-seat summary is the cohort elected at that election, not the full 76-seat Senate, which also includes continuing state senators. One shared simplified ABS ASGS 2021 state/territory boundary file is used because the eight Senate constituencies did not change across these cycles.

The 2025 federal Australia boundary file is adapted from the AEC `AUS-March-2025-esri.zip` shapefile, linked from the AEC federal electoral boundary GIS download page. The result rows are generated from the AEC 2025 House of Representatives Distribution of Preferences by Division CSV, event `31496`, with no `StateAb` filtering.

The 2022 federal Australia boundary file is adapted from the AEC `2021-Cwlth_electoral_boundaries_ESRI.zip` shapefile, linked from the AEC federal electoral boundary GIS download page. The result rows are generated from the AEC 2022 House of Representatives Distribution of Preferences by Division CSV, event `27966`, with no `StateAb` filtering.

The 2019 federal Australia boundary file is adapted from the AEC `national-esri-fe2019.zip` shapefile. The result rows are generated from the AEC 2019 House of Representatives Distribution of Preferences by Division CSV, event `24310`, with no `StateAb` filtering. The boundary file uses the legacy spelling `Mcpherson`; the builder normalises this to the AEC result spelling `McPherson`.

The 2016 federal Australia boundary file is assembled from the official AEC jurisdiction files used for the 2016 election period: `act-tab-20072016.zip`, `nsw-esri-06042016.zip`, `NT-20080919-elb.zip`, `qld-shape-files-13012010.zip`, `sa-esri-16122011.zip`, `TAS-20080216-elb.zip`, `vic-esri-24122010.zip`, and `wa-esri-19012016.zip`. The result rows are generated from the AEC 2016 House of Representatives Distribution of Preferences by Division CSV, event `20499`, with no `StateAb` filtering. The builder reprojects each jurisdiction to WGS84 lon/lat and normalises `Mcpherson` to `McPherson`.

The 2013 federal Victoria boundary file uses the same AEC `vic-esri-24122010.zip` shapefile because those Victorian federal divisions were gazetted on 24 December 2010 and applied to the 2013 federal election. The result rows are generated from the AEC 2013 House of Representatives Distribution of Preferences by Division CSV, event `17496`, filtered to `StateAb == VIC`.

The 2010 federal Victoria boundary file is adapted from the AEC `national-esri-2010.zip` shapefile because the AEC states the 2010 federal election in Victoria ran on the same boundaries as the 2007 election while the 2010 Victorian redistribution was still underway. The result rows are generated from the AEC 2010 House of Representatives Distribution of Preferences by Division CSV, event `15508`, filtered to `StateAb == VIC`. The older national GIS file provides `ELECT_DIV` and `STATE` fields but no numeric division ID, so the builder filters `STATE == VIC` and leaves `division_id` blank for this boundary source.

The 2007 federal Victoria entry reuses the 2010 boundary file because both were generated from the same AEC `national-esri-2010.zip` shapefile and are byte-identical. The result rows are generated from the AEC 2007 House of Representatives Distribution of Preferences by Division CSV, event `13745`, filtered to `StateAb == VIC`.

## Victorian local councils 2024

The Victorian local-government entry covers the standard 31 Greater Melbourne councils. Thirty councils use 288 single-councillor wards. The builder discovers their canonical result pages from the VEC's 2024 council index, parses enrolment and formal/informal totals, and retains complete downloadable preference distributions where the VEC publishes them. Eight wards were uncontested and are explicitly represented as elected unopposed with no invented poll totals. Where a recount replaced an earlier workbook, the final recount figures displayed by the VEC take precedence.

Melbourne City Council is structurally different. Its Lord Mayor and Deputy Lord Mayor nominate as a paired leadership team under preferential voting, while nine councillors are elected citywide by proportional representation. These are exposed as separate internal views. The councillor view preserves the official distribution workbook's candidate first preferences—including allocated above-the-line ticket votes—and final count standing, elected order, and quota.

Ordinary VEC ward result pages do not state candidate party affiliation. The generated rows therefore say `Affiliation not stated`; the app does not infer affiliation from biographies, endorsements, media coverage, or later council behaviour. The metropolitan map uses a neutral winning-margin scale. Melbourne team/group labels are retained because the official result page publishes them.

Ward geometry comes from the official Vicmap Admin `WARD_2024` WFS layer produced for the 2024 local elections. The builder filters it to the 30 warded metropolitan councils, uses council-plus-ward identifiers to prevent duplicate-name collisions, and requires all 288 results to join one-to-one. Melbourne's citywide contests use the official Vicmap LGA polygon. Mitchell is excluded because it is not one of the standard 31 metropolitan municipalities, despite being partly included in some planning definitions. Later by-elections and vacancies are not merged into the 2024 general-election snapshot.

## Why long format?

The VEC pages are visually wide tables. Long format is better for:

- filtering by district
- drawing bar charts
- tracking progressive totals
- map-linked district drilldowns
- summary calculations
