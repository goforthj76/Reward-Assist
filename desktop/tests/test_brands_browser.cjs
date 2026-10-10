const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});try{
 const page=await browser.newPage(),posts=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.context().route('**/*',route=>{const u=new URL(route.request().url());if(u.pathname.startsWith('/api/')){if(route.request().method()==='POST')posts.push(u.pathname);return route.fulfill({json:u.pathname==='/api/status'?{profiles:[],version:'0.5.30'}:{ok:true}})}if(u.hostname==='brands.test'){const f=path.join(__dirname,'../demo',u.pathname==='/'?'index.html':u.pathname);if(fs.existsSync(f))return route.fulfill({path:f})}return route.fulfill({status:200,body:'Official website fixture'})});
 await page.goto('http://brands.test/');await page.evaluate(()=>document.getElementById('authGate').remove());
 for(const brand of ['The Cheesecake Factory']){
  await page.locator(`[data-brand="${brand}"]`).click();
  assert(await page.locator('#newBrandPanel').isVisible());assert(!(await page.locator('#signupGrid').isVisible()));
  assert.equal(await page.locator('#newBrandTitle').textContent(),brand);
  assert(await page.locator(`[data-brand="${brand}"] img`).evaluate(el=>el.complete&&el.naturalWidth>0));
  posts.length=0;await page.evaluate(()=>startSetup());assert.equal(posts.length,0);
  const popupPromise=page.waitForEvent('popup');await page.getByRole('button',{name:'Open official website',exact:true}).click();const popup=await popupPromise;await popup.waitForLoadState();assert.match(popup.url(),/nothingbundtcakes.com|thecheesecakefactory.com/);await popup.close();
 }
 for(const brand of ['Dutch Bros','Taco Bell','Paris Baguette','Nothing Bundt Cakes']){await page.locator(`[data-brand="${brand}"]`).click();assert(await page.locator('#signupGrid').isVisible());assert(!(await page.locator('#newBrandPanel').isVisible()))}
 assert.deepEqual(errors,[]);console.log('PASS: new brand logos, pending state, official links, no unintended signup, existing flow restoration');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
