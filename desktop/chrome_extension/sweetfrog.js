(() => {
  if (window.__sweetFrogHelper) return;
  window.__sweetFrogHelper = true;
  const app = 'sweetFrog';
  const ask = message => new Promise(resolve => {
    try { chrome.runtime.sendMessage(message, r => resolve(chrome.runtime.lastError ? null : r)); }
    catch { resolve(null); }
  });
  const visible = e => e && e.getClientRects().length > 0;
  const text = e => (e?.textContent || '').replace(/\s+/g, ' ').trim();
  const inputs = () => [...document.querySelectorAll('input')].filter(visible);
  const label = e => [e.id, e.name, e.type, e.getAttribute('aria-label'),
    ...[...(e.labels || [])].map(text)].join(' ');
  const field = pattern => inputs().find(e => pattern.test(label(e)));
  const button = name => [...document.querySelectorAll('button')].find(e => visible(e) && !e.disabled && text(e).toUpperCase() === name);
  function fill(e, value) {
    if (!visible(e) || e.disabled) return false;
    if (e.value !== value) {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(e, value);
      for (const type of ['input','change','blur']) e.dispatchEvent(new Event(type,{bubbles:true}));
    }
    return e.value === value;
  }
  const digits = s => String(s || '').replace(/\D/g,'');
  const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  let busy = false, session = '', ticks = 0;
  async function run() {
    if (busy) return;
    busy = true;
    try {
      const task = await ask({type:'task',app});
      if (!task?.active) return;
      if (session !== task.session_id) {session = task.session_id; ticks = 0;}
      const report = stage => ask({type:'status',payload:{app,session_id:session,stage}});
      const body = document.body?.innerText || '';
      const claims = task.claims || [];
      if (++ticks > 900) {await report('attention');return;}
      if (location.hostname === 'member.spendgo.com') {
        if (claims.includes('claim_submit') && /\/sweetfrog\/rewards\/?$/.test(location.pathname)
            && /MY REWARDS/i.test(body) && /Available Rewards/i.test(body)) await report('complete');
        else await report('attention'); // Never count a pre-existing signed-in account as a new signup.
        return;
      }
      const d = task.details;
      if (!d) return;
      const otp = inputs().filter(e => /^Digit [1-6] of 6$/i.test(e.getAttribute('aria-label') || ''));
      if (otp.length === 6) {
        await report('waiting_code');
        if (/^\d{6}$/.test(task.code || '') && (await report('claim_code'))?.claimed) {
          otp.sort((a,b) => label(a).localeCompare(label(b)));
          otp.forEach((e,i) => fill(e, task.code[i]));
        }
        return;
      }
      if (/incorrect code|invalid code|code has expired|something went wrong/i.test(body)) {await report('attention');return;}
      if (claims.includes('claim_submit')) return;
      if (/Enter your phone/i.test(body)) {
        if (claims.includes('claim_phone')) return;
        const phone = field(/phone|tel/i);
        if (digits(phone?.value) !== d.phone) fill(phone,d.phone);
        if (digits(phone?.value) !== d.phone || !button('NEXT')) return;
        await report('review_phone');
        if (task.approved && (await report('claim_phone'))?.claimed) button('NEXT')?.click();
        return;
      }
      if (!/Tell us about yourself/i.test(body)) return;
      // Each field must retain its expected value before the profile can be approved.
      const parts = d.birthday.split('-').map(Number);
      const date = new Date(Date.UTC(parts[0],parts[1]-1,parts[2]));
      if (date.getUTCFullYear()!==parts[0] || date.getUTCMonth()!==parts[1]-1 || date.getUTCDate()!==parts[2]) {await report('attention');return;}
      let ok = true;
      for (const [pattern,value] of [[/first.?name/i,d.first_name],[/last.?name/i,d.last_name],
        [/email/i,d.email],[/\bday\b/i,String(parts[2])],[/\byear\b/i,String(parts[0])],[/zip/i,d.zip_code]]) ok = fill(field(pattern),value) && ok;
      const month = document.getElementById('month');
      if (text(month) !== months[parts[1]-1]) {
        const option = [...document.querySelectorAll('[role="option"]')].find(e=>visible(e)&&text(e)===months[parts[1]-1]);
        if (option) option.click(); else if (visible(month)) month.click();
        return;
      }
      const store = document.getElementById('favorite_store');
      if (!visible(store)) return;
      if (!store.value || !store.value.toLowerCase().includes(d.store.toLowerCase()) || store.value.includes('**')) {
        const options = [...document.querySelectorAll('[role="option"]')].filter(e=>visible(e)&&!text(e).includes('**')&&text(e).toLowerCase().includes(d.store.toLowerCase()));
        if (options.length === 1) options[0].click();
        else if (options.length > 1) {await report('attention');}
        else { const open = button('OPEN'); if(open) open.click(); }
        return;
      }
      if (!ok || !button('NEXT')) return;
      await report('review_profile'); // Email/SMS choices remain as displayed for user review.
      if (task.approved && (await report('claim_submit'))?.claimed) button('NEXT')?.click();
    } finally {busy = false;}
  }
  setInterval(() => run().catch(()=>{}),1000);
  run().catch(()=>{});
})();
