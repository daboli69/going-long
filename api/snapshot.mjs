import {readFile} from 'node:fs/promises';
import {sendJson} from '../server/vercel-response.mjs';
const allowed=new Set(['history.json','data.json','nfl_betting.json','ncaa_lines.json','results.json','football_context.json']);
export default async function handler(req,res){
  if(req.method!=='GET')return sendJson(req,res,{error:'Method not allowed'},405);
  const file=new URL(req.url,'https://going-long.vercel.app').searchParams.get('file');
  if(!allowed.has(file))return sendJson(req,res,{error:'Unknown snapshot'},400);
  try{
    const r=await fetch(`https://raw.githubusercontent.com/daboli69/going-long/main/data/${file}`,{signal:AbortSignal.timeout(10000)});
    if(r.ok){const body=await r.json();res.setHeader('X-Snapshot-Source','nightly');return sendJson(req,res,body,200,120);}
  }catch{/* Use the validated deployment snapshot if GitHub is unavailable. */}
  try{
    const body=JSON.parse(await readFile(new URL('../data/'+file,import.meta.url),'utf8'));
    res.setHeader('X-Snapshot-Source','packaged');return sendJson(req,res,body,200,30);
  }catch{return sendJson(req,res,{error:'Snapshot temporarily unavailable'},503);}
}
