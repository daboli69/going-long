"""Descriptive scoring of actual pregame shadows only; never tune/select models."""
import hashlib
import numpy as np
import pandas as pd
from .config import CACHE,ARCHIVES,REPORTS,now,read,once
from .models import scores
from .research_io import update


def score(asof=None):
    time=pd.Timestamp(asof or pd.Timestamp.now(tz='UTC'))
    games=pd.read_parquet(CACHE/'games.parquet')
    ready=games[games.completed&(games.tipoff+pd.Timedelta(hours=24)).lt(time)].set_index('game_id')
    records=[];pending=0
    for kind,folder in [('individual','individual_forecasts'),('scores','score_forecasts')]:
        for meta in sorted((ARCHIVES/folder).glob('*/META.json')):
            for row in pd.read_parquet(meta.parent/'predictions.parquet').to_dict('records'):
                created=pd.Timestamp(row['created_at']);tipoff=pd.Timestamp(row['tipoff'])
                if created>=tipoff:raise ValueError('Non-pregame shadow archive cannot be scored')
                if pd.Timestamp(row['training_available_through'])>=created or pd.Timestamp(row['calibration_available_through'])>=created:
                    raise ValueError('Shadow training outcomes are not pre-forecast')
                game_id=str(row['game_id'])
                if game_id not in ready.index:pending+=1;continue
                actual=ready.loc[game_id]
                if isinstance(actual,pd.DataFrame):raise ValueError('Duplicate game outcome')
                if actual.home!=row['home'] or actual.away!=row['away'] or pd.Timestamp(actual.tipoff)!=tipoff:
                    raise ValueError('Shadow/final schedule identity mismatch')
                candidate=row['candidate'] if kind=='individual' else row['method']
                name=hashlib.sha256((game_id+':'+candidate).encode()).hexdigest()[:24]+'.json'
                path=meta.parent/'scored'/name
                if path.exists():record=read(path)
                else:
                    record={'kind':kind,'candidate':candidate,'config_hash':row['config_hash'],'game_id':game_id,
                            'created_at':row['created_at'],'scored_at':now(),'archive':meta.parent.name,
                            'home_win':int(actual.home_score>actual.away_score)}
                    if kind=='individual':record['p_home']=row['p_home']
                    else:
                        margin=float(actual.home_score-actual.away_score);total=float(actual.home_score+actual.away_score)
                        record.update({'p_home':row['p_home_score_model'],'margin_abs_error':abs(row['home_margin']-margin),
                            'total_abs_error':abs(row['total']-total),'margin_sq_error':(row['home_margin']-margin)**2,
                            'total_sq_error':(row['total']-total)**2,
                            'margin_covered':bool(row['margin_p10']<=margin<=row['margin_p90']),
                            'total_covered':bool(row['total_p10']<=total<=row['total_p90'])})
                    once(path,record)
                records.append(record)
    summary=[]
    if records:
        d=pd.DataFrame(records).sort_values(['created_at','archive']).drop_duplicates(['kind','candidate','config_hash','game_id'],keep='first')
        for (kind,candidate,config),group in d.groupby(['kind','candidate','config_hash']):
            row={'kind':kind,'candidate':candidate,'config_hash':config,**scores(group.home_win,group.p_home)}
            if kind=='scores':
                for target in ('margin','total'):
                    row[target+'_mae']=float(group[target+'_abs_error'].mean())
                    row[target+'_rmse']=float(np.sqrt(group[target+'_sq_error'].mean()))
                    row[target+'_coverage_80']=float(group[target+'_covered'].mean())
            summary.append(row)
    result={'updated_at':now(),'summary':summary,'scored_revision_rows':len(records),'pending_revision_rows':pending,
            'rule':'Earliest saved pregame revision per game/candidate/configuration; outcomes after tipoff+24h.',
            'status':'Descriptive prospective results only; no tuning, selection or promotion.'}
    update(REPORTS/'SHADOW_PROSPECTIVE.json',result);return result
