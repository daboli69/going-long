import {fetchParlay,SPORT_KEYS} from '../server/parlay.mjs';
import {sendJson} from '../server/vercel-response.mjs';
const cache=new Map(),pending=new Map(),TTL=120000;
export default async function handler(req,res){
  if(req.method!=='GET')return sendJson(req,res,{error:'Method not allowed'},405);
  const sport=new URL(req.url,'https://going-long.vercel.app').searchParams.get('sport')||'nfl';
  if(!Object.hasOwn(SPORT_KEYS,sport))return sendJson(req,res,{error:'Unsupported sport'},400);
  const key=process.env.PARLAY_API_KEY?.trim();
  if(!key)return sendJson(req,res,{error:'Live feed is not configured; saved prices remain available.'},503);
  try{
    let hit=cache.get(sport);
    if(!hit||Date.now()-hit.at>=TTL){
      if(!pending.has(sport))pending.set(sport,fetchParlay(sport,key).then(body=>{
        const value={body,at:Date.now()};cache.set(sport,value);return value;
      }).finally(()=>pending.delete(sport)));
      hit=await pending.get(sport);
    }
    return sendJson(req,res,hit.body,200,Math.max(0,Math.floor((TTL-Date.now()+hit.at)/1000)));
  }catch(error){
    console.error('Parlay odds request failed',{sport,type:error?.name||'Error'});
    return sendJson(req,res,{error:'Live provider unavailable; saved prices remain available.',provider:'parlay'},502);
  }
}
