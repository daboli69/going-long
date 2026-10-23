"""Six fixed families with independent chronological sigmoid calibration."""
import warnings
import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier,HistGradientBoostingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC
from sklearn.metrics import log_loss,brier_score_loss,accuracy_score
from xgboost import XGBClassifier
from .config import KEYS,SEED


def make(key,threads=1):
    models={
        'logistic':lambda:LogisticRegression(C=1,max_iter=1000,random_state=SEED),
        'random_forest':lambda:RandomForestClassifier(n_estimators=150,max_depth=8,min_samples_leaf=20,max_features='sqrt',n_jobs=threads,random_state=SEED),
        'xgboost':lambda:XGBClassifier(n_estimators=200,max_depth=3,learning_rate=.05,subsample=.9,colsample_bytree=.9,reg_lambda=5,n_jobs=threads,random_state=SEED,eval_metric='logloss'),
        'hist_gradient_boosting':lambda:HistGradientBoostingClassifier(max_iter=150,max_leaf_nodes=15,l2_regularization=5,early_stopping=False,random_state=SEED),
        'rbf_svm':lambda:SVC(C=1,gamma='scale',probability=False,random_state=SEED),
        'mlp':lambda:MLPClassifier(hidden_layer_sizes=(64,32),alpha=.01,max_iter=200,early_stopping=False,random_state=SEED)}
    return make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler(),models[key]())


def raw(model,x):
    if hasattr(model,'decision_function'):return model.decision_function(x)
    p=np.clip(model.predict_proba(x)[:,1],1e-6,1-1e-6)
    return np.log(p/(1-p))


def fit(train,calibration,columns,threads=1,log=print):
    if train.tipoff.max()>=calibration.tipoff.min():raise ValueError('Training and calibration overlap chronologically')
    if (train.tipoff.max()+np.timedelta64(24,'h'))>=calibration.tipoff.min():raise ValueError('Training outcomes were not available before calibration began (+24h rule)')
    if len(train)<300 or len(calibration)<100:raise ValueError('Insufficient chronological fitting samples')
    models={};messages=[]
    x=train[columns].to_numpy(float);xc=calibration[columns].to_numpy(float)
    for key in KEYS:
        log('Fitting '+key)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            model=make(key,threads);model.fit(x,train.home_win.astype(int))
            calibrator=LogisticRegression(C=1,max_iter=1000).fit(raw(model,xc).reshape(-1,1),calibration.home_win.astype(int))
        messages.extend({'model':key,'warning':type(w.message).__name__,'message':str(w.message)[:300]} for w in caught)
        models[key]=(model,calibrator)
    return {'models':models,'columns':columns,'warnings':messages,'train_n':len(train),'calibration_n':len(calibration),
            'trained_through':train.tipoff.max().isoformat(),'calibrated_through':calibration.tipoff.max().isoformat(),
            'training_outcomes_available_through':(train.tipoff.max()+np.timedelta64(24,'h')).isoformat(),
            'calibration_outcomes_available_through':(calibration.tipoff.max()+np.timedelta64(24,'h')).isoformat(),
            'medians':train[columns].median().fillna(0).to_numpy(float)}


def probabilities(bundle,frame):
    x=frame[bundle['columns']].to_numpy(float)
    return np.column_stack([bundle['models'][key][1].predict_proba(raw(bundle['models'][key][0],x).reshape(-1,1))[:,1] for key in KEYS])


def scores(y,p):
    y=np.asarray(y,int);p=np.clip(np.asarray(p,float),1e-6,1-1e-6)
    return {'n':len(y),'log_loss':float(log_loss(y,p,labels=[0,1])),'brier':float(brier_score_loss(y,p)),
            'accuracy':float(accuracy_score(y,p>.5))}


def weights(p,y):
    losses=np.array([scores(y,p[:,j])['log_loss'] for j in range(p.shape[1])])
    skill=np.maximum(0,np.log(2)-losses)
    return skill/skill.sum() if skill.sum()>0 else np.full(p.shape[1],1/p.shape[1])


def logits(p):
    p=np.clip(p,1e-6,1-1e-6);return np.log(p/(1-p))


def combine(p,historical_p=None,historical_y=None):
    if historical_p is None or len(historical_p)<100:
        mean=p.mean(axis=1)
        return {'equal':mean,'weighted':mean,'stacked':mean},np.full(6,1/6),None
    w=weights(historical_p,historical_y)
    stack=LogisticRegression(C=1,max_iter=1000).fit(logits(historical_p),historical_y)
    return {'equal':p.mean(axis=1),'weighted':p@w,'stacked':stack.predict_proba(logits(p))[:,1]},w,stack


def paired_ci(y,candidate,baseline,draws=2000,alpha=.05):
    y=np.asarray(y);candidate=np.clip(candidate,1e-6,1-1e-6);baseline=np.clip(baseline,1e-6,1-1e-6)
    loss=lambda p:-(y*np.log(p)+(1-y)*np.log(1-p))
    delta=loss(candidate)-loss(baseline);rng=np.random.default_rng(SEED)
    samples=np.array([delta[rng.integers(0,len(delta),len(delta))].mean() for _ in range(draws)])
    return {'delta':float(delta.mean()),'ci_low':float(np.quantile(samples,alpha/2)),'ci_high':float(np.quantile(samples,1-alpha/2))}
