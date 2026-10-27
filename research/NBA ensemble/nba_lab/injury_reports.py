"""Official NBA injury-report PDFs: one pregame report per game day, archived and parsed.

Each game day gets the latest official report whose own header time, URL slot and HTTP
Last-Modified are all at or before (first ET tipoff - lead). Raw PDFs are archived by
SHA256 with retrieval metadata. Rows carry the report's publication time as available_at.
Player names map to ESPN athlete_id only by exact normalized name; anything else is
reported as unmatched, never guessed. Nothing here feeds a model.

Run: python -m nba_lab.injury_reports collect --start 2022 --end 2026
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import re
import time
import unicodedata
from email.utils import parsedate_to_datetime
from pathlib import Path
import pandas as pd
import requests
from .config import CACHE,DATA,RAW,now,atomic

BASE='https://ak-static.cms.nba.com/referee/injury/'
ARCHIVE=RAW/'archive'/'injury_pdf'
MANIFEST=ARCHIVE/'MANIFEST.json'
OUTPUT=CACHE/'injury_reports.parquet'
AUDIT=DATA/'INJURY_REPORTS_AUDIT.json'
ET='America/New_York'
# Filenames moved from hourly "_05PM" to quarter-hour "_05_00PM" on this ET date (probed 2026-10-23).
QUARTER_HOUR_FROM=pd.Timestamp('2025-12-22')
STATUSES=('Out','Doubtful','Questionable','Probable','Available')
NYS='NOT YET SUBMITTED'
COLUMNS=('game_date','game_time','matchup','team','player','status','reason')
SUFFIXES={'jr','sr','ii','iii','iv','v'}


# ---------- URL slots ----------

def slot_url(slot):
    """URL for a report slot (tz-aware ET timestamp)."""
    stem=slot.strftime('%Y-%m-%d_%I')
    if slot.tz_localize(None).normalize()>=QUARTER_HOUR_FROM:stem+=slot.strftime('_%M')
    return BASE+f'Injury-Report_{stem}{slot.strftime("%p")}.pdf'


def candidate_slots(cutoff,hours_back=14):
    """Slots at or before cutoff on the same ET date, latest first."""
    cutoff=pd.Timestamp(cutoff).tz_convert(ET);day=cutoff.normalize()
    step=pd.Timedelta(minutes=15) if cutoff.tz_localize(None).normalize()>=QUARTER_HOUR_FROM else pd.Timedelta(hours=1)
    slot=cutoff.floor(step);out=[]
    while slot>=day and slot>=cutoff-pd.Timedelta(hours=hours_back):out.append(slot);slot-=step
    return out


# ---------- PDF parsing ----------

def _lines(words,tolerance=1.5):
    lines=[]
    for w in sorted(words,key=lambda w:(w['top'],w['x0'])):
        if lines and abs(lines[-1][0]-w['top'])<=tolerance:lines[-1][1].append(w)
        else:lines.append([w['top'],[w]])
    return [(top,sorted(ws,key=lambda w:w['x0'])) for top,ws in lines]


def _header(lines):
    for i,(top,ws) in enumerate(lines):
        text=[w['text'] for w in ws]
        if 'Matchup' in text and 'Reason' in text:
            games=[w['x0'] for w in ws if w['text']=='Game']
            find=lambda name:next(w['x0'] for w in ws if w['text']==name)
            if len(games)<2:raise ValueError('Unrecognized injury-report header')
            return i,[games[0],games[1],find('Matchup'),find('Team'),find('Player'),find('Current'),find('Reason')]
    return None,None


def report_time(text):
    match=re.search(r'Injury Report:\s*(\d{2}/\d{2}/\d{2})\s+(\d{1,2}:\d{2})\s*(AM|PM)',text)
    if not match:raise ValueError('Injury-report header time not found')
    return pd.Timestamp(pd.to_datetime(' '.join(match.groups()),format='%m/%d/%y %I:%M %p')).tz_localize(ET)


def parse_pages(pages):
    """pages: list of word lists (pdfplumber extract_words dicts with x0/top/text).

    Returns (report_time, rows, issues). Rows inherit date/time/matchup/team from the
    row above, as the PDF leaves those cells blank. Wrapped cells attach to the nearest
    anchor row (a row with a status or NOT YET SUBMITTED); a fragment above the first
    anchor on a page continues the last row of the previous page."""
    issues=[];rows=[];bounds=None;stamp=None;state=dict.fromkeys(COLUMNS[:4])
    for number,words in enumerate(pages,1):
        lines=_lines(words)
        title=[i for i,(top,ws) in enumerate(lines) if ws[0]['text']=='Injury' and len(ws)>1 and ws[1]['text']=='Report:']
        if title:
            text=' '.join(w['text'] for w in lines[title[0]][1])
            page_time=report_time(text);stamp=stamp or page_time
            if page_time!=stamp:issues.append({'page':number,'issue':'header time differs between pages'})
        h,found=_header(lines)
        if found:bounds=found
        if bounds is None:raise ValueError('No column header before first data page')
        body=[(top,ws) for i,(top,ws) in enumerate(lines) if i not in title and i!=h
              and not re.fullmatch(r'Page\s*\d+\s*of\s*\d+',' '.join(w['text'] for w in ws))]
        cells=[]
        for top,ws in body:
            parts=['']*7
            for w in ws:
                col=max(i for i,x in enumerate(bounds) if w['x0']>=x-3) if w['x0']>=bounds[0]-3 else 0
                parts[col]=(parts[col]+' '+w['text']).strip()
            cells.append((top,parts))
        anchors=[i for i,(top,p) in enumerate(cells) if p[5] in STATUSES or NYS in ' '.join(p)]
        if not anchors:
            if cells:issues.append({'page':number,'issue':'page without status rows','text':' | '.join(' '.join(p) for _,p in cells)[:200]})
            continue
        tops=[cells[i][0] for i in anchors]
        gaps=sorted(b-a for a,b in zip(tops,tops[1:]))
        gap=gaps[len(gaps)//2] if gaps else 22
        attached={i:[] for i in anchors};carry=[]
        for i,(top,parts) in enumerate(cells):
            if i in attached:continue
            near=sorted(anchors,key=lambda a:abs(cells[a][0]-top));nearest=near[0]
            first=abs(cells[nearest][0]-top);second=abs(cells[near[1]][0]-top) if len(near)>1 else float('inf')
            # Two-line cells sit about gap/3 from their row, three-line cells about 2*gap/3.
            # Beyond that, or without a clearly nearest row, the fragment is not attached.
            if first<.75*gap and (first<gap/2+.5 or second-first>4):attached[nearest].append((top,parts))
            elif top<tops[0]:carry.append(parts)
            else:issues.append({'page':number,'issue':'unattached fragment','text':' '.join(p for p in parts if p)})
        if carry:
            if not rows:issues.append({'page':number,'issue':'continuation before first row'})
            else:
                for parts in carry:
                    for col,key in ((4,'player_name_raw'),(6,'reason')):
                        if parts[col]:rows[-1][key]=((rows[-1][key] or '')+' '+parts[col]).strip()
                    if any(parts[c] for c in (0,1,2,3,5)):issues.append({'page':number,'issue':'continuation outside player/reason','text':' '.join(parts)})
        for i in anchors:
            merged=[]
            for col in range(7):
                pieces=sorted([(cells[i][0],cells[i][1][col])]+[(t,p[col]) for t,p in attached[i]])
                merged.append(' '.join(p for _,p in pieces if p).strip())
            if merged[2] and not merged[3]:issues.append({'page':number,'issue':'matchup without team','text':' '.join(merged)})
            if merged[0]:state['game_date']=merged[0]
            if merged[1]:state['game_time']=merged[1]
            if merged[2]:state['matchup']=merged[2];state['team']=None
            if merged[3]:state['team']=merged[3]
            nys=NYS in ' '.join(merged)
            rows.append({**state,'player_name_raw':None if nys else merged[4] or None,
                         'status':NYS if nys else merged[5],'reason':None if nys else merged[6] or None,'not_yet_submitted':nys,'page':number})
    if stamp is None:raise ValueError('Report header time not found')
    for r in rows:
        if not all(r[k] for k in ('game_date','game_time','matchup','team')):issues.append({'issue':'row missing game/team context','text':str(r)[:200]})
        if not r['not_yet_submitted'] and not r['player_name_raw']:issues.append({'issue':'status row without player','text':str(r)[:200]})
    return stamp,rows,issues


def parse_pdf(source):
    import pdfplumber
    handle=io.BytesIO(source) if isinstance(source,(bytes,bytearray)) else source
    with pdfplumber.open(handle) as pdf:
        pages=[p.extract_words(x_tolerance=1.0) for p in pdf.pages]
    return parse_pages(pages)


# ---------- archive / download ----------

def _manifest():
    return json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.exists() else {}


def fetch(url,manifest,session,pause=.25):
    """Archived PDF bytes for url, or None when the slot does not exist (HTTP 403/404).
    Historical misses are remembered so they are not requested again."""
    prior=manifest.get(url)
    if prior:
        if prior['status']!=200:return None,prior
        return Path(prior['path']).read_bytes(),prior
    time.sleep(pause)
    response=session.get(url,timeout=(10,35),headers={'User-Agent':'NBA-Ensemble-Local-Research/1.0'})
    retrieved=now()
    if response.status_code in (403,404):
        manifest[url]={'status':response.status_code,'retrieved_at':retrieved};return None,manifest[url]
    response.raise_for_status();body=response.content
    if not body.startswith(b'%PDF'):raise ValueError('Not a PDF: '+url)
    if len(body)>10_000_000:raise ValueError('PDF exceeds bounded size: '+url)
    checksum=hashlib.sha256(body).hexdigest();name=url.rsplit('/',1)[1]
    directory=ARCHIVE/name[14:24];directory.mkdir(parents=True,exist_ok=True)
    path=directory/(name[:-4]+'_'+checksum[:16]+'.pdf')
    if not path.exists():
        with path.open('xb') as f:f.write(body)
    modified=response.headers.get('Last-Modified')
    manifest[url]={'status':200,'retrieved_at':retrieved,'sha256':checksum,'bytes':len(body),'path':str(path),
                   'last_modified':parsedate_to_datetime(modified).isoformat() if modified else None}
    return body,manifest[url]


def pregame_report(day,first_tipoff,manifest,session,lead_hours=1.0):
    """Latest report for one ET game day with every timestamp <= first tipoff - lead."""
    cutoff=pd.Timestamp(first_tipoff).tz_convert(ET)-pd.Timedelta(hours=lead_hours);tried=0
    for slot in candidate_slots(cutoff):
        url=slot_url(slot);body,meta=fetch(url,manifest,session);tried+=1
        if body is None:continue
        stamp,rows,issues=parse_pdf(body)
        modified=pd.Timestamp(meta['last_modified']).tz_convert(ET) if meta.get('last_modified') else None
        published=max(t for t in (stamp,slot,modified) if t is not None)
        if published>cutoff:continue
        return {'day':day,'url':url,'slot':slot,'report_time':stamp,'last_modified':modified,'available_at':published.tz_convert('UTC'),
                'cutoff':cutoff,'first_tipoff':pd.Timestamp(first_tipoff),'sha256':meta['sha256'],'retrieved_at':meta['retrieved_at'],
                'tried':tried,'rows':rows,'issues':issues}
    return {'day':day,'url':None,'cutoff':cutoff,'first_tipoff':pd.Timestamp(first_tipoff),'tried':tried,'rows':[],'issues':[]}


# ---------- identity mapping ----------

def normalize_name(name,strip_suffix=False):
    text=unicodedata.normalize('NFKD',str(name)).encode('ascii','ignore').decode().lower()
    # Periods join initials ("O.G." == "OG"); hyphens/apostrophes split words on both sides.
    tokens=re.sub(r"[^a-z0-9 ]",'',re.sub(r"[\-']",' ',text.replace('.',''))).split()
    if strip_suffix:tokens=[t for t in tokens if t not in SUFFIXES]
    return ' '.join(tokens)


def display_name(raw):
    """'Moore Jr., Wendell' -> 'Wendell Moore Jr.'; names without a comma are kept."""
    if not raw:return None
    last,sep,first=str(raw).partition(',')
    return (first.strip()+' '+last.strip()).strip() if sep else str(raw).strip()


def team_ids(players):
    names=players[['team_id','team_display_name']].dropna().drop_duplicates()
    out={}
    for team_id,name in names.itertuples(index=False):
        key=normalize_name(name)
        if out.get(key,team_id)!=team_id:raise ValueError('Team name maps to two ESPN ids: '+name)
        out[key]=team_id
    return out


def map_rows(frame,games,players):
    """Adds team_id, game_id, athlete_id and match_method. Exact normalized names only, at the
    first level with any candidate: team-season, team-season without suffix, same team in any
    season (players absent all season have no box that year), any team this season (e.g. just
    traded), any team any season. More than one athlete_id at that level -> ambiguous, unmatched."""
    d=frame.copy();teams=team_ids(players)
    d['team_id']=d.team.map(lambda t:teams.get(normalize_name(t)) if t else None)
    g=games[games.season.isin(d.season.unique())].copy();g['et_date']=g.tipoff.dt.tz_convert(ET).dt.strftime('%m/%d/%Y')
    side=pd.concat([g[['game_id','et_date']].assign(team_id=g.home_id),g[['game_id','et_date']].assign(team_id=g.away_id)])
    if side.duplicated(['et_date','team_id']).any():raise ValueError('Team plays twice on one ET date')
    d=d.merge(side.rename(columns={'et_date':'game_date'}),on=['game_date','team_id'],how='left',validate='many_to_one')
    p=players[['season','team_id','athlete_id','athlete_display_name']].dropna().drop_duplicates()
    p=p.assign(full=p.athlete_display_name.map(normalize_name),bare=p.athlete_display_name.map(lambda n:normalize_name(n,True)))
    index={}
    for key,col,scope in (('team_exact','full',['season','team_id']),('team_suffix','bare',['season','team_id']),
                          ('team_other_season','full',['team_id']),('season_exact','full',['season']),('any_exact','full',[])):
        ids=p.groupby(scope+[col]).athlete_id.agg(lambda s:tuple(sorted(set(s))))
        index[key]={k if isinstance(k,tuple) else (k,):v for k,v in ids.items()}
    athlete=[];method=[]
    for r in d.itertuples(index=False):
        if r.not_yet_submitted or not r.player_name:athlete.append(None);method.append(None);continue
        full,bare=normalize_name(r.player_name),normalize_name(r.player_name,True);found=None
        for key,lookup in (('team_exact',(r.season,r.team_id,full)),('team_suffix',(r.season,r.team_id,bare)),
                           ('team_other_season',(r.team_id,full)),('season_exact',(r.season,full)),('any_exact',(full,))):
            ids=index[key].get(lookup)
            if ids and len(ids)==1:found=(ids[0],key);break
            if ids:found=(None,'ambiguous_'+key);break
        athlete.append(found[0] if found else None);method.append(found[1] if found else 'unmatched')
    d['athlete_id']=athlete;d['match_method']=method
    return d


# ---------- collection ----------

def game_days(games,start,end):
    g=games[games.season.between(start,end)].copy()
    g['day']=g.tipoff.dt.tz_convert(ET).dt.strftime('%Y-%m-%d')
    return g.groupby(['season','day']).tipoff.min().reset_index()


def collect(start=2022,end=2026,lead_hours=1.0,log=print,session=None):
    games=pd.read_parquet(CACHE/'games.parquet');players=pd.read_parquet(CACHE/'player_boxes.parquet')
    manifest=_manifest();session=session or requests.Session();ARCHIVE.mkdir(parents=True,exist_ok=True)
    reports=[];frames=[];errors=[]
    days=game_days(games,start,end)
    for n,(season,day,tip) in enumerate(days.itertuples(index=False),1):
        try:report=pregame_report(day,tip,manifest,session,lead_hours)
        except Exception as error:
            errors.append({'day':day,'error':type(error).__name__,'message':str(error)[:200]});log(errors[-1]);continue
        finally:
            if n%25==0:atomic(MANIFEST,manifest)
        report['season']=season;reports.append(report)
        if report['rows']:
            frames.append(pd.DataFrame(report['rows']).assign(season=season,report_day=day,report_url=report['url'],report_sha256=report['sha256'],
                report_time=report['report_time'].tz_convert('UTC'),available_at=report['available_at']))
        if n%25==0:log(f'{n}/{len(days)} days; latest {day}: {len(report["rows"])} rows')
    atomic(MANIFEST,manifest)
    rows=pd.concat(frames,ignore_index=True)
    # Reports also preview the next day's games; each game keeps rows from its own day's report.
    same_day=rows.game_date.eq(pd.to_datetime(rows.report_day).dt.strftime('%m/%d/%Y'))
    other_day=int((~same_day).sum());rows=rows[same_day].reset_index(drop=True)
    rows['player_name']=rows.player_name_raw.map(display_name)
    rows=map_rows(rows,games,players)
    rows['retrieved_at']=rows.report_url.map(lambda u:manifest[u]['retrieved_at'])
    rows.to_parquet(OUTPUT,index=False)
    audit=coverage(rows,reports,errors,games,start,end,lead_hours);audit['other_day_rows_dropped']=other_day
    atomic(AUDIT,audit);return audit


def coverage(rows,reports,errors,games,start,end,lead_hours):
    per=[];r=pd.DataFrame([{k:v for k,v in x.items() if k not in ('rows','issues')} for x in reports])
    for season in range(start,end+1):
        g=games[games.season.eq(season)];days=r[r.season.eq(season)] if len(r) else r
        s=rows[rows.season.eq(season)];players=s[~s.not_yet_submitted]
        found=days[days.url.notna()]
        lag=(found.cutoff-found.slot).dt.total_seconds()/60 if len(found) else pd.Series(dtype=float)
        teams_reported=s.dropna(subset=['game_id']).groupby('game_id').team_id.nunique()
        per.append({'season':season,'label':f'{season-1}-{str(season)[-2:]}','games':len(g),
            'game_days':len(days),'days_with_report':len(found),'days_missing_report':int(days.url.isna().sum()),
            'games_on_report_days':int(g.game_id.isin(s.game_id).sum()) if len(s) else 0,
            'games_with_both_teams_listed':int(teams_reported.eq(2).sum()),
            'rows':len(s),'player_rows':len(players),'not_yet_submitted_rows':int(s.not_yet_submitted.sum()),
            'rows_without_game_id':int(s.game_id.isna().sum()),'rows_without_team_id':int(s.team_id.isna().sum()),
            'status_counts':players.status.value_counts().to_dict(),
            'athlete_match':players.match_method.value_counts().to_dict(),
            'unmatched_player_rows':int(players.athlete_id.isna().sum()),
            'unmatched_out_rows':int((players.athlete_id.isna()&players.status.eq('Out')).sum()),
            'unmatched_by_reason':players[players.athlete_id.isna()].reason.fillna('').str.split(' - ').str[0].value_counts().to_dict(),
            'minutes_report_before_cutoff_median':float(lag.median()) if len(lag) else None,
            'available_at_before_every_tipoff':bool((s.dropna(subset=['game_id']).merge(g[['game_id','tipoff']],on='game_id').pipe(lambda x:(x.available_at<x.tipoff).all())) if len(s) else None)})
    players=rows[~rows.not_yet_submitted]
    unmatched=players[players.athlete_id.isna()]
    names=unmatched.groupby(['season','team','player_name','match_method']).size().sort_values(ascending=False).reset_index(name='rows')
    issues=[{'day':x['day'],**i} for x in reports for i in x['issues']]
    return {'created_at':now(),'lead_hours':lead_hours,
        'rule':'One report per ET game day: latest official PDF whose header time, URL slot and HTTP Last-Modified are all <= first tipoff - lead. available_at = max of those three.',
        'limits':['Later games on a day use the same early report, so late scratches are not visible.',
                  'Regular season only (games.parquet). Play-in and playoffs are not collected.',
                  'Historical retrieval is recent; publication time is the PDF header/slot/Last-Modified, not our own observation.',
                  'Identity mapping uses ESPN box names from the whole season, including later games; it is identity resolution, not a feature value.',
                  'Unmatched rows (mostly two-way/G League players without box appearances or name variants) are left unmapped.'],
        'seasons':per,'download_errors':errors,'parse_issues':issues[:500],'parse_issue_count':len(issues),
        'unmatched_names':names.head(300).to_dict('records'),'unmatched_name_count':len(names),'model_input':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['collect']);parser.add_argument('--start',type=int,default=2022)
    parser.add_argument('--end',type=int,default=2026);parser.add_argument('--lead-hours',type=float,default=1.0)
    args=parser.parse_args()
    audit=collect(args.start,args.end,args.lead_hours)
    print(json.dumps({'seasons':audit['seasons'],'download_errors':len(audit['download_errors']),'parse_issue_count':audit['parse_issue_count'],
                      'unmatched_name_count':audit['unmatched_name_count']},indent=2,default=str))


if __name__=='__main__':main()


# ---------- every version ----------

VERSIONS=CACHE/'injury_report_versions.parquet'


def day_slots(first_tipoff,last_tipoff,from_hour=9):
    """Every published slot from from_hour ET through the day's last tipoff."""
    start=pd.Timestamp(first_tipoff).tz_convert(ET).normalize()+pd.Timedelta(hours=from_hour)
    end=pd.Timestamp(last_tipoff).tz_convert(ET)
    step=pd.Timedelta(minutes=15) if start.tz_localize(None).normalize()>=QUARTER_HOUR_FROM else pd.Timedelta(hours=1)
    slot=start;out=[]
    while slot<=end:out.append(slot);slot+=step
    return out


def collect_versions(start=2022,end=2026,workers=4,log=print):
    """Download and parse every report version per game day. Rows keep their own game date only."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    games=pd.read_parquet(CACHE/'games.parquet');players=pd.read_parquet(CACHE/'player_boxes.parquet')
    g=games[games.season.between(start,end)].copy();g['day']=g.tipoff.dt.tz_convert(ET).dt.strftime('%Y-%m-%d')
    days=g.groupby(['season','day']).tipoff.agg(['min','max']).reset_index()
    manifest=_manifest();lock=threading.Lock();local=threading.local();ARCHIVE.mkdir(parents=True,exist_ok=True)
    jobs=[(r.season,r.day,slot) for r in days.itertuples() for slot in day_slots(r.min,r.max)]
    log(f'{len(jobs)} slots over {len(days)} game days')
    def one(job):
        season,day,slot=job
        if not hasattr(local,'session'):local.session=requests.Session()
        url=slot_url(slot)
        with lock:prior=manifest.get(url)
        if prior is None:
            scratch={}
            body,meta=fetch(url,scratch,local.session)
            with lock:manifest.update(scratch)
        else:
            body=Path(prior['path']).read_bytes() if prior['status']==200 else None;meta=prior
        if body is None:return None
        stamp,rows,issues=parse_pdf(body)
        modified=pd.Timestamp(meta['last_modified']).tz_convert(ET) if meta.get('last_modified') else None
        published=max(t for t in (stamp,slot,modified) if t is not None)
        frame=pd.DataFrame(rows)
        if frame.empty:return None
        frame=frame[frame.game_date.eq(pd.Timestamp(day).strftime('%m/%d/%Y'))]
        return frame.assign(season=season,report_day=day,report_url=url,report_sha256=meta['sha256'],
                            published_at=published.tz_convert('UTC'),parse_issues=len(issues))
    frames=[];done=0
    with ThreadPoolExecutor(workers) as pool:
        for frame in pool.map(one,jobs):
            done+=1
            if frame is not None and len(frame):frames.append(frame)
            if done%500==0:
                with lock:atomic(MANIFEST,manifest)
                log(f'{done}/{len(jobs)} slots, {len(frames)} versions with rows')
    atomic(MANIFEST,manifest)
    rows=pd.concat(frames,ignore_index=True);rows['player_name']=rows.player_name_raw.map(display_name)
    rows=map_rows(rows,games,players);rows.to_parquet(VERSIONS,index=False)
    summary={'created_at':now(),'slots_tried':len(jobs),'versions':int(rows.report_url.nunique()),'rows':len(rows),
             'days':int(rows.report_day.nunique()),'unmatched_player_rows':int((rows.athlete_id.isna()&~rows.not_yet_submitted).sum())}
    atomic(DATA/'INJURY_REPORT_VERSIONS.json',summary);return summary
