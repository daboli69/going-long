"""Bridge to Codex's installed research package. Runs it as a subprocess in its own venv; never imports it.

The package under updates/ stays byte-identical (verified against BUNDLE_CONTENTS.json). Its outputs go to
new, timestamped paths in its own .cache folder. KOTC stays blocked research-only; the FGA candidate stays inactive.
"""
import hashlib
import json
import subprocess
from pathlib import Path
import pandas as pd
from .config import ROOT,stamp

PACKAGE=ROOT/'updates'/'2026-10-27-dca2756e533d'
PYTHON=PACKAGE/'.venv-research'/'Scripts'/'python.exe'
MANIFEST_SHA256='dca2756e533d0d3d3e4e6103ad2ea44eeb04d27dca41e6021742a8931479e222'
WINNERS=PACKAGE/'.cache'/'nba-winners';KOTC=PACKAGE/'.cache'/'king-court'
# Codex canonical codes -> this app's ESPN abbreviations.
TEAMS={'GSW':'GS','SAS':'SA','NYK':'NY','NOP':'NO','UTA':'UTAH','WAS':'WSH'}
VOTERS={'elo':'Elo','logistic':'Logistic','gradient_boosting':'Gradient boosting','random_forest':'Random forest',
        'naive_bayes':'Naive Bayes','ridge_margin':'Ridge margin'}
# The winner CLI locks ending-year 2026 (its registered holdout), so live training uses the other seasons.
FORECAST_SEASONS=('2023','2024','2025','2027')


def verify():
    """Manifest hash plus every payload file's SHA256."""
    manifest=PACKAGE/'BUNDLE_CONTENTS.json'
    if not manifest.exists():return {'installed':False,'problems':['package folder missing']}
    problems=[]
    if hashlib.sha256(manifest.read_bytes()).hexdigest()!=MANIFEST_SHA256:problems.append('BUNDLE_CONTENTS.json hash differs from the install receipt')
    files=json.loads(manifest.read_text(encoding='utf-8'))['files']
    for f in files:
        p=PACKAGE/f['path']
        if not p.exists():problems.append('missing '+f['path'])
        elif hashlib.sha256(p.read_bytes()).hexdigest()!=f['sha256']:problems.append('changed '+f['path'])
    return {'installed':True,'files':len(files),'problems':problems,'environment':PYTHON.exists()}


def run(*args,timeout=900):
    if not PYTHON.exists():raise FileNotFoundError('Research environment missing: create updates\\...\\.venv-research (see docs/CODEX_INTEGRATION.md)')
    result=subprocess.run([str(PYTHON),*args],cwd=PACKAGE,capture_output=True,text=True,timeout=timeout)
    if result.returncode:raise RuntimeError((result.stderr or result.stdout).strip().splitlines()[-1][:400])
    return result.stdout


def tests():
    result=subprocess.run([str(PYTHON),'-m','unittest','tests.test_nba_winners','tests.test_king_court','tests.test_king_court_diagnostics'],
                          cwd=PACKAGE,capture_output=True,text=True,timeout=900)
    tail=result.stderr.strip().splitlines()
    return {'passed':result.returncode==0,'summary':' '.join(tail[-3:])}


def forecast():
    """Fresh schedule fetch, then the frozen predict command. Returns the new predictions path."""
    version=stamp();source=WINNERS/f'fresh-{version}.json';output=WINNERS/f'predictions-{version}.json'
    run('-m','scripts.nba_winners','fetch','--seasons',*FORECAST_SEASONS,'--cache','.cache/nba-winners/raw','--output',str(source.relative_to(PACKAGE)))
    run('-m','scripts.nba_winners','predict','--input',str(source.relative_to(PACKAGE)),'--output',str(output.relative_to(PACKAGE)))
    return output


def saved(date):
    """Latest Codex forecast per game for this Eastern date, in the Today board's shape."""
    rows=[]
    for path in sorted(WINNERS.glob('predictions-*.json')):
        report=json.loads(path.read_text(encoding='utf-8'))
        for p in report.get('predictions',[]):
            tip=pd.Timestamp(p['tipoff'])
            if tip.tz_convert('America/New_York').date()!=pd.Timestamp(date).date():continue
            rows.append({'game_id':p['game_id'].removeprefix('espn:'),'tipoff':tip,'home':TEAMS.get(p['home'],p['home']),
                         'away':TEAMS.get(p['away'],p['away']),'p_home':p['home_probability'],'created_at':report['origin'],
                         **{name:v['home_probability'] for name,v in p['models'].items()},'codex_flags':', '.join(p['flags'])})
    if not rows:return pd.DataFrame()
    return pd.DataFrame(rows).sort_values('created_at').drop_duplicates('game_id',keep='last')


def latest_status():
    """Most recent predict run: how many games it forecast and why others were excluded."""
    paths=sorted(WINNERS.glob('predictions-*.json'))
    if not paths:return None
    report=json.loads(paths[-1].read_text(encoding='utf-8'))
    return {'origin':report['origin'],'forecasts':len(report.get('predictions',[])),'excluded':report.get('excluded',{}),
            'training_games':report.get('training_games')}


def development():
    """Latest development replay metrics, if one has been run locally."""
    paths=sorted(WINNERS.glob('new-development-*.json'))
    if not paths:return None
    report=json.loads(paths[-1].read_text(encoding='utf-8'))['report']
    return pd.DataFrame([{'model':k,'n':v['n'],'brier':v['brier'],'log_loss':v['log_loss'],'accuracy':v['accuracy']}
                         for k,v in report['metrics'].items()])


def kotc_audit():
    paths=sorted(KOTC.glob('new-audit-*.json'))
    return json.loads(paths[-1].read_text(encoding='utf-8')) if paths else None
