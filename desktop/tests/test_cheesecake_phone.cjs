const {chromium}=require('playwright'),path=require('path'),assert=require('assert/strict');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const page=await browser.newPage();
 await page.setContent('<p>Enter the mobile phone number you want to use</p><input type="tel"><button disabled>TEXT ME</button>');
 await page.evaluate(()=>{
  window.clicks=0;window.reports=[];window.task={active:true,session_id:'phone',claims:[],details:{phone:'2025550147'}};
  document.querySelector('input').oninput=e=>{e.target.value='(202) 555 0147';document.querySelector('button').disabled=false};
  document.querySelector('button').onclick=()=>{clicks++;document.body.innerHTML='<h1>Enter Your Code</h1><input placeholder="Enter 6-Digit Code"><button>CONTINUE</button>';document.querySelector('button').onclick=()=>window.continued=true};
  window.chrome={runtime:{sendMessage:(m,cb)=>{if(m.type==='status'){reports.push(m.payload.stage);if(m.payload.stage.startsWith('claim_')){const claimed=!task.claims.includes(m.payload.stage);if(claimed)task.claims.push(m.payload.stage);cb({claimed});return}}cb(m.type==='task'?task:{ok:true})}}};
 });
 await page.addScriptTag({path:path.join(__dirname,'../chrome_extension/cheesecake.js')});
 await page.waitForFunction(()=>reports.includes('waiting_code'));assert.equal(await page.evaluate(()=>clicks),1);
 await page.evaluate(()=>task.code='123456');await page.waitForFunction(()=>window.continued===true);
 assert.equal(await page.locator('input').inputValue(),'123456');
 console.log('PASS: masked phone requests SMS once and code continues');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
