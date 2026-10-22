# Data, dependencies and attribution

GapLens code is distributed under the root [MIT license](../LICENSE). Its own code implements retrieval, endpoint correction, relative scales, calibration, data contracts, provenance, reporting and experimental orchestration. It does not claim authorship of the underlying mathematical families or of external components.

## Included real data

Three processed files and derived examples/results come from the official Numenta/NAB repository at commit `ea702d75cc2258d9d7dd35ca8e5e2539d71f3140`. Its inspected license is MIT, copyright 2014–2024 Numenta Inc. The full notice is included in [data/LICENSE-NAB.txt](../data/LICENSE-NAB.txt). Preserve that notice when distributing the data or derived examples.

The [manifest](../data/manifest.json) identifies immutable source URLs, SHA-256 hashes, source/processed counts and exact transformations. NAB attributes the real sources to office temperature, AWS utilization, and NYC Taxi and Limousine Commission passenger records. Those providers' separate original terms were not independently audited; this project records the corpus distributor's supplied license and provenance. Ambient missing timestamps were inserted as missing rows, without inventing measurements. Evaluation masks are artificial; source values are real.

The v2 corpus adds 14 streams; its complete [rights and transformation ledger](../data/v2/README.md)
and [immutable-source manifest](../data/v2/manifest.json) accompany the files.
SSA births and JHU reporting increments are attributed under CC BY 4.0;
CO2 and NOAA-derived numeric weather are declared public domain; EIA oil data
are public domain with PDDL packaging; NAB-distributed streams retain the MIT
notice and documented original-provider audit limitation. Corresponding source
terms also apply to redistributed evaluation truth and source-derived v2
artifacts, including prediction tables and examples. Preserve the source
attribution, links, license notices and descriptions of changes. The root MIT
license governs GapLens code and does not replace these data terms.

## Runtime components

| Component | Used for | Upstream license |
| --- | --- | --- |
| NumPy | Array operations, distances, deterministic random sampling | BSD-3-Clause |
| pandas | CSV, timestamps, data tables | BSD-3-Clause |
| SciPy | Scientific dependency of scikit-learn; no custom SciPy algorithm claimed | BSD-3-Clause |
| scikit-learn | ExtraTrees baseline and its tree implementation | BSD-3-Clause |
| Matplotlib | Reproducible research PNG/SVG figures | Matplotlib license (PSF-derived) |
| Python standard library | CLI, hashing, HTTP download, JSON, paths | Python Software Foundation license |
| pytest | Development tests | MIT |
| Hatchling | Python package build | MIT |

Exact direct/transitive versions, platform markers and distribution hashes are in `uv.lock` and `requirements.lock`. Installed packages retain their own license notices; consult their distribution metadata for the complete texts and bundled third-party notices. The browser test optionally uses platform-provided Playwright (Apache-2.0) and Chromium (multiple third-party licenses); neither is a runtime requirement of GapLens. HTML reports embed no external JavaScript, CSS, font or model asset.

## Related research

imputeTS, ImputeGAP, BRITS, SAITS, CSDI, EnbPI and MAPIE were consulted as related work. Their implementation code or model weights are not included in this repository, and their benchmark claims were not reproduced here. Citations and actual access records appear in [SOURCES.md](SOURCES.md).

The deeper v2 review adds AnDA, DynaMMo, Rssa/SSA, TKCM, STUMPY and SPCI.
Our PCA, Kalman and separated-retrieval implementations use established
mathematical ideas; they are not copies or claimed exact reproductions of those
packages. See [v2 sources](v2/SOURCES.md) for primary-source access, bibliographic
details and limitations, including the attributed third-party TKCM code inspected.
