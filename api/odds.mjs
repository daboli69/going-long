import {fetchParlay,SPORT_KEYS} from '../server/parlay.mjs';
import {sendJson} from '../server/vercel-response.mjs';
const failures=new Map();
const cache=new Map(),pending=new Map(),TTL=600000;
export default async function handler(req,res){
  if(req.method!=='GET')return sendJson(req,res,{error:'Method not allowed'},405);
  const sport=new URL(req.url,'https://going-long.vercel.app').searchParams.get('sport')||'nfl';
  if(!Object.hasOwn(SPORT_KEYS,sport))return sendJson(req,res,{error:'Unsupported sport'},400);
  const key=process.env.PARLAY_API_KEY?.trim();
  if(!key)return sendJson(req,res,{error:'Live feed is not configured; saved prices remain available.'},503);
  const saved=()=>{
    const hit=cache.get(sport);
    if(!hit||Date.now()-hit.at>86400000)return false;
    res.setHeader('X-Odds-Cache','stale');
    sendJson(req,res,{...hit.body,feed_status:'STALE',refresh_status:'STALE',feed_notice:'Provider refresh failed. Saved prices remain visible with their original timestamps; confirm current prices before betting.',retry_at:new Date(failures.get(sport).at).toISOString(),provider_error:failures.get(sport).reason},200,60);
    return true;
  };
  const retry=failures.get(sport);
  if(retry&&Date.now()<retry.at){if(saved())return;return sendJson(req,res,{error:'Live provider unavailable; requests are paused briefly to avoid repeated failures.',provider:'parlay',provider_error:retry.reason,retry_at:new Date(retry.at).toISOString()},503,60);}
  try{
    let hit=cache.get(sport);
    if(!hit||Date.now()-hit.at>=TTL){
      if(!pending.has(sport))pending.set(sport,fetchParlay(sport,key).then(body=>{
        const value={body,at:Date.now()};cache.set(sport,value);return value;
      }).finally(()=>pending.delete(sport)));
      hit=await pending.get(sport);
    }
    res.setHeader('X-Odds-Cache-Age',String(Math.max(0,Math.floor((Date.now()-hit.at)/1000))));
    return sendJson(req,res,hit.body,200,Math.max(0,Math.floor((TTL-Date.now()+hit.at)/1000)));
  }catch(error){
    const wait=Math.max(60,Number(error?.retryAfterSec)||300),reason={code:error?.code||error?.name||'ERROR',status:error?.status||null,stage:error?.stage||'request',message:error?.providerMessage||'transport unavailable'};
    failures.set(sport,{at:Date.now()+wait*1000,reason});
    console.error('Parlay odds request failed',{sport,...reason,retry_after_seconds:wait});
    if(saved())return;
    return sendJson(req,res,{error:'Live provider unavailable; saved prices remain available.',provider:'parlay',provider_error:reason},502);
  }
}
