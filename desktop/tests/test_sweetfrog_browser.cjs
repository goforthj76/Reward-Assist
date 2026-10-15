const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
 const page=await browser.newPage();
 await page.setContent('<h1>Enter your phone</h1><input type="tel" aria-label="Phone"><button>NEXT</button>');
 await page.evaluate(()=>{
 window.task={active:true,session_id:'one',details:{phone:'2025550100'},claims:[],approved:false};
 window.reports=[];window.clicks=0;
 document.querySelector('button').onclick=()=>clicks++;
 window.chrome={runtime:{sendMessage:(m,cb)=>{
 if(m.type==='task')return cb(JSON.parse(JSON.stringify(task)));
 reports.push(m.payload.stage);
 if(m.payload.stage.startsWith('claim_')){const claimed=!task.claims.includes(m.payload.stage);if(claimed)task.claims.push(m.payload.stage);return cb({claimed})}
 cb({ok:true});
 }}};
 });
 await page.addScriptTag({path:path.join(__dirname,'../chrome_extension/sweetfrog.js')});
 await page.waitForFunction(()=>reports.includes('review_phone'));
 assert.equal(await page.evaluate(()=>clicks),0);
 await page.evaluate(()=>task.approved=true);
 await page.waitForFunction(()=>clicks===1);
 await page.evaluate(()=>{document.body.innerHTML='<h1>Please enter your code</h1>'+Array.from({length:6},(_,i)=>'<input aria-label="Digit '+(i+1)+' of 6">').join('');task.code='123456';});
 await page.waitForFunction(()=>[...document.querySelectorAll('input')].map(e=>e.value).join('')==='123456');
 assert.equal(await page.evaluate(()=>reports.filter(x=>x==='claim_phone').length),1);
 assert.equal(await page.evaluate(()=>reports.filter(x=>x==='claim_code').length),1);

 await page.evaluate(()=>{
 task.details={first_name:'Test',last_name:'Person',email:'test@example.com',phone:'2025550100',birthday:'1990-10-21',zip_code:'75022',store:'Flower Mound - 35634'};
 task.approved=false;task.code='';window.clicks=0;
 document.body.innerHTML='<h1>Tell us about yourself</h1><input id="first_name"><input id="last_name"><input type="email"><input id="day"><input id="year"><input id="zip"><div id="month">October</div><input id="favorite_store" value="Flower Mound - 35634"><button>NEXT</button>';
 document.querySelector('button').onclick=()=>clicks++;
 });
 await page.waitForFunction(()=>reports.includes('review_profile'));
 assert.equal(await page.locator('#day').inputValue(),'21');
 assert.equal(await page.locator('#year').inputValue(),'1990');
 assert.equal(await page.evaluate(()=>clicks),0);
 await page.evaluate(()=>task.approved=true);
 await page.waitForFunction(()=>clicks===1);
 assert.equal(await page.evaluate(()=>reports.filter(x=>x==='claim_submit').length),1);
 console.log('PASS: phone waits for approval, one SMS request, six-digit code entry, no duplicate claims');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
