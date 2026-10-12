const assert=require('node:assert/strict');
const Flow=require('../demo/remote-taco.js');
(async()=>{
 const calls=[];let verified=false;
 const api=async(path,options)=>{calls.push(path);if(path.startsWith('/api/adb'))return {ok:true,serial:'phone'};if(path.endsWith('/verify'))return {stage:verified?'signed_in':'attention',message:'Try latest code'};if(path.endsWith('/payment'))return {payment_ready:true};if(path.endsWith('/review'))return {text:'Store A Total $0.00 PLACE ORDER'};return {message:'Submitted once'};};
 const f=new Flow({details:'email: test@example.com',taco_plan:{location:'Store A',payment_method:'venmo'}},api);
 await f.validate();assert.equal(f.serial,'phone');
 assert.equal((await f.afterWeb()).codePhase,'android');
 assert.equal((await f.code('123456')).stage,'waiting_code');assert(!calls.includes('/api/taco/prepare'));
 verified=true;assert.equal((await f.code('654321')).reviewKind,'order');assert(!calls.includes('/api/taco/submit'));
 assert.equal((await f.submit()).stage,'attention');await assert.rejects(()=>f.submit());
 assert.equal(calls.filter(x=>x.endsWith('/submit')).length,1);
 console.log('Phone Taco flow: Android handoff, failed verification, checkout review, and single submission passed.');
})().catch(e=>{console.error(e);process.exitCode=1});

