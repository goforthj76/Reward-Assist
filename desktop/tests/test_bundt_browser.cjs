const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),assert=require('assert/strict');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const page=await browser.newPage();
 await page.setContent(`<form>${['firstname','lastname','email_address','telephone','zip','password','password-confirmation'].map(id=>`<input id="${id}">`).join('')}<select id="birth_id"><option value="01">JANUARY</option></select><select id="day_id"><option value="15">15</option></select><select id="bakery_country"><option value="US">United States</option></select><select id="bakery_region_id"><option value="TX">Texas</option></select><select id="bakery_id"><option value="276">Flower Mound, TX</option></select><input type="checkbox" id="thanx-check"><input type="checkbox" id="sms-check"><button type="submit">CREATE ACCOUNT</button></form>`);
 await page.evaluate(()=>{window.reports=[];window.submits=0;document.querySelector('form').onsubmit=e=>{e.preventDefault();submits++};window.task={active:true,session_id:'test',details:{first_name:'Test',last_name:'Example',email:'test@example.com',phone:'2025550147',zip_code:'75022',password:'ExampleTest123!',birthday:'2000-01-15',country:'United States',state:'Texas',bakery:'Flower Mound, TX'}};window.chrome={runtime:{sendMessage:(m,cb)=>{if(m.type==='status')reports.push(m.payload);cb(m.type==='task'?task:{ok:true})}}};});
 await page.addScriptTag({path:path.join(__dirname,'../chrome_extension/bundt.js')});
 await page.waitForFunction(()=>reports.some(r=>r.stage==='ready_for_review'));
 assert.equal(await page.locator('#password').inputValue(),'ExampleTest123!');assert.equal(await page.locator('#password-confirmation').inputValue(),'ExampleTest123!');assert(await page.locator('#thanx-check').isChecked());assert(!await page.locator('#sms-check').isChecked());assert.equal(await page.evaluate(()=>submits),0);assert(!(await page.evaluate(()=>JSON.stringify(reports))).includes('ExampleTest123!'));
 await page.evaluate(()=>{task.session_id='missing-bakery';task.details.bakery='Unknown';reports=[]});
 await page.waitForFunction(()=>reports.some(r=>r.stage==='filling_details'));assert(!(await page.evaluate(()=>reports)).some(r=>r.stage==='ready_for_review'));
 console.log('PASS: both passwords, explicit rewards opt-in, SMS unchanged, missing bakery blocks ready, no submit or secret reports');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});

