import {gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
const hash=b=>createHash('sha256').update(b).digest('hex');
const invalid=(message,status=400)=>Object.assign(Error(message),{status});
// Below Vercel's 4.5 MB body ceiling; expanded inputs remain capped at 8 MB.
export function decodePrivateUpload(body){
 const wire=Buffer.isBuffer(body)?body:Buffer.from(typeof body==='string'?body:JSON.stringify(body??null));
 if(wire.length>4_000_000)throw invalid('Private upload too large',413);
 let envelope;try{envelope=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(wire));}catch{throw invalid('Invalid private upload');}
 let raw=wire;
 if(envelope?.encoding!==undefined){
  if(envelope.encoding!=='gzip-base64-v1'||Object.keys(envelope).sort().join(',')!=='data,encoding,sha256'||typeof envelope.data!=='string'||envelope.data.length%4||!/^[A-Za-z0-9+/]+={0,2}$/.test(envelope.data)||!/^[a-f\d]{64}$/.test(envelope.sha256))throw invalid('Invalid private upload encoding');
  const gzip=Buffer.from(envelope.data,'base64');if(gzip.toString('base64')!==envelope.data)throw invalid('Invalid private upload encoding');
  try{raw=gunzipSync(gzip,{maxOutputLength:8_000_000});}catch(error){throw invalid('Private upload expansion failed',error.code==='ERR_BUFFER_TOO_LARGE'?413:400);}
  if(hash(raw)!==envelope.sha256)throw invalid('Private upload checksum mismatch');
 }
 let data;try{data=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(raw));}catch{throw invalid('Invalid private input JSON');}
 return {data,inputSha256:hash(raw)};
}
