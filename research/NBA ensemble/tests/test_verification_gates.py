"""Verification steps must fail when they compare nothing or compare mismatched sets."""
import subprocess
import sys
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / 'nba_xgb' / 'independent_eval.py'
ARCHIVE = ROOT / 'data' / 'raw' / 'archive'
pytestmark = pytest.mark.skipif(not (ARCHIVE / 'schedule_2025').exists(), reason='raw archive not present')


def run_eval(tmp_path, frame):
    f = tmp_path / 'p.csv'
    frame.to_csv(f, index=False)
    return subprocess.run([sys.executable, str(EVAL), str(f), '--archive', str(ARCHIVE), '--pairs', 'a:b'],
                          capture_output=True, text=True, cwd=ROOT)


def frame(ids, models=('a', 'b')):
    rows = []
    for m in models:
        rows.append(pd.DataFrame({'game_id': ids, 'season': 2025, 'game_date': '2025-01-01',
                                  'prediction_cutoff_utc': '2025-01-01T10:00:00+00:00', 'model': m,
                                  'p_home_raw': 0.6, 'p_home': 0.6}))
    return pd.concat(rows, ignore_index=True)


def test_unmatched_game_ids_fail(tmp_path):
    r = run_eval(tmp_path, frame(['999999999', '999999998']))
    assert r.returncode != 0 and 'AssertionError' in r.stderr


def test_models_with_different_game_sets_fail(tmp_path):
    sched = pd.read_parquet(sorted((ARCHIVE / 'schedule_2025').glob('*.parquet'))[-1])
    ids = sched[sched.season_type.eq(2) & sched.status_type_completed.eq(True)].game_id.astype(str).head(6).tolist()
    f = pd.concat([frame(ids, ('a',)), frame(ids[:4], ('b',))], ignore_index=True)
    r = run_eval(tmp_path, f)
    assert r.returncode != 0 and 'AssertionError' in r.stderr


def test_valid_input_passes(tmp_path):
    sched = pd.read_parquet(sorted((ARCHIVE / 'schedule_2025').glob('*.parquet'))[-1])
    ids = sched[sched.season_type.eq(2) & sched.status_type_completed.eq(True)].game_id.astype(str).head(6).tolist()
    r = run_eval(tmp_path, frame(ids))
    assert r.returncode == 0, r.stderr[-400:]
