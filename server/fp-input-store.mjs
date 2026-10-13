// Server-only licensed inputs. Never imported into browser bundles or public snapshots.
import {createHash,timingSafeEqual} from 'node:crypto';
const digest=x=>createHash('sha256').update(String(x)).digest();
export function authorized(header,secret){return typeof secret==='string'&&secret.length>=32&&typeof header==='string'&&timingSafeEqual(digest(header),digest('Bearer '+secret));}
export function awareTime(value){
 if(typeof value!=='string')return NaN;
 const m=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$/.exec(value);
 if(!m)return NaN;
 const [y,mo,d,h,mi,se]=m.slice(1,7).map(Number),date=new Date(Date.UTC(y,mo-1,d));
 if(y<100||mo<1||mo>12||d<1||date.getUTCFullYear()!==y||date.getUTCMonth()!==mo-1||date.getUTCDate()!==d||h>23||mi>59||se>59)return NaN;
 if(m[7]!=='Z'){const [oh,om]=m[7].slice(1).split(':').map(Number);if(oh>23||om>59)return NaN;}
 return Date.parse(value);
}
const strings=x=>Array.isArray(x)&&x.every(v=>typeof v==='string'&&v.length>0&&v.length<=256);
const flat=x=>x&&Object.getPrototypeOf(x)===Object.prototype&&Object.values(x).every(v=>v===null||typeof v==='string'||typeof v==='boolean'||typeof v==='number'&&Number.isFinite(v));
export function validateInputs(data){
 if(data?.schema!=='going-private-fp-inputs-v1'||data.licensed!==true||!Number.isInteger(data.season)||data.season<2026||!Number.isInteger(data.prediction_week)||data.prediction_week<1||data.prediction_week>18||!Array.isArray(data.datasets)||!data.datasets.length||data.datasets.length>256)throw Error('Invalid private input envelope');
 let rows=0;
 for(const d of data.datasets){
  if(d.season!==data.season||!['prior_week','season_to_date'].includes(d.scope)||d.status!=='accepted'||typeof d.table!=='string'||!Array.isArray(d.records)||!d.records.length||!strings(d.columns)||!d.columns.length||(d.groups!==undefined&&!strings(d.groups))||!d.records.every(flat)||(d.reference_rows!==undefined&&(!Array.isArray(d.reference_rows)||!d.reference_rows.every(flat)))||!Number.isFinite(awareTime(d.known_at))||!Number.isFinite(awareTime(d.exported_at)))throw Error('Invalid dataset provenance');
  if(d.scope==='prior_week'&&d.observed_week!==data.prediction_week-1)throw Error('Wrong observed week');
  rows+=d.records.length;
 }
 if(rows>20000)throw Error('Private input size limit');return data;
}
function connection(env){
 const url=new URL(env.SUPABASE_URL||'https://invalid.invalid');
 if(url.protocol!=='https:'||!url.hostname.endsWith('.supabase.co')||!env.SUPABASE_SERVICE_ROLE_KEY)throw Error('Private storage is not configured');
 return {url:new URL('/storage/v1/object/going-fp-private/current.json',url),headers:{apikey:env.SUPABASE_SERVICE_ROLE_KEY,Authorization:'Bearer '+env.SUPABASE_SERVICE_ROLE_KEY}};
}
export async function writePrivateInputs(data,{env=process.env,fetchImpl=fetch}={}){
 validateInputs(data);const c=connection(env);
 const r=await fetchImpl(c.url,{method:'POST',headers:{...c.headers,'Content-Type':'application/json','x-upsert':'true'},body:JSON.stringify(data),signal:AbortSignal.timeout(15000)});
 if(!r.ok)throw Error('Private storage write failed');
 return {season:data.season,week:data.prediction_week,datasets:data.datasets.length};
}
export async function readPrivateInputs({season,week,knownBy},{env=process.env,fetchImpl=fetch}={}){
 const cutoff=awareTime(knownBy);if(!Number.isFinite(cutoff))throw Error('Model cutoff required');const c=connection(env);
 const r=await fetchImpl(c.url,{headers:c.headers,signal:AbortSignal.timeout(15000)});
 if(!r.ok)throw Error('Private storage unavailable');const data=validateInputs(await r.json());
 if(data.season!==season||data.prediction_week!==week)throw Error('Private inputs do not match model period');
 return data.datasets.filter(d=>awareTime(d.known_at)<=cutoff&&awareTime(d.exported_at)<=cutoff);
}
