/* Verify that published data reached the public application, without provider calls. */
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {isLiveSnapshot} from '../server/public-snapshots.mjs';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const CRITICAL=new Set(['nfl_betting.json','ncaa_lines.json','history.json','nfl_roster.json','injury_context.json','opportunities.json']);
const digest=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex');

export async function checkPublicRefresh({root=ROOT,report,fetcher=fetch,sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms)),attempts=4}={}){
 const paths=report?.publication_paths;
 if(!Array.isArray(paths))throw Error('Publication report is required');
 const files=[...new Set(paths.filter(p=>typeof p==='string'&&p.startsWith('data/')).map(p=>p.slice(5)).filter(p=>CRITICAL.has(p)&&isLiveSnapshot(p)))];
 const checks=await Promise.all(files.map(async file=>{
  const expected=digest(JSON.parse(await readFile(path.join(root,'data',file),'utf8')));
  let error;
  for(let attempt=0;attempt<attempts;attempt++){
   if(attempt)await sleep(45000); // Allow the existing 120-second CDN entry to expire.
   try{
    const response=await fetcher('https://going-long.vercel.app/api/snapshot?file='+encodeURIComponent(file),{signal:AbortSignal.timeout(20000),headers:{'Accept':'application/json'}});
    if(!response.ok)throw Error('HTTP '+response.status);
    if(digest(await response.json())!==expected)throw Error('Published content differs from the public response');
    return {file,status:'verified',source:response.headers.get('x-snapshot-source')||'unknown'};
   }catch(e){error=e.message;}
  }
  return {file,status:'failed',error};
 }));
 return {healthy:checks.every(c=>c.status==='verified'),checks};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const report=JSON.parse(await readFile(process.argv[2],'utf8'));
 const result=await checkPublicRefresh({report});console.log(JSON.stringify(result,null,2));
 if(!result.healthy)process.exitCode=1;
}
