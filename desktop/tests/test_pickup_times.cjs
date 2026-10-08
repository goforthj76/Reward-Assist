const assert=require('node:assert/strict');
const times=require('../demo/pickup-times.js');
assert.equal(times(new Date(2026,9,8,14,28))[0],'2:45 PM');
assert.equal(times(new Date(2026,9,8,14,30))[0],'2:45 PM');
assert.equal(times(new Date(2026,9,8,14,30,1))[0],'3:00 PM');
assert.equal(times(new Date(2026,9,8,23,29))[0],'11:45 PM');
assert.deepEqual(times(new Date(2026,9,8,23,46)),[]);
assert.equal(times(new Date(2026,9,8,0,0))[0],'12:15 AM');
console.log('PASS: lead time, quarter-hour rounding, seconds, and midnight cutoff');
