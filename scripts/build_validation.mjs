import {build} from 'vite';
import {fileURLToPath} from 'node:url';
export async function buildValidation(){
 await build({configFile:false,root:fileURLToPath(new URL('../apps/validation/',import.meta.url)),base:'/validation/',build:{outDir:fileURLToPath(new URL('../dist/vercel/validation/',import.meta.url)),emptyOutDir:true}});
}
