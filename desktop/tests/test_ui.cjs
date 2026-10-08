const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(require('node:path').join(__dirname,'../demo/index.html'),'utf8');
for(const [,script] of html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g))new vm.Script(script);
const context={document:{getElementById:id=>({value:id==='detailsBlock'?context.text:context.email})}};vm.createContext(context);
for(const name of ['parseLooseTacoBlocks','checkoutGiftCard','tacoPlan']){const start=html.indexOf('function '+name+'(');const end=html.indexOf('\n',start);vm.runInContext(html.slice(start,end),context)}
context.text='first_name: Test\nemail: test@example.com\ngift_card_number: 0000-1234\ngift_card_pin: 001\nEND ;';context.email='test@example.com';
assert.equal(context.checkoutGiftCard().number,'00001234');assert.equal(context.checkoutGiftCard().pin,'001');
assert.equal(context.tacoPlan().gift_card,undefined);
context.email='someone-else@example.com';assert.throws(()=>context.checkoutGiftCard());
context.text='first_name: Test\nemail: test@example.com\nEND';assert.equal(context.checkoutGiftCard(),null);
console.log('PASS: JavaScript syntax, paste parsing, leading zeroes, account selection, and saved-plan exclusion');

