"""Describe genuinely archived pregame forecasts; never fit or select a model."""
import hashlib
import pandas as pd
from .config import CACHE,ARCHIVES,REPORTS,read,once,atomic,now
from .models import scores


def score(asof=None):
    time=pd.Timestamp(asof or pd.Timestamp.now(tz='UTC'))
    path=CACHE/'games.parquet'
    if not path.exists():raise ValueError('Refresh NBA results first')
    games=pd.read_parquet(path)
    ready=games[games.completed & (pd.to_datetime(games.tipoff,utc=True)+pd.Timedelta(hours=24)).lt(time)]
    ready=ready.set_index('game_id');records=[];pending=0
    for meta_path in sorted((ARCHIVES/'forecasts').glob('*/META.json')):
        meta=read(meta_path);directory=meta_path.parent
        forecasts=pd.read_parquet(directory/'predictions.parquet')
        for row in forecasts.to_dict('records'):
            game_id=str(row['game_id']);tipoff=pd.Timestamp(row['tipoff']);created=pd.Timestamp(row['created_at'])
            if created>=tipoff:raise ValueError('Archive contains a non-pregame forecast')
            for key in ('training_outcomes_available_through','calibration_outcomes_available_through'):
                if pd.Timestamp(row[key])>=created:raise ValueError('Archive training cutoff is not pre-forecast')
            if game_id not in ready.index:pending+=1;continue
            actual=ready.loc[game_id]
            if isinstance(actual,pd.DataFrame):raise ValueError('Duplicate final game IDs')
            if actual.home!=row['home'] or actual.away!=row['away'] or pd.Timestamp(actual.tipoff)!=tipoff:
                raise ValueError('Archive and final schedule identity mismatch')
            name=hashlib.sha256(game_id.encode()).hexdigest()[:24]+'.json'
            destination=directory/'scored'/name
            if destination.exists():record=read(destination)
            else:
                record={'game_id':game_id,'archive':directory.name,'created_at':row['created_at'],
                        'scored_at':now(),'p_home':float(row['p_home']),
                        'home_win':int(actual.home_score>actual.away_score),'model_version':row['model_version'],
                        'config_hash':row['config_hash'],'status':'Descriptive only; no model decisions or tuning.'}
                once(destination,record)
            records.append(record)
    # Multiple revisions of one game must not inflate the prospective sample size.
    if records:
        data=pd.DataFrame(records).sort_values(['created_at','archive']).drop_duplicates('game_id',keep='first')
        metrics=scores(data.home_win,data.p_home)
    else:metrics={'n':0}
    result={'updated_at':now(),'metrics':metrics,'scored_revision_rows':len(records),'pending_revision_rows':pending,
            'rule':'Earliest saved pregame revision per game; results eligible only after tipoff+24h.',
            'status':'Descriptive prospective tracking only; no tuning or promotion.'}
    atomic(REPORTS/'PROSPECTIVE.json',result);return result
