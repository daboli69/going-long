from datetime import datetime, timezone
from unittest.mock import patch, Mock

import pytest

from lab.fpds_session import deadline_for, terminate_owned


def test_local_deadline_to_utc():
    from datetime import timedelta
    eastern = timezone(timedelta(hours=-4))
    result = deadline_for('15:30', datetime(2026, 10, 21, 9, 20, tzinfo=eastern))
    assert result == datetime(2026, 10, 21, 19, 30, tzinfo=timezone.utc)


def test_past_deadline_rejected():
    with pytest.raises(ValueError, match='already passed'):
        deadline_for('15:30', datetime(2026, 10, 21, 16, tzinfo=timezone.utc))


def test_does_not_kill_unowned_job():
    with patch('lab.fpds_session.jobs.active', return_value={'job': 'other', 'pid': 1}), patch('lab.fpds_session.psutil.Process') as process:
        assert not terminate_owned('owned')
        process.assert_not_called()


def test_hard_stop_kills_verified_worker_and_children(tmp_path):
    parent, child = Mock(), Mock()
    parent.cmdline.return_value = ['python', '--job', 'owned']
    parent.children.return_value = [child]
    with patch('lab.fpds_session.jobs.active', return_value={'job': 'owned', 'pid': 1}), patch('lab.fpds_session.psutil.Process', return_value=parent), patch('lab.fpds_session.psutil.wait_procs'), patch('lab.fpds_session.jobs.directory', return_value=tmp_path), patch('lab.fpds_session.jobs.state') as state:
        assert terminate_owned('owned')
        child.kill.assert_called_once()
        parent.kill.assert_called_once()
        assert state.call_args.args[1] == 'checkpoint'
