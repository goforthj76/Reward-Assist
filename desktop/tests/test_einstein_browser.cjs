const {chromium}=require('playwright'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const page=await browser.newPage();
 await page.route('https://orders.einsteinbros.com/**',r=>r.fulfill({contentType:'text/html',body:'<input id="formBasicFirstName"><input id="formBasicLastName"><input id="formBasicZipCode"><input id="formBasicDOB"><input type="email"><input type="tel"><input type="password"><input type="password"><button>JOIN NOW</button>'}));
 await page.goto('https://orders.einsteinbros.com/signup');
 await page.evaluate(()=>{
 window.task={active:true,session_id:'test',claims:[],approved:false,details:{first_name:'Test',last_name:'Person',zip_code:'75022',birthday:'2000-10-14',email:'test@example.com',phone:'2025550100',password:'Example123'}};
 window.reports=[];window.clicks=0;document.querySelector('button').onclick=()=>{clicks++;document.body.innerHTML='<h3>Welcome!</h3><p>Get ready for perks, points, and all the bagels.</p>'};
 window.chrome={runtime:{sendMessage:(m,cb)=>{if(m.type==='task')return cb(JSON.parse(JSON.stringify(task)));reports.push(m.payload.stage);if(m.payload.stage==='claim_submit'){const claimed=!task.claims.includes('claim_submit');task.claims.push('claim_submit');return cb({claimed})}cb({ok:true})}}};
 });
 await page.addScriptTag({path:path.join(__dirname,'../chrome_extension/einstein.js')});
 await page.waitForFunction(()=>reports.includes('review_required'));
 assert.equal(await page.evaluate(()=>clicks),0);
 assert.equal(await page.locator('#formBasicDOB').inputValue(),'10/14/2000');
 assert.deepEqual(await page.locator('input[type=password]').evaluateAll(es=>es.map(e=>e.value)),['Example123','Example123']);
 await page.evaluate(()=>task.approved=true);
 await page.waitForFunction(()=>reports.includes('complete'));
 assert.equal(await page.evaluate(()=>clicks),1);
 console.log('PASS: both passwords, birthday, approval gate, single submit and welcome confirmation');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
