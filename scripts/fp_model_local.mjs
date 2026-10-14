// Local private-model evaluation only. No network, provider spending or public writes.
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {buildFpModel} from '../server/fp-model.mjs';
import {validateInputs} from '../server/fp-input-store.mjs';
import {createHash} from 'node:crypto';
import {loadFpModelContext} from '../server/fp-model-context.mjs';
const root=resolve(process.argv[2]||'FantasyPoints');
const repo=fileURLToPath(new URL('../',import.meta.url));
const bundle=validateInputs(JSON.parse(await readFile(join(root,'model_inputs/current.json'),'utf8')));
const schedule=JSON.parse(await readFile(join(repo,'data/nfl_betting.json'),'utf8'));
const history=JSON.parse(await readFile(join(repo,'data/history.json'),'utf8'));
const context=await loadFpModelContext({season:bundle.season,week:bundle.prediction_week,fetchImpl:async()=>{throw Error('Offline local evaluation');},readImpl:async file=>JSON.stringify(file==='history.json'?history:schedule)});
const result=buildFpModel(bundle.datasets,{season:bundle.season,week:bundle.prediction_week,games:context.games,profiles:context.profiles});
await mkdir(join(root,'model_inputs/challenger'),{recursive:true});
const hash=x=>createHash('sha256').update(x).digest('hex');
const codeHash=hash(await readFile(join(repo,'server/fp-model.mjs'))),protocolHash=hash(await readFile(join(repo,'config/fp_model_protocol.json')));
const historyHash=hash(JSON.stringify(history)),scheduleHash=hash(JSON.stringify(schedule));
const fingerprint=hash(JSON.stringify({codeHash,protocolHash,historyHash,scheduleHash,receipts:result.forecasts.map(x=>x.receipt)}));
const seal={captured_at:new Date().toISOString(),codeHash,protocolHash,historyHash,scheduleHash,result,availability:'Unverified research-only projection; not a recommendation or eligible forward-performance cohort'};
try{await writeFile(join(root,'model_inputs/challenger',fingerprint+'.json'),JSON.stringify(seal),{flag:'wx'});}catch(error){if(error.code!=='EEXIST')throw error;}
await writeFile(join(root,'model_inputs/challenger/current.json'),JSON.stringify(result));
console.log(JSON.stringify({season:result.season,week:result.week,forecasts:result.forecasts.length,changed:result.forecasts.filter(x=>Math.abs(x.delta)>.01).length,excluded:result.excluded.length,reasons:result.excluded.reduce((m,x)=>(m[x.reason]=(m[x.reason]||0)+1,m),{}),status:result.status}));
