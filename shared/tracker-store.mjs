/* Read side of the segmented public tracker store (no dependencies; runs in browsers and Node).
 *
 * The primary football tracking store is an append-only log of records. It is kept as
 * data/public_tracker/manifest.json (small, mutable, written last) plus immutable segment files
 * (consecutive records in original order). Inside a segment, exact-duplicate subtrees and long
 * strings are replaced by {"$ref":"<id>"} pointing into that segment's `dict`. Expansion returns
 * records whose JSON is byte-identical to what the writer produced, so every consumer sees the
 * same shape as the former single file.
 */
export const LAYOUT='public-tracker-segments-v1',MANIFEST_PATH='public_tracker/manifest.json';

export function expandValue(value,dict,share=false){
 if(Array.isArray(value))return value.map(v=>expandValue(v,dict,share));
 if(value&&typeof value==='object'){
  const keys=Object.keys(value);
  if(keys.length===1&&keys[0]==='$ref'){
   if(!Object.prototype.hasOwnProperty.call(dict,value.$ref))throw new Error('Tracker segment references a missing dictionary entry: '+value.$ref);
   // Default: a fresh copy, so a shared subtree can never be mutated through one record.
   // `share` keeps one object per dictionary entry; use it only for read-only consumers (the browser UI).
   return share?dict[value.$ref]:JSON.parse(JSON.stringify(dict[value.$ref]));
  }
  const out={};
  for(const k of keys)out[k]=expandValue(value[k],dict,share);
  return out;
 }
 return value;
}

export function expandSegment(segment,{share=false}={}){
 if(!segment||segment.layout!==LAYOUT||!Array.isArray(segment.records))throw new Error('Not a public tracker segment');
 return segment.records.map(r=>expandValue(r,segment.dict||{},share));
}

/** Rebuild the legacy single-file shape from a manifest and its segments (in manifest order). */
export function rehydrate(manifest,segments,{share=false}={}){
 if(!manifest||manifest.layout!==LAYOUT||!Array.isArray(manifest.segments))throw new Error('Not a public tracker manifest');
 if(segments.length!==manifest.segments.length)throw new Error('Segment count does not match the manifest');
 const records=[];
 segments.forEach((seg,i)=>{
  const rows=expandSegment(seg,{share});
  if(rows.length!==manifest.segments[i].records)throw new Error('Segment '+manifest.segments[i].file+' has '+rows.length+' records, expected '+manifest.segments[i].records);
  for(const r of rows)records.push(r);
 });
 if(records.length!==manifest.total_records)throw new Error('Rehydrated record count does not match the manifest');
 const out={};
 for(const key of manifest.top_level_keys)out[key]=key==='records'?records:manifest.summary[key];
 return out;
}

/** Browser/Node async loader. `getJson(relativePath)` fetches a file under the data directory. */
export async function loadTracker(getJson,{share=false}={}){
 const manifest=await getJson(MANIFEST_PATH);
 const segments=await Promise.all(manifest.segments.map(s=>getJson('public_tracker/'+s.file)));
 return rehydrate(manifest,segments,{share});
}

async function sha256Hex(text){
 const digest=await globalThis.crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));
 return [...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join('');
}

/** Like loadTracker, but takes raw text and verifies every segment against the manifest checksum. A cached
 *  manifest paired with a newer segment (or the reverse) fails here instead of rendering mixed history. */
export async function loadTrackerVerified(getText,{share=false}={}){
 const manifest=JSON.parse(await getText(MANIFEST_PATH));
 const segments=await Promise.all(manifest.segments.map(async s=>{
  const text=await getText('public_tracker/'+s.file);
  if(await sha256Hex(text)!==s.sha256)throw new Error('Tracker segment '+s.file+' is out of sync with the manifest');
  return JSON.parse(text);
 }));
 return rehydrate(manifest,segments,{share});
}
