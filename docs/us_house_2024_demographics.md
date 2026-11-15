# U.S. House 2024 demographic data

Bismillah, these files join official **2024 American Community Survey (ACS)
1-year estimates** to the repo's 435 voting House districts. This is a data-only
addition; it does not calculate correlations or add an explorer view.

The separate [district-level analysis](us_house_2024_analysis.md) joins these
indicators to the election results and documents the first correlations. The
source demographic files remain unchanged by that join. The explorer's **House
2024 → Demographics** view shows all 42 indicators beside the map. Select a dot,
map district or district option to inspect its result and 90% estimate uncertainty.
The chart can show either Democratic or Republican two-party vote share. Each
axis has an independent **Full range / Fit data** control. Full percentage axes
use 0–100; other full axes start at zero. Fitted axes cover the observed district
values with 5% padding (clamped to 0–100 for percentages). Axis settings do not
change the sample or correlations, and party/range settings persist in the URL.

## Files

| File in `data/` | Contents |
| --- | --- |
| `us_2024_house_demographics.csv` | One row per district; 42 named demographic indicators, each with a `_moe` column |
| `us_2024_house_demographics_acs.csv` | All 355 source estimates and their published MOEs from 18 tables, using Census variable IDs |
| `us_2024_house_demographics_metadata.json` | Variable labels, universes, metric formulas, units, source URLs, retrieval times, checksums and table coverage |
| `us_2024_house_demographics_flags.csv` | Original special-value tokens, controlled MOEs and missing source-table rows |

The CSVs use UTF-8. Preserve `constituency_code` as a **four-character string**:
two-digit state FIPS plus two-digit congressional district, with `00` for an
at-large seat. For example, `0101` is Alabama 1st and `0200` is Alaska at-large.
This key already exists in `us_2024_house_fpp.csv` and
`us_2024_congressional_boundaries.geojson`. Joining election candidate rows to
demographics is many-to-one; aggregate election results to one district row
before computing district correlations.

`census_geo_id` retains the Census identifier, such as `5001900US0101`. The
`5001900` prefix identifies the **119th Congress**, the districts used for the
2024 election. DC and nonvoting territories are excluded. Never join other
election years solely by district number: the geographic footprint can change.

## Coverage and definitions

| Tables | Content |
| --- | --- |
| B01001, B01002 | Sex, age counts and median age |
| B03002 | Race and Hispanic / Latino origin |
| B05002, B05003 | Birthplace, citizenship, sex and adult population |
| B29001 | Citizen voting-age population by age |
| B15003 | Educational attainment for residents aged 25+ |
| C16001 | Language spoken at home and English proficiency for residents aged 5+ |
| B17001 | Poverty status by sex and age |
| B19001, B19013 | Household income brackets and median household income |
| B23025 | Employment and labor-force status for residents aged 16+ |
| C24030 | Industry by sex for civilian employed residents aged 16+ |
| B25003, B25064, B25077 | Housing tenure, median gross rent and median home value |
| B11001 | Household composition |
| C08301 | Means of transportation to work |

Seventeen tables cover all 435 districts. The condensed language table C16001
contains 430: **Alabama 4th (`0104`), Mississippi 2nd (`2802`), Oregon 2nd
(`4102`), Texas 16th (`4816`), and Texas 34th (`4834`)** are absent from the
published source. Both language indicators and their MOEs are blank for these
five districts. The manifest records the gaps; the flags file identifies every
affected source cell. There is no imputation or substitution from a different
survey year. Condensed language and commuting tables were chosen because their
more detailed counterparts have substantially less district coverage.

Each percentage has a specific denominator documented in the dictionary:
education uses people aged 25+, poverty excludes people without a determined
poverty status, unemployment uses the civilian labor force, and homeownership
uses occupied housing units. Race indicators use non-Hispanic categories;
Hispanic / Latino includes people of any race, making the eight named categories
mutually exclusive and collectively exhaustive.

Dollar estimates use 2024 dollars. These are characteristics of residents and
households, not the people who actually voted. Citizen voting-age population is
not a count of registered or legally eligible voters. No turnout rate is inferred.

## Uncertainty and special values

`_moe` is the **90% margin of error**, in the indicator's units. For percentages
this means percentage points. Source MOEs are preserved in `_acs.csv`; direct
indicators use the published MOE. Derived sums use root-sum-of-squares, and
percentages use the Census subset-proportion formula, with the ratio formula
when the subtraction under the square root is negative. These derived MOEs are
approximations, not published profile MOEs, and are not clipped to 0–100.

Negative Census sentinel values and unavailable cells are preserved in the raw
CSV and explained in the flags file. They become blank derived values, never
zero population or zero percent. The specific MOE token `-555555555` means a
**controlled estimate**: it contributes zero sampling variability when deriving
MOEs. Its controlled status remains in the flags. There are 32 such source MOE
cells across the six at-large states. A zero sampling MOE does not eliminate
nonsampling error.

## Rebuild and validate

Only Python's standard library is needed. The builder downloads official public
bulk files and public variable metadata without an API key. National raw files
are cached in ignored `tmp/us_house_demographics/`.

```bash
python3 scripts/build_us_house_demographics.py
python3 scripts/validate_us_house_demographics.py --cache tmp/us_house_demographics
python3 scripts/test_us_house_demographics.py
```

Rebuild without network access with `--offline`. Use `--refresh` to redownload
the sources deliberately; their checksums and retrieval times are recorded in
the manifest. The validator checks file checksums, unique district identities,
result/boundary joins, variable coverage, flags, population and category totals,
CVAP reconciliation, derived indicator arithmetic, and percentage ranges.

## Official sources

- [2024 ACS table-based Summary File and documentation](https://www.census.gov/programs-surveys/acs/data/summary-file.2024.html)
- [2024 ACS 1-year bulk tables](https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/1YRData/)
- [2024 congressional geography changes](https://www.census.gov/programs-surveys/acs/technical-documentation/table-and-geography-changes/2024/geography-changes.html)
- [2024 ACS statistical testing and derived uncertainty formulas](https://www2.census.gov/programs-surveys/acs/tech_docs/statistical_testing/2024_Instructions_for_Stat_Testing_ACS.pdf)
- [Census special-value and annotation definitions](https://www.census.gov/data/developers/data-sets/acs-1year/data-notes.html)
