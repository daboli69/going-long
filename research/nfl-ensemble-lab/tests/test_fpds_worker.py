"""Retry metadata writes, never fit or rerun a configuration."""
import pytest
from lab.fpds_worker import retry_atomic


def test_transient_pointer_permission_retry_preserves_value(tmp_path):
    calls=[];pauses=[];payload={'configuration':'synthetic','completed_blocks':3}
    def operation(path,value):
        calls.append((path,value.copy()))
        if len(calls)<3:raise PermissionError('synthetic file lock')
        return 'saved'
    assert retry_atomic(operation,tmp_path/'LEDGER.json',payload,sleep=pauses.append)=='saved'
    assert len(calls)==3 and all(value==payload for _,value in calls) and pauses==[.1,.2]


def test_persistent_lock_and_other_errors_fail_closed(tmp_path):
    calls=[]
    def locked(*a):calls.append(1);raise PermissionError('synthetic lock')
    with pytest.raises(PermissionError):retry_atomic(locked,tmp_path/'LEDGER.json',{},sleep=lambda _:None,retries=3)
    assert len(calls)==3
    def invalid(*a):raise ValueError('not a file-lock failure')
    with pytest.raises(ValueError):retry_atomic(invalid,tmp_path/'LEDGER.json',{},sleep=lambda _:pytest.fail('Unexpected retry'))
