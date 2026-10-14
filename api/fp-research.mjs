import {readPrivateInputs} from '../server/fp-input-store.mjs';
import {deriveResearch} from '../server/fp-research.mjs';
import {buildFpModel} from '../server/fp-model.mjs';
import {loadFpModelContext} from '../server/fp-model-context.mjs';
export default async function handler(req,res){
 res.setHeader('Cache-Control','private, no-store');res.setHeader('Vercel-CDN-Cache-Control','no-store');
 const send=(status,data)=>{res.statusCode=status;res.setHeader('Content-Type','application/json');res.end(JSON.stringify(data));};
 if(req.method!=='GET')return send(405,{error:'Method not allowed'});
 const allowed=String(process.env.GOING_FP_ALLOWED_USERS||'').split(',').filter(Boolean);
 if(!allowed.length)return send(503,{error:'Private research access is not configured'});
 const auth=req.headers?.authorization;
 if(!auth?.startsWith('Bearer '))return send(401,{error:'Sign in to use private research'});
 const season=Number(req.query?.season),week=Number(req.query?.week);
 if(!Number.isInteger(season)||!Number.isInteger(week)||week<1||week>18)return send(400,{error:'Verified model period required'});
 try{
  const base=new URL(process.env.SUPABASE_URL),key=process.env.SUPABASE_PUBLISHABLE_KEY;
  if(base.protocol!=='https:'||!base.hostname.endsWith('.supabase.co')||!key)throw Error('Configuration unavailable');
  const r=await fetch(new URL('/auth/v1/user',base),{headers:{apikey:key,Authorization:auth},signal:AbortSignal.timeout(10000)});
  if(!r.ok)return send(401,{error:'Session expired'});const user=await r.json();
  if(!allowed.includes(user.id))return send(403,{error:'Private research access denied'});
  const datasets=await readPrivateInputs({season,week,knownBy:new Date().toISOString()});
  const research=deriveResearch(datasets,{season,week});
  try{
   const context=await loadFpModelContext({season,week});
   research.challenger={...buildFpModel(datasets,{season,week,games:context.games,profiles:context.profiles}),contextSources:context.sources,contextClocks:context.clocks};
  }catch{research.challenger={status:'Private projection context unavailable; forecasts unchanged',forecasts:[]};}
  return send(200,research);
 }catch{return send(503,{error:'Private research unavailable; forecasts unchanged'});}
}
