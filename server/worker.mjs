import {fetchParlay,SPORT_KEYS} from './parlay.mjs';
const memory=new Map(),pending=new Map();
const TTL=120000;
const SNAPSHOTS=new Set(['/data/history.json','/data/data.json','/data/nfl_betting.json','/data/ncaa_lines.json']);
const snapshots=new Map();
const json=(body,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
export async function oddsResponse(request,env,ctx={waitUntil(){}}){
  if(request.method!=='GET')return json({error:'Method not allowed'},405);
  const url=new URL(request.url),sport=url.searchParams.get('sport')||'nfl';
  if(!Object.hasOwn(SPORT_KEYS,sport))return json({error:'Unsupported sport'},400);
  const cached=memory.get(sport);
  if(cached&&Date.now()-cached.at<TTL)return json(cached.body);
  const cacheKey=new Request(`${url.origin}/api/cache/parlay-v1/${sport}`);
  const cache=globalThis.caches?.default;
  const shared=await cache?.match(cacheKey);
  if(shared)return json(await shared.json());
  if(!env.PARLAY_API_KEY)return json({error:'Live feed is not configured. The saved snapshot remains available.'},503);
  try{
    if(!pending.has(sport))pending.set(sport,fetchParlay(sport,env.PARLAY_API_KEY).finally(()=>pending.delete(sport)));
    const body=await pending.get(sport);memory.set(sport,{at:Date.now(),body});
    if(cache)ctx.waitUntil(cache.put(cacheKey,Response.json(body,{headers:{'Cache-Control':`public,max-age=${TTL/1000}`}})));
    return json(body);
  }catch(error){
    // Do not forward upstream bodies, headers or credentials to the client.
    return json({error:'The live odds provider is unavailable. Showing the saved snapshot.',provider:'parlay'},502);
  }
}
export default {
  async fetch(request,env,ctx){
    const url=new URL(request.url);
    if(url.pathname==='/api/odds')return oddsResponse(request,env,ctx);
    if(url.pathname.startsWith('/api/'))return json({error:'Not found'},404);
    if(SNAPSHOTS.has(url.pathname)){
      // Follow nightly GitHub snapshots without requiring a new UI deployment.
      const hit=snapshots.get(url.pathname);
      if(hit&&Date.now()-hit.at<300000)return new Response(hit.text,{headers:{'Content-Type':'application/json','X-Snapshot-Source':'nightly','Cache-Control':'public,max-age=300'}});
      try{
        const r=await fetch('https://raw.githubusercontent.com/daboli69/going-long/main'+url.pathname,{signal:AbortSignal.timeout(10000)});
        if(r.ok){
          const body=await r.json();
          if(url.pathname!=='/data/history.json'||body.betting?.schema_version===1){
            const text=JSON.stringify(body);snapshots.set(url.pathname,{at:Date.now(),text});
            return new Response(text,{headers:{'Content-Type':'application/json','X-Snapshot-Source':'nightly','Cache-Control':'public,max-age=300'}});
          }
        }
      }catch{/* Packaged snapshot remains available during source outages. */}
    }
    return env.ASSETS.fetch(request);
  }
};
