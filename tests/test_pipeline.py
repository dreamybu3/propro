from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from gaplens.data import read_series
from gaplens.pipeline import RepairConfig, repair
from gaplens.report import render_report


@pytest.fixture
def inputs(tmp_path):
    n = 2400
    t = pd.date_range('2020-01-01', periods=n + 300, freq='h', tz='UTC')
    values = 10 + .002 * np.arange(n + 300) + 2 * np.sin(np.arange(n + 300) * 2 * np.pi / 24)
    reference = pd.DataFrame({'timestamp': t[:n], 'value': values[:n]})
    query = pd.DataFrame({'timestamp': t[n:], 'value': values[n:]})
    query.loc[80:87, 'value'] = np.nan
    reference.to_csv(tmp_path / 'reference.csv', index=False)
    query.to_csv(tmp_path / 'query.csv', index=False)
    return tmp_path / 'reference.csv', tmp_path / 'query.csv'


def test_complete_pipeline_preserves_observations_and_exports_intervals(inputs, tmp_path):
    reference, query = inputs
    output = tmp_path / 'result'
    report = repair(reference, query, output)
    saved = pd.read_csv(output / 'repaired.csv', float_precision='round_trip')
    original = read_series(query).value.to_numpy()
    finite = np.isfinite(original)
    assert np.array_equal(saved.value.to_numpy()[finite], original[finite])
    assert saved.value.notna().all()
    repaired = saved.status == 'reconstructed'
    assert repaired.sum() == 8
    assert (saved.lower[repaired] <= saved.value[repaired]).all()
    assert (saved.upper[repaired] >= saved.value[repaired]).all()
    assert saved.lower[~repaired].isna().all()
    assert report['summary']['reconstructed_gaps'] == 1
    assert report['gaps'][0]['calibration_count'] >= 9
    assert all(n['reference_index'] < report['reference']['training_rows'] for n in report['gaps'][0]['neighbors'])
    assert json.loads((output / 'report.json').read_text()) == report
    assert 'application/json' in (output / 'report.html').read_text()


def test_boundary_and_adjacent_gaps_are_explicitly_unresolved(inputs, tmp_path):
    reference, query = inputs
    frame = read_series(query)
    frame.loc[:2, 'value'] = np.nan
    frame.loc[92:94, 'value'] = np.nan  # within 6 samples of the existing gap
    frame.to_csv(query, index=False)
    result = repair(reference, query, tmp_path / 'out')
    assert result['summary']['unresolved_gaps'] == 3
    assert all(g['reason'] for g in result['gaps'])
    saved = pd.read_csv(tmp_path / 'out/repaired.csv')
    assert saved.value.isna().sum() == frame.value.isna().sum()


def test_overlapping_history_and_mismatched_cadence_rejected(inputs, tmp_path):
    reference, query = inputs
    frame = read_series(query)
    frame.timestamp -= pd.Timedelta(days=100)
    frame.to_csv(query, index=False)
    with pytest.raises(ValueError, match='strictly after'):
        repair(reference, query, tmp_path / 'bad')
    frame.timestamp = pd.date_range('2021-01-01', periods=len(frame), freq='2h', tz='UTC')
    frame.to_csv(query, index=False)
    with pytest.raises(ValueError, match='same sampling cadence'):
        repair(reference, query, tmp_path / 'bad')


def test_inadequate_calibration_abstains_without_fake_intervals(inputs, tmp_path):
    reference, query = inputs
    result = repair(reference, query, tmp_path / 'out', RepairConfig(calibration_gaps=5))
    assert result['summary']['unresolved_gaps'] == 1
    assert result['gaps'][0]['quantile'] is None
    assert result['gaps'][0]['calibration_count'] == 5
    assert 'calibration' in result['gaps'][0]['reason']


def test_output_protection_and_named_overwrite_only(inputs, tmp_path):
    reference, query = inputs
    output = tmp_path / 'out'
    output.mkdir()
    (output / 'user-notes.txt').write_text('preserve me')
    with pytest.raises(ValueError, match='already exists'):
        repair(reference, query, output)
    repair(reference, query, output, overwrite=True)
    assert (output / 'user-notes.txt').read_text() == 'preserve me'
    with pytest.raises(ValueError, match='must not overwrite input'):
        repair(reference, output / 'repaired.csv', output, overwrite=True)


def test_self_contained_report_escapes_script_termination(inputs, tmp_path):
    reference, query = inputs
    report = repair(reference, query, tmp_path / 'out')
    report['input']['name'] = '</script><script>alert("bad")</script>'
    frame = read_series(query)
    frame['original_value'] = frame.value
    frame['lower'] = np.nan
    frame['upper'] = np.nan
    rendered = render_report(report, frame)
    assert '<script>alert(' not in rendered
    assert '\\u003c/script>' in rendered
    assert '<script src=' not in rendered


def test_cli_error_is_actionable_and_no_traceback(inputs, tmp_path):
    reference, query = inputs
    result = subprocess.run([sys.executable, '-m', 'gaplens.cli', 'repair', '--reference', str(reference),
                             '--input', str(query), '--output', str(tmp_path / 'out'), '--alpha', 'nan'],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert 'alpha' in result.stderr
    assert 'Traceback' not in result.stderr


def test_resource_and_config_validation():
    for config in (RepairConfig(neighbors=257), RepairConfig(max_gap=513), RepairConfig(context=0),
                   RepairConfig(calibration_fraction=1), RepairConfig(seed=-1)):
        with pytest.raises(ValueError):
            config.validate()


@pytest.mark.parametrize('method', ['linear', 'extra-trees'])
def test_baselines_complete_the_same_product_workflow(inputs, tmp_path, method):
    reference, query = inputs
    result = repair(reference, query, tmp_path / method, RepairConfig(method=method))
    assert result['summary']['reconstructed_samples'] == 8
    assert result['gaps'][0]['neighbors'] == []
    assert len(result['gaps'][0]['lower']) == 8


def test_too_short_reference_is_actionable(inputs, tmp_path):
    reference, query = inputs
    read_series(reference).iloc[:30].to_csv(reference, index=False)
    with pytest.raises(ValueError, match='too short'):
        repair(reference, query, tmp_path / 'out')


def test_too_long_gap_remains_missing(inputs, tmp_path):
    reference, query = inputs
    result = repair(reference, query, tmp_path / 'out', RepairConfig(max_gap=4))
    assert result['summary']['unresolved_gaps'] == 1
    assert 'exceeding max_gap' in result['gaps'][0]['reason']


def test_single_sample_gap_exports_real_nonzero_uncertainty(inputs, tmp_path):
    reference, query = inputs
    frame = read_series(query)
    # A one-sample missing block is a genuine supported product input.
    frame.value = frame.value.interpolate()
    frame.loc[80, 'value'] = np.nan
    frame.to_csv(query, index=False)
    result = repair(reference, query, tmp_path / 'singleton')
    gap = result['gaps'][0]
    assert gap['length'] == 1
    assert result['summary']['reconstructed_samples'] == 1
    assert gap['lower'][0] < gap['mean'][0] < gap['upper'][0]
    import re
    html = (tmp_path / 'singleton/report.html').read_text(encoding='utf-8')
    payload = json.loads(re.search(r'<script id="gaplens-data" type="application/json">(.*?)</script>', html).group(1))
    point = next(p for p in payload['views']['1'] if p['i'] == 80)
    assert point['lo'] == gap['lower'][0]
    assert point['hi'] == gap['upper'][0]
