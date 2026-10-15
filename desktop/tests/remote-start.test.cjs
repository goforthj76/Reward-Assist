const {readFileSync}=require('node:fs');
const {runInNewContext}=require('node:vm');
const assert=require('node:assert/strict');
async function scenario(app){
 const updates=[],starts=[];let tick;
 const toggle={checked:true};
 const node={style:{},querySelector:s=>s==='input'?toggle:node,querySelectorAll:()=>[],append(){},prepend(){},before(){},after(){},setAttribute(){}};
 const context={document:{createElement:()=>node,querySelector:()=>node,body:node},localStorage:{},crypto:{randomUUID:()=> 'device'},setInterval:f=>{tick=f},cloudKey:{},
  api:async (url,opts)=>{if(url.endsWith('/start'))starts.push(JSON.parse(opts.body));return {stage:'idle'}},
  cloudApi:async (url,opts)=>{if(url==='/api/remote')return {jobs:[{device:'device',id:'job',stage:'queued'}]};const body=JSON.parse(opts.body);if(url.endsWith('/claim'))return {job:{id:'job',payload:'encrypted'}};if(url.endsWith('/update'))updates.push(body);return {}},
  cloudDecrypt:async()=>({app,details:'authorized test fixture',confirmed:true}),cloudEncrypt:async x=>JSON.stringify(x)};
 runInNewContext(readFileSync(__dirname+'/../demo/remote.js','utf8'),context);
 // onchange starts the first async tick; wait for its side effects to settle.
 toggle.checked=true;toggle.onchange();for(let i=0;i<40;i++)await Promise.resolve();
 return {updates,starts};
}
(async()=>{
 const valid=await scenario('Nothing Bundt Cakes');assert.equal(valid.starts.length,1);assert(valid.updates.some(x=>x.stage==='running'));
 const invalid=await scenario('Unknown restaurant');assert.equal(invalid.starts.length,0);const failure=invalid.updates.find(x=>x.stage==='attention');assert(failure);assert.match(JSON.parse(failure.payload).message,/Invalid phone request/);
 console.log('PASS: supported request starts; unsupported request is rejected with an encrypted explanation');
})().catch(e=>{console.error(e);process.exit(1)});
