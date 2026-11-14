# U.S. House 2024: first demographic correlations

Bismillah, this is a descriptive district-level exploration of the joined local datasets.
No causal or individual-voter conclusions are drawn.

The join retains all **435 districts** and all **42 demographic indicators with their MOEs**.
The baseline uses **397 districts** with named Democratic and Republican candidates, positive party vote totals, and official results.
The other **38 districts** remain in the joined CSV with exclusion reasons and blank two-party shares.
Both-party vote totals include explicitly party-labelled write-ins; unclassified write-ins remain Other.

## First relationships

Outcome: Democratic two-party vote share, 100 × D / (D + R). Positive correlations mean higher values occur in districts with higher Democratic shares; negative correlations mean lower shares.
These ten indicators were selected before computing correlations to cover education, income, poverty, age, housing and racial/ethnic composition.

| Indicator | n | Pearson r | Spearman ρ | Within-state r | Sensitivity r |
| --- | ---: | ---: | ---: | ---: | ---: |
| Adults 25+ with a bachelor's degree or higher | 397 | 0.409 | 0.393 | 0.338 | 0.413 |
| Median household income in 2024 inflation-adjusted dollars | 397 | 0.258 | 0.262 | 0.009 | 0.261 |
| People below the poverty level, among those with poverty status determined | 397 | 0.154 | 0.064 | 0.332 | 0.162 |
| Median age | 397 | -0.283 | -0.268 | -0.475 | -0.293 |
| Residents aged 65 and over | 397 | -0.323 | -0.315 | -0.461 | -0.331 |
| Owner-occupied share of occupied housing units | 397 | -0.658 | -0.630 | -0.706 | -0.661 |
| Non-Hispanic White alone residents | 397 | -0.590 | -0.596 | -0.694 | -0.595 |
| Non-Hispanic Black alone residents | 397 | 0.380 | 0.270 | 0.656 | 0.391 |
| Non-Hispanic Asian alone residents | 397 | 0.417 | 0.577 | 0.257 | 0.421 |
| Hispanic / Latino residents of any race | 397 | 0.273 | 0.358 | 0.236 | 0.275 |

Every district has equal weight. Spearman uses average ranks for ties.
Within-state r demeans both variables within state before correlating them; it removes differences in state averages, not other demographic or candidate effects.
Sensitivity r uses **389 districts**, excluding Alaska/Maine and races with multiple named candidates of a major party. It is a robustness comparison, not a correction for every difference in election rules.
The machine-readable correlation CSV contains both sample definitions and their sample sizes.

## Districts furthest from the education-only line

These are the five largest absolute residuals from a simple least-squares line fitted to bachelor's-degree share and Democratic two-party vote share in the baseline sample.
A positive residual means a higher Democratic share than that descriptive line; these are not forecasts, anomalies in the source, or estimates of a candidate effect.

| District | Bachelor's degree or higher (%) | Democratic two-party share (%) | Residual (pp) |
| --- | ---: | ---: | ---: |
| Maryland 4th | 35.24 | 88.72 | +39.79 |
| New York 15th | 21.88 | 78.36 | +37.13 |
| New York 13th | 35.35 | 83.54 | +34.54 |
| Maryland 7th | 34.15 | 82.38 | +34.08 |
| California 43rd | 22.19 | 75.07 | +33.66 |

## Limits

- Demographics describe residents/households and each indicator's documented universe, not the people who voted. Group-level associations do not establish individual voting behavior or causation.
- Correlations use point estimates. ACS margins of error are retained but are not propagated into correlation uncertainty. No p-values, causal models or significance claims are produced.
- The sample excludes missing-party and same-party contests and is not representative of every district. Candidate effects, incumbency, turnout composition, district boundaries and other demographics can affect the relationships.
- Source candidate totals are retained as published in the existing repo. Ranked-choice transfer rounds are not reconstructed. Multiple same-party candidates are aggregated into party totals; candidate winning margin is a different measure from D–R party margin.
- Florida 20th and Oklahoma 3rd have no reported candidate vote totals in the source. Their recorded zeros are preserved and flagged; all vote-share and candidate-margin fields are blank.
- Two language indicators have five source gaps. The ten first-pass indicators above have complete coverage in the baseline sample.

## Explore in the app

Serve the repo locally and open `app/?year=us-house-2024&view=demographics`.
The Demographics view links the district scatterplot to the election map and full results. Choose among all 42 indicators and either district sample; inspect the selected district's 90% estimate uncertainty on demand.
The view shows Pearson, Spearman and within-state correlations for the chosen measure. It loads data only when opened, preserves missing values, and supports keyboard/touch selection and shareable URLs. Map filters do not change the election-wide analysis sample.

## Files and reproduction

- `data/us_2024_house_analysis.csv`: 435 joined district rows with result totals, eligibility flags, 42 indicators and their MOEs.
- `data/us_2024_house_analysis_metadata.json`: input/output hashes, result-field definitions, demographic dictionary and sample definitions.
- `data/us_2024_house_analysis_correlations.csv`: Pearson, Spearman and within-state correlations for both samples.

```bash
python3 scripts/build_us_house_analysis.py
python3 scripts/validate_us_house_analysis.py
python3 scripts/test_us_house_analysis.py
```

See [demographic source documentation](us_house_2024_demographics.md) for official Census sources, boundary vintage, uncertainty methods and missingness.
