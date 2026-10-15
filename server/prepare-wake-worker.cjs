// Prepare a deployment from an exported copy of the CURRENT production worker.
// Never deploy wake.js alone: authentication, vault and reporting must be preserved.
const fs=require('node:fs');
const path=require('node:path');
const [input,output]=process.argv.slice(2);
if(!input||!output)throw Error('Usage: node server/prepare-wake-worker.cjs current-worker.js staged-worker.mjs');
let source=fs.readFileSync(input,'utf8');
if(source.includes('async function wake('))throw Error('Wake integration already present; review instead of adding twice.');
const auth='const uid=await current(q,e);';
const remote='async function remote(q,e,u,c,uid){';
for(const needle of [auth,remote])if(source.split(needle).length!==2)throw Error('Unexpected production structure; review required: '+needle);
source=source.replace(auth,"if(u.pathname.startsWith('/api/wake/tablet/'))return wake(q,e,u,c);"+auth);
source=source.replace(remote,remote+"\nif(u.pathname==='/api/remote/wake'||u.pathname.startsWith('/api/remote/wake/'))return wake(q,e,u,c,uid);\n");
source=fs.readFileSync(path.join(__dirname,'wake.js'),'utf8')+'\n'+source;
fs.writeFileSync(output,source,{flag:'wx'});
console.log('Prepared worker. Review diff and run node --check before deployment.');
