"""Create the documented demo by hiding actual later NYC taxi observations."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from gaplens.data import read_series


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument('--source', type=Path, default=root / 'data/processed/nyc_taxi.csv')
    parser.add_argument('--output', type=Path, default=root / 'examples')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    names = ['reference.csv', 'with_gaps.csv', 'ground_truth.csv', 'provenance.json']
    if not args.overwrite and any((args.output / name).exists() for name in names):
        parser.error('Demo artifacts already exist; use --overwrite to regenerate the same deterministic masks')
    frame = read_series(args.source)
    a, b = int(.6 * len(frame)), int(.8 * len(frame))
    reference = frame.iloc[:a].copy()
    truth = frame.iloc[b:].reset_index(drop=True)
    query = truth.copy()
    masks = []
    for center, length in zip((.2, .5, .8), (6, 12, 24)):
        start = int(len(query) * center)
        end = start + length
        if start < 6 or end + 6 > len(query) or not np.isfinite(query.value.iloc[start-6:end+6]).all():
            parser.error('Source is too short or incomplete for the fixed demo masks')
        query.loc[start:end-1, 'value'] = np.nan
        masks.append({'start_index': start, 'end_index_exclusive': end, 'length': length})
    args.output.mkdir(parents=True, exist_ok=True)
    reference.to_csv(args.output / 'reference.csv', index=False)
    query.to_csv(args.output / 'with_gaps.csv', index=False)
    truth.to_csv(args.output / 'ground_truth.csv', index=False)
    provenance = {'source': 'Numenta/NAB realKnownCause/nyc_taxi.csv',
                  'source_processed_sha256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
                  'source_rows': len(frame), 'reference_rows': a, 'input_start_source_index': b,
                  'masking': 'Deterministic artificial missingness on real observations; ground truth is for verification only.',
                  'gaps': masks, 'data_license': 'MIT; see data/LICENSE-NAB.txt',
                  'command': 'python scripts/make_demo.py'}
    (args.output / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n', encoding='utf-8')
    print(f'Created {args.output}: {a} history rows; {len(query)} input rows; 3 gaps / 42 hidden observations.')


if __name__ == '__main__':
    main()
