import {availability} from '../server/promo-availability.mjs';
import {sendJson} from '../server/vercel-response.mjs';
export default async function handler(req,res){
 if(req.method!=='GET')return sendJson(req,res,{error:'Method not allowed'},405);
 try{return sendJson(req,res,await availability(),200,120);}
 catch{return sendJson(req,res,{error:'Automatic roster checks are temporarily unavailable. Suggestions will retry automatically.'},503,30);}
}
