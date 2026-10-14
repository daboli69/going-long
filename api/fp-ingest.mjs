// Write-only uploader for the PC intake process. No raw-data GET/download endpoint.
import {authorized,writePrivateInputs,validateInputs} from '../server/fp-input-store.mjs';
import {decodePrivateUpload} from '../server/fp-upload.mjs';
export default async function handler(req,res){
 res.setHeader('Cache-Control','private, no-store');
 const send=(status,data)=>{res.statusCode=status;res.setHeader('Content-Type','application/json');res.end(JSON.stringify(data));};
 if(req.method!=='POST')return send(405,{error:'Method not allowed'});
 if(!authorized(req.headers.authorization,process.env.GOING_FP_INGEST_TOKEN))return send(401,{error:'Unauthorized'});
 if(Number(req.headers['content-length']||0)>4_000_000)return send(413,{error:'Payload too large'});
 let decoded;
 try{decoded=decodePrivateUpload(req.body);validateInputs(decoded.data);}catch(error){return send(error.status||400,{error:'Invalid or oversized private input; previous inputs retained'});}
 try{return send(200,{ok:true,...await writePrivateInputs(decoded.data),inputSha256:decoded.inputSha256});}
 catch{return send(503,{error:'Private input sync unavailable; previous inputs retained'});}
}
