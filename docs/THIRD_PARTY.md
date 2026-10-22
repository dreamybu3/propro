# Data, dependencies and attribution

GapLens code is distributed under the root [MIT license](../LICENSE). Its own code implements retrieval, endpoint correction, relative scales, calibration, data contracts, provenance, reporting and experimental orchestration. It does not claim authorship of the underlying mathematical families or of external components.

## Included real data

Three processed files and derived examples/results come from the official Numenta/NAB repository at commit `ea702d75cc2258d9d7dd35ca8e5e2539d71f3140`. Its inspected license is MIT, copyright 2014–2024 Numenta Inc. The full notice is included in [data/LICENSE-NAB.txt](../data/LICENSE-NAB.txt). Preserve that notice when distributing the data or derived examples.

The [manifest](../data/manifest.json) identifies immutable source URLs, SHA-256 hashes, source/processed counts and exact transformations. NAB attributes the real sources to office temperature, AWS utilization, and NYC Taxi and Limousine Commission passenger records. Those providers' separate original terms were not independently audited; this project records the corpus distributor's supplied license and provenance. Ambient missing timestamps were inserted as missing rows, without inventing measurements. Evaluation masks are artificial; source values are real.

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
