const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),assert=require('assert/strict');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const page=await browser.newPage();
 await page.route('https://www.nothingbundtcakes.com/**',r=>r.fulfill({body:'<html></html>',contentType:'text/html'}));await page.goto('https://www.nothingbundtcakes.com/customer/account/create/');
 await page.setContent(`<form>${['firstname','lastname','email_address','telephone','zip','password','password-confirmation'].map(id=>`<input id="${id}">`).join('')}<select id="birth_id"><option value="01">JANUARY</option></select><select id="day_id"><option value="15">15</option></select><select id="bakery_country"><option value="US">United States</option></select><select id="bakery_region_id"><option value="TX">Texas</option></select><select id="bakery_id"><option value="276">Flower Mound, TX</option></select><input type="checkbox" id="thanx-check"><input type="checkbox" id="sms-check"><button id="create-account" type="submit">CREATE ACCOUNT</button></form>`);
 await page.evaluate(()=>{document.querySelector('#telephone').addEventListener('input', e=>{const d=e.target.value.replace(/\D/g,'');if(d.length===10)e.target.value='('+d.slice(0,3)+') '+d.slice(3,6)+'-'+d.slice(6)});window.reports=[];window.submits=0;document.querySelector('form').onsubmit=e=>{e.preventDefault();submits++};window.task={active:true,session_id:'test',details:{first_name:'Test',last_name:'Example',email:'test@example.com',phone:'2025550147',zip_code:'75022',password:'ExampleTest123!',birthday:'2000-01-15',country:'United States',state:'Texas',bakery:'Flower Mound, TX'}};window.chrome={runtime:{sendMessage:(m,cb)=>{if(m.type==='status'){reports.push(m.payload);if(m.payload.stage==='claim_submit'){const claimed=!task.submitted;task.submitted=true;cb({claimed});return}}cb(m.type==='task'?task:{ok:true})}}};});
 await page.addScriptTag({path:path.join(__dirname,'../chrome_extension/bundt.js')});
 await page.waitForFunction(()=>submits===1);
 assert.equal(await page.locator('#password').inputValue(),'ExampleTest123!');assert.equal(await page.locator('#password-confirmation').inputValue(),'ExampleTest123!');assert(await page.locator('#thanx-check').isChecked());assert(!await page.locator('#sms-check').isChecked());assert.equal(await page.evaluate(()=>submits),1);assert(!(await page.evaluate(()=>JSON.stringify(reports))).includes('ExampleTest123!'));
 await page.evaluate(()=>{task.session_id='missing-bakery';task.submitted=false;task.details.bakery='Unknown';document.querySelector('#thanx-check').checked=false;reports=[]});
 await page.waitForFunction(()=>reports.some(r=>r.stage==='filling_details'));assert(!(await page.evaluate(()=>reports)).some(r=>r.stage==='ready_for_review'));
 assert.equal(await page.evaluate(()=>submits),1);assert(await page.locator('#thanx-check').isChecked());
 const login=await browser.newPage();
 await login.route('https://www.nothingbundtcakes.com/**',r=>r.fulfill({body:'<a href="/customer/account/logout/">LOG OUT</a>',contentType:'text/html'}));
 await login.goto('https://www.nothingbundtcakes.com/customer/account/login/referer/test/');
 await login.evaluate(()=>{window.chrome={runtime:{sendMessage:(m,cb)=>cb({active:true,session_id:'logout-test',details:{}})}}});
 await login.addScriptTag({path:path.join(__dirname,'../chrome_extension/bundt.js')});
 await login.waitForURL('**/customer/account/create/');
 await login.close();
 await page.evaluate(()=>{task.session_id='invalid-date';task.submitted=false;task.details.birthday='2000-02-31';reports=[]});
 await page.waitForFunction(()=>reports.some(r=>r.reason==='birthday'));
 assert.equal(await page.evaluate(()=>submits),1);
 console.log('PASS: logout resumes despite stale header, formatted phone accepted, rewards selected with delayed bakery, both passwords, explicit rewards opt-in, SMS unchanged, missing bakery blocks ready, single submit and no secret reports');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});

