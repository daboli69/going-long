import {sendJson} from '../server/vercel-response.mjs';
export default function handler(req,res){
 if(req.method!=='GET')return sendJson(req,res,{error:'Method not allowed'},405);
 let key=process.env.SUPABASE_PUBLISHABLE_KEY||null;
 if(key&&!key.startsWith('sb_publishable_')){try{if(JSON.parse(Buffer.from(key.split('.')[1],'base64url')).role!=='anon')key=null;}catch{key=null;}}
 return sendJson(req,res,{url:process.env.SUPABASE_URL||null,publishableKey:key},200,60);
}
