# Data provenance and reuse

The three bundled files in `processed/` are derived from **real observations** in
the [Numenta Anomaly Benchmark (NAB)](https://github.com/numenta/NAB), pinned to
commit `ea702d75cc2258d9d7dd35ca8e5e2539d71f3140` and retrieved on 2026-10-22.
No artificial NAB series is included. `manifest.json` records immutable source
URLs, SHA-256 digests, sizes, dates, cadence, preprocessing, and output digests.

| ID | Original observations | Regular-grid rows | Native missing rows | Cadence | Meaning |
| --- | ---: | ---: | ---: | --- | --- |
| `nyc_taxi` | 10,320 | 10,320 | 0 | 30 minutes | Aggregated NYC taxi passenger counts |
| `cpu_utilization` | 18,050 | 18,050 | 0 | 5 minutes | CPU utilization across an AWS cluster, including autoscaling misconfiguration |
| `ambient_temperature` | 7,267 | 7,888 | 621 | 1 hour | Ambient office temperature, including outages |

The [upstream corpus description](https://github.com/numenta/NAB/blob/ea702d75cc2258d9d7dd35ca8e5e2539d71f3140/data/README.md)
describes the original sources and known events. NYC taxi counts originate from
[NYC Taxi and Limousine Commission trip records](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page),
aggregated by NAB. We consume NAB's supplied aggregate, not individual trips.
Units for temperature and CPU utilization are not normalized or independently
verified; errors therefore use the original series units and normalized metrics
where cross-series comparisons are needed.

## License

At the pinned revision, NAB's root [`LICENSE.txt`](https://github.com/numenta/NAB/blob/ea702d75cc2258d9d7dd35ca8e5e2539d71f3140/LICENSE.txt)
is the MIT license, copyright 2014–2024 Numenta Inc. A verbatim copy is included
as [`LICENSE-NAB.txt`](LICENSE-NAB.txt). The reviewed corpus README specifies no
separate data license. These copies are distributed following that upstream
repository license and preserve its notice. The source's underlying provenance
is retained above; this is not an assertion that we independently audited all
upstream contributors' rights. GapLens does not use NAB's detector code.

## Exact preparation

From the project root, after installing pinned Python dependencies:

```console
python scripts/fetch_data.py
```

This fetches the three immutable CSV URLs through ordinary HTTPS with TLS
verification, checks their expected SHA-256 values, and writes `data/raw/`.
Subsequent runs reuse checksum-verified raw files without network access. A hash
mismatch fails explicitly. Existing different files are never silently replaced.
The processed datasets are included, so ordinary demonstrations and experiments
can run offline without fetching anything.

Preparation parses original measurements with round-trip float precision and
puts each source on its documented regular sampling grid. It inserts **empty
values**, not interpolated observations, at the 621 absent hourly timestamps in
the ambient-temperature series. The other two files require no new rows. It does
not sort, deduplicate, smooth, remove anomalies, clip values, or impute anything.
The original values retain their original numeric units. Naive source clock times
are marked UTC only to make indexing unambiguous; the source does not establish
their actual geographic timezone. No local-time or DST interpretation is claimed.

The generic `gaplens.data.read_series` validator does **not** silently regularize
user input. A user-supplied CSV must already have a unique, increasing regular
timestamp grid, with empty cells for missing values.

## Evaluation limits

NAB was designed for anomaly detection, not gap reconstruction. GapLens creates
controlled missing blocks in **observed real values** to obtain ground truth for
evaluation. These are synthetic missingness patterns on real signals, not a
measurement of accuracy on genuine outages. Native missing ambient-temperature
values have no ground truth and are excluded from scored windows. Unusual events
remain in the data; no outcome-based filtering is performed. The series are small,
historical, univariate, and not representative of every monitoring system.
