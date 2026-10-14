// Write-only uploader for the PC intake process. No raw-data GET/download endpoint.
import {authorized,writePrivateInputs} from '../server/fp-input-store.mjs';
export default async function handler(req,res){
 res.setHeader('Cache-Control','private, no-store');
 const send=(status,data)=>{res.statusCode=status;res.setHeader('Content-Type','application/json');res.end(JSON.stringify(data));};
 if(req.method!=='POST')return send(405,{error:'Method not allowed'});
 if(!authorized(req.headers.authorization,process.env.GOING_FP_INGEST_TOKEN))return send(401,{error:'Unauthorized'});
 if(Number(req.headers['content-length']||0)>8_000_000)return send(413,{error:'Payload too large'});
 try{const data=typeof req.body==='string'?JSON.parse(req.body):req.body;if(Buffer.byteLength(JSON.stringify(data))>8_000_000)return send(413,{error:'Payload too large'});return send(200,{ok:true,...await writePrivateInputs(data)});}
 catch{return send(503,{error:'Private input sync unavailable; previous inputs retained'});}
}
