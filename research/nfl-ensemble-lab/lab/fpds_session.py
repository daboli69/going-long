"""Local foreground supervisor; owns only its explicitly launched manual jobs."""
import argparse
import json
import os
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psutil

from .fpds_manual import jobs


def deadline_for(value, current=None):
    current = current or datetime.now().astimezone()
    hour, minute = map(int, value.split(':'))
    deadline = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if deadline <= current:
        raise ValueError('The requested local stop time has already passed')
    return deadline.astimezone(timezone.utc)


def terminate_owned(job):
    """Kill only a PID verified to be this job's worker and its descendants."""
    active = jobs.active()
    if not active or active.get('job') != job:
        return False
    try:
        parent = psutil.Process(active['pid'])
        if job not in parent.cmdline():
            return False
        children = parent.children(recursive=True)
        for process in reversed(children):
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
        psutil.wait_procs(children + [parent], timeout=5)
        jobs.state(jobs.directory(job), 'checkpoint', message='Local session hard deadline; completed blocks retained; unfinished fit discarded')
        return True
    except psutil.NoSuchProcess:
        return False


def supervise(path):
    config = json.loads((path / 'SESSION.json').read_text(encoding='utf-8'))
    deadline = datetime.fromisoformat(config['deadline_utc'])
    graceful = deadline - timedelta(minutes=10)
    own_job = None
    history = []

    def status(phase, **extra):
        jobs.atomic(path / 'STATUS.json', dict(phase=phase, updated_at=datetime.now(timezone.utc).isoformat(), supervisor_pid=os.getpid(), jobs=history, **extra))

    try:
        jobs.registered()
        if jobs.active():
            raise ValueError('Another manual job is active; no competing session started')
        for action in ('project', 'compare'):
            if datetime.now(timezone.utc) >= graceful - timedelta(minutes=15):
                break
            hours = min(6, (graceful - datetime.now(timezone.utc)).total_seconds() / 3600)
            own_job = jobs.launch(action, week=config['week'], scope='all', sims=config['sims'], seed=17,
                                  hours=min(2, hours) if action == 'project' else hours,
                                  refresh=(action == 'project'))
            history.append(dict(job=own_job, action=action))
            status('running', action=action, job=own_job)
            while True:
                current = datetime.now(timezone.utc)
                if current >= deadline:
                    killed = terminate_owned(own_job)
                    status('stopped_deadline', terminated_worker=killed)
                    return
                if current >= graceful:
                    jobs.stop(own_job)
                state = jobs.read(jobs.directory(own_job) / 'STATUS.json')
                active = jobs.active()
                if not active or active.get('job') != own_job:
                    phase = state.get('phase')
                    history[-1]['phase'] = phase
                    if phase == 'checkpoint' and current < graceful - timedelta(minutes=15):
                        hours = min(6, (graceful - current).total_seconds() / 3600)
                        jobs.launch('compare', resume=own_job, hours=hours)
                        status('running', action=action, job=own_job)
                        continue
                    if phase != 'complete':
                        status('stopped', message='Job failed or checkpointed; private diagnostics retained; no automatic retry')
                        return
                    break
                time.sleep(min(5, max(.05, (deadline - current).total_seconds())))
        status('complete', message='Requested fixed work completed or admission window ended; no redundant fitting')
    except Exception:
        (path / 'ERROR_PRIVATE.log').write_text(traceback.format_exc(), encoding='utf-8')
        # Do not orphan an owned worker on supervisor failure.
        if own_job:
            jobs.stop(own_job)
            terminate_owned(own_job)
        status('failed', message='Local supervisor stopped; private diagnostic retained')


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--session', required=True, type=Path)
    args = parser.parse_args()
    supervise(args.session)


if __name__ == '__main__':
    main()
