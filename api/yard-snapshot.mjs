import {sendJson} from '../server/vercel-response.mjs';
const allowed=new Set(['board.json','odds.json','history.json','backtest.json','bvp_career.json','hand2yr.json','microclimate.json','park_factors.json','wind_sens.json']);
const cache=new Map(),pending=new Map();
export default async function handler(req,res){
  if(req.method!=='GET')return sendJson(req,res,{error:'Method not allowed'},405);
  const file=new URL(req.url,'https://going-long.vercel.app').searchParams.get('file');
  if(!allowed.has(file))return sendJson(req,res,{error:'Unknown baseball snapshot'},400);
  let hit=cache.get(file);
  try{
    if(!hit||Date.now()-hit.at>120000){
      if(!pending.has(file))pending.set(file,(async()=>{const r=await fetch(`https://raw.githubusercontent.com/daboli69/hr-board/main/docs/${file}`,{signal:AbortSignal.timeout(20000)});if(!r.ok)throw Error();const body=await r.json();const value={body,at:Date.now()};cache.set(file,value);return value;})().finally(()=>pending.delete(file)));
      hit=await pending.get(file);
    }
    return sendJson(req,res,hit.body,200,120);
  }catch{
    if(hit){res.setHeader('X-Snapshot-Stale','true');return sendJson(req,res,hit.body,200,15);}
    return sendJson(req,res,{error:'Baseball data is temporarily unavailable. Please retry.'},503);
  }
}
