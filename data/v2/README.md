# GapLens v2 evaluation data

This corpus contains **14 distinct scalar signals**, released by **6 collections**,
with **8 conservative provider/domain groups**. It contains 12 labeled observation
system groups; those labels do **not** establish statistical independence. Three
AWS metrics share one group because their asset linkage is unknown. Countries
share a pandemic and reporting pipeline; ticker counts share a social platform;
advertising exchanges may share market shocks. Do not describe these data as
14 independent physical systems.

The three v1 series (`nyc_taxi`, `cpu_utilization`, `ambient_temperature`) remain
development data. Their original files and results are not modified. Selection
of the new corpus used licenses, provenance, cadence, and missingness metadata,
without looking at predictions, scores, performance plots, correlations, or
final-test patterns. The protocol determines the evaluation splits and masks.

| ID | Observation | Cadence | Rows | Native missing | Conservative group |
|---|---|---|---:|---:|---|
| `co2_mauna_loa` | Atmospheric CO₂, ppmv | 7 days | 2,284 | 59 | Mauna Loa CO₂ |
| `brent_weekly` | Weekly Brent spot price, USD/barrel | 7 days | 2,058 | 3 | EIA Brent |
| `ssa_births` | US births by calendar date | Daily | 5,479 | 0 | SSA births |
| `seattle_temp_max` | Daily maximum temperature, °C | Daily | 1,461 | 0 | NOAA Seattle |
| `jhu_deaths_germany` | Signed daily reporting increment | Daily | 1,142 | 0 | JHU COVID reporting |
| `jhu_deaths_japan` | Signed daily reporting increment | Daily | 1,142 | 0 | JHU COVID reporting |
| `jhu_deaths_us` | Signed daily reporting increment | Daily | 1,142 | 0 | JHU COVID reporting |
| `nab_tweets_aapl` | Ticker mention count | 5 minutes | 15,902 | 0 | NAB Twitter mentions |
| `nab_tweets_ibm` | Ticker mention count | 5 minutes | 15,893 | 0 | NAB Twitter mentions |
| `nab_ec2_cpu` | CPU utilization | 5 minutes | 4,032 | 0 | NAB AWS CloudWatch |
| `nab_ec2_network` | Incoming network bytes | 5 minutes | 4,034 | 2 | NAB AWS CloudWatch |
| `nab_elb_requests` | Load-balancer request count | 5 minutes | 4,040 | 8 | NAB AWS CloudWatch |
| `nab_ad_cpc_exchange3` | Advertising cost per click | Hourly | 1,647 | 109 | NAB advertising |
| `nab_ad_cpc_exchange4` | Advertising cost per click | Hourly | 1,647 | 4 | NAB advertising |

The count of source groups is a conservative analysis convention, not a sample
of eight randomly drawn populations. Source-cluster uncertainty and leave-group
out sensitivity have limited resolution with this corpus. No selected pair has
an identical full numerical vector after preparation; that duplicate check does
not prove absence of dependence. Seven new streams come from the NAB release
also used for development, so collection-level separation is incomplete even
though the development series are not reused as final evaluation signals.

## Reproduce and verify

Run in the pinned project environment, from any directory:

```bash
python /path/to/propro/scripts/fetch_data_v2.py --verify-only
python /path/to/propro/scripts/fetch_data_v2.py
```

The first command checks bundled processed hashes, counts, and regular grids
offline. The second downloads **immutable commit URLs**, checks the source
SHA-256, repeats the declared transformation, and checks the processed SHA-256.
It caches sources under ignored `data/raw/v2/`. It fails on differing existing
files instead of overwriting them. No API keys, paid APIs, or GPU are required.
The bundled files allow offline experiments; downloading is needed only to
independently rebuild preparation. `manifest.json` records every URL, commit,
hash, transformation, count, unit, period, and local output path. Pinned
provenance/license files and their hashes are also listed there.

## Exact preparation and time semantics

All output files have `timestamp,value` columns. Timestamps use ISO 8601 UTC
encoding. **UTC encoding is a storage convention** for source-naive labels;
it is not evidence that a publisher measured in UTC. Daily/weekly dates denote
observation/reporting periods, not precise instants. No local time zone is
invented. Models using hour/weekday features should interpret them accordingly.

- NAB: retain the published values and timestamp phase; insert absent grid
  rows as empty values. Reject duplicates, unsorted dates, and off-grid dates.
  No resampling or interpolation is applied to the selected NAB series.
- CO₂: parse the original `YYYYMMDD` sample dates, retain weekly values and
  all 59 source missing entries. The recorded weeks are seven days apart.
- Brent: use EIA's already aggregated weekly observations, with Friday-ending
  date labels. Insert three absent Fridays as empty values. No daily-to-weekly
  averaging is performed by GapLens.
- Births: assemble the supplied year/month/day and validate against its
  independently supplied weekday. Select `births`; no aggregation is needed.
- Seattle: select numeric `temp_max`. Vega's documented source transformation
  divides NOAA TMAX tenths of a degree by ten. The synthetic categorical
  `weather` field is **not used**. GapLens does not modify temperatures.
- JHU: select the single national cumulative-deaths row for each named
  country, then first-difference successive daily reports. Omit the first
  undefined increment; do not assume a pre-series zero. Retain negative
  retrospective revisions: Germany has 3, Japan 1, and US 4. These signals are
  **signed changes in reported cumulative deaths**, not occurrence-date death
  counts. No provincial rows are combined with national totals, and no
  clipping, smoothing, or forward-fill is performed.

No source is normalized, imputed, sorted, or deduplicated. Native missing values
have no known truth and cannot be scored. Artificially hidden finite values
provide evaluation truth only to the mask generator/evaluator under the frozen
protocol; they are not genuine missing observations.

## Source rights, attribution, and scope

Retrieved source snapshots: **2026-10-22**. The retrieval date is not represented
as a dataset's original publication date. Each immutable source URL is in the
manifest. All selected data permit redistribution under the checked source
statements; project MIT licensing does not replace third-party terms.

- **NAB:** Copyright 2014–2024 Numenta Inc., MIT; full notice in
  [LICENSE-NAB.txt](LICENSE-NAB.txt), dataset descriptions in
  [NAB-data-README.md](provenance/NAB-data-README.md). The release license is the
  permission evidence. Rights of every earlier provider were not separately
  audited; metadata does not establish independence of anonymous assets.
- **Mauna Loa CO₂:** statsmodels' dataset-specific declaration is public domain
  and identifies CDIAC/Scripps provenance. Cite Keeling, C. D. and T. P. Whorf
  (2004), “Atmospheric CO₂ concentrations derived from flask air samples at sites
  in the SIO network,” *Trends: A Compendium of Data on Global Change*, Carbon
  Dioxide Information Analysis Center, Oak Ridge National Laboratory, US DOE.
  Preserve the source qualification that this weekly series describes
  continuous-sample measurements, as documented in
  [CO2-data.py.txt](provenance/CO2-data.py.txt).
- **Brent:** Source: U.S. Energy Information Administration, weekly Europe Brent
  spot prices, through **2026-10-16**, as archived in the pinned DataHub package
  retrieved 2026-10-22. EIA data are public domain; additional packaging is
  [PDDL 1.0](https://opendatacommons.org/licenses/pddl/1-0/). The package quotes
  EIA's reuse statement in [EIA-oil-package-README.md](provenance/EIA-oil-package-README.md).
- **SSA births:** Social Security Administration daily totals, released by
  FiveThirtyEight under [CC BY 4.0](LICENSE-CC-BY-4.0.txt). Attribution:
  FiveThirtyEight, “U.S. Births,” with SSA as original provider;
  [source description](provenance/SSA-births-README.md). GapLens extracts the
  births column and changes date/CSV formatting as described above.
- **Seattle:** NOAA National Climatic Data Center observations, packaged by
  Vega Datasets. The dataset-specific `seattle_weather` entry in
  [Vega-datapackage.json](provenance/Vega-datapackage.json) declares “U.S.
  Government Dataset”/public domain and identifies NOAA. The preserved
  [generation script](provenance/Vega-weather.py.txt) documents numeric conversion.
- **JHU:** “JHU CSSE COVID-19 Data,” Copyright Johns Hopkins University 2020,
  [official repository](https://github.com/CSSEGISandData/COVID-19), licensed
  [CC BY 4.0](LICENSE-CC-BY-4.0.txt) as stated in the preserved
  [JHU README](provenance/JHU-README.md). GapLens extracts countries, computes
  signed first differences, and reformats dates; it does not claim these
  derived observations are JHU's unmodified table. Cite Dong, E., Du, H., and
  Gardner, L. (2020), “An interactive web-based dashboard to track COVID-19 in
  real time,” *The Lancet Infectious Diseases* 20(5), 533–534,
  [doi:10.1016/S1473-3099(20)30120-1](https://doi.org/10.1016/S1473-3099(20)30120-1).

Original license disclaimers apply; no provider endorsement is implied. Direct
NOAA/EIA policy pages returned an environment proxy HTTP 403 during this review;
the provenance evidence is the pinned explicit dataset/package statements above.
This limitation is recorded rather than claiming those pages were inspected.

## Metadata-only exclusions

The manifest preserves exclusions and their reasons. ETT's official **dataset**
license is CC BY-ND 4.0, so it was excluded to avoid ambiguity when publishing
transformed data and detailed derived artifacts. An MIT license on related model
code does not relicense the dataset. Monthly El Niño and yearly sunspots do not
fit this product's constant-duration grid. NAB traffic candidates had irregular
minute phases, duplicates, or insufficient dense context; hourly TravelTime 387
has 879 missing bins out of 1,660 and only two complete 24-sample windows.
None of these decisions used method scores or final-test outcomes.
