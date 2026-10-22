import json
import pytest
from lab.fpds_next.__main__ import preflight
from lab.fpds_next import run as X


def test_completed_resume_refuses_without_mutating_status(tmp_path):
    (tmp_path/'RUN.json').write_text('{}')
    (tmp_path/'SUMMARY.json').write_text('{}')
    state=tmp_path/'STATUS.json';state.write_text('{"phase":"complete"}')
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(SystemExit):preflight(tmp_path,'resume')
    assert before=={p.name:p.read_bytes() for p in tmp_path.iterdir()}


def test_existing_new_run_refuses_and_missing_resume_refuses(tmp_path):
    with pytest.raises(SystemExit):preflight(tmp_path,'research')
    with pytest.raises(SystemExit):preflight(tmp_path,'resume')


def test_prepared_snapshot_mutation_is_rejected_before_read_or_fit(tmp_path):
    file=tmp_path/'players.parquet';file.write_bytes(b'changed')
    (tmp_path/'PREPARED.json').write_text(json.dumps({'files':{'players.parquet':'wrong_hash'}}))
    with pytest.raises(ValueError,match='snapshot changed'):X.prepare(tmp_path,{})
