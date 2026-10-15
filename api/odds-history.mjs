import {authorized} from '../server/fp-input-store.mjs';
import {writeHistory,readHistory} from '../server/odds-history-store.mjs';
export default async function handler(req,res){
 res.setHeader('Cache-Control','private, no-store');res.setHeader('Vercel-CDN-Cache-Control','no-store');
 const send=(status,data)=>{res.statusCode=status;res.setHeader('Content-Type','application/json');res.end(JSON.stringify(data));};
 if(req.method==='POST'){
  if(!authorized(req.headers?.authorization,process.env.GOING_FP_INGEST_TOKEN))return send(401,{error:'Unauthorized'});
  if(Number(req.headers['content-length']||0)>4_000_000)return send(413,{error:'Historical upload too large'});
  let body;try{body=typeof req.body==='string'?JSON.parse(req.body):req.body;if(Buffer.byteLength(JSON.stringify(body))>4_000_000)throw Error();}catch{return send(400,{error:'Invalid historical upload'});}
  try{return send(200,await writeHistory(body));}catch{return send(503,{error:'Historical archive write unavailable; local originals retained'});}
 }
 if(req.method!=='GET')return send(405,{error:'Method not allowed'});
 const auth=req.headers?.authorization;
 if(!auth?.startsWith('Bearer '))return send(401,{error:'Sign in to browse saved historical odds'});
 const allowed=String(process.env.GOING_FP_ALLOWED_USERS||'').split(',').filter(Boolean);
 if(!allowed.length)return send(503,{error:'Private archive access unavailable'});
 try{
  const base=new URL(process.env.SUPABASE_URL),key=process.env.SUPABASE_PUBLISHABLE_KEY;
  if(base.protocol!=='https:'||!base.hostname.endsWith('.supabase.co')||!key)throw Error();
  const r=await fetch(new URL('/auth/v1/user',base),{headers:{apikey:key,Authorization:auth},signal:AbortSignal.timeout(10000)});
  if(!r.ok)return send(401,{error:'Session expired'});
  if(!allowed.includes((await r.json()).id))return send(403,{error:'Private archive access denied'});
  const query=new URL(req.url,'https://going-long.vercel.app').searchParams;
  return send(200,await readHistory(query.get('event'),query.get('market'),{book:query.get('book'),offset:query.get('offset')}));
 }catch{return send(503,{error:'Historical archive is not available yet'});}
}
