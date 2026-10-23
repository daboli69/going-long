from pathlib import Path
import hashlib
import json
import os
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data';RAW=DATA/'raw';CACHE=DATA/'cache'
MODELS=ROOT/'models';REPORTS=ROOT/'reports';ARCHIVES=ROOT/'artifacts'
SEED=20261023
KEYS=('logistic','random_forest','xgboost','hist_gradient_boosting','rbf_svm','mlp')
NAMES={'logistic':'Logistic regression','random_forest':'Random forest','xgboost':'XGBoost',
       'hist_gradient_boosting':'Histogram gradient boosting','rbf_svm':'RBF support-vector model','mlp':'MLP neural network'}

def now():return datetime.now(timezone.utc).isoformat()
def stamp():return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def atomic(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
    temporary.write_text(json.dumps(obj,indent=2,default=str,allow_nan=False),encoding='utf-8');os.replace(temporary,path)
def once(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,default=str,allow_nan=False)

def low_priority():
    import psutil
    p=psutil.Process();n=max(1,(psutil.cpu_count() or 2)-2)
    if os.name=='nt':p.nice(psutil.IDLE_PRIORITY_CLASS);p.cpu_affinity(list(range(n)))
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[key]=str(n)
    return n
