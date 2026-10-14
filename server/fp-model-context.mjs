// Reuse the public snapshot source, not a deployment's indefinitely old data.
import {readFile} from 'node:fs/promises';
import {awareTime} from './fp-input-store.mjs';
export async function loadFpModelContext({season,week,now=Date.now(),fetchImpl=fetch,readImpl=file=>readFile(new URL('../data/'+file,import.meta.url),'utf8')}={}){
 const clocks={},sources={};
 const load=async file=>{
  const valid=data=>{
   const at=awareTime(file==='history.json'?data?.betting?.generated_at:data?.generated_at);
   if(!Number.isFinite(at)||at>now||now-at>36*3600000)return false;
   if(file==='history.json')return data?.betting?.profiles&&typeof data.betting.profiles==='object';
   return Array.isArray(data.games)&&data.games.some(g=>g.season===season&&g.week===week&&awareTime(g.kickoff)>now);
  };
  try{
   const r=await fetchImpl('https://raw.githubusercontent.com/daboli69/going-long/main/data/'+file,{signal:AbortSignal.timeout(10000)});
   if(r.ok){const data=await r.json();if(valid(data)){sources[file]='current-public-snapshot';clocks[file]=file==='history.json'?data.betting.generated_at:data.generated_at;return data;}}
  }catch{/* Only a provably fresh matching deployment snapshot may substitute. */}
  const data=JSON.parse(await readImpl(file));
  if(!valid(data))throw Error('Fresh current-period public model context unavailable');
  sources[file]='fresh-packaged-fallback';clocks[file]=file==='history.json'?data.betting.generated_at:data.generated_at;return data;
 };
 const [schedule,history]=await Promise.all([load('nfl_betting.json'),load('history.json')]);
 return {games:schedule.games,profiles:history.betting.profiles,clocks,sources};
}
