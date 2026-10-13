(() => {
  if (window.__bundtHelper) return;
  window.__bundtHelper = true;
  const app = 'Nothing Bundt Cakes';
  const ask = message => new Promise(resolve => {
    try { chrome.runtime.sendMessage(message, result => resolve(chrome.runtime.lastError ? null : result)); }
    catch { resolve(null); }
  });
  const field = id => document.getElementById(id);
  const visible = e => e && e.getClientRects().length > 0;
  function fill(id, value) {
    const e = field(id);
    if (!visible(e)) return false;
    if (e.value !== value) {
      const proto = e instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, 'value').set.call(e, value);
      for (const type of ['input', 'change', 'blur']) e.dispatchEvent(new Event(type, {bubbles:true}));
    }
    return id === 'telephone' ? e.value.replace(/\D/g, '') === String(value).replace(/\D/g, '') : e.value === value;
  }
  function select(id, label) {
    const e = field(id);
    if (!visible(e)) return false;
    const matches = [...e.options].filter(o => o.text.trim().toLowerCase() === label.trim().toLowerCase());
    return matches.length === 1 && fill(id, matches[0].value);
  }
  let busy = false, session = '', attempts = 0, done = false;
  async function run() {
    if (busy) return;
    busy = true;
    try {
      const task = await ask({type:'task',app});
      if (!task?.active) return;
      if (session !== task.session_id) {session = task.session_id; attempts = 0; done = false;}
      if (done) return;
      const report = (stage, reason = '') => ask({type:'status',payload:{app,session_id:session,stage,reason}});
      if (task.submitted) {
        const registered = /Thank you for registering with Nothing Bundt Cakes\./i.test(document.body.innerText);
        if (location.pathname === '/customer/account/' && registered) {
          done = true; await report('complete');
        } else if (++attempts >= 60) {done = true; await report('attention');}
        return;
      }
      if (!task.details) return;
      if (!location.pathname.startsWith('/customer/account/create')) {
        const key='rewardAssistLogout:'+session;
        // The logout response may retain a stale header link. Recognize login first.
        if (/^\/customer\/account\/login(?:\/|$)/.test(location.pathname) || /you (?:are|have been) logged out/i.test(document.body.innerText)) {location.assign('/customer/account/create/');return;}
        const logout=[...document.querySelectorAll('a[href]')].find(a=>/^(sign out|log out|logout)$/i.test(a.textContent.trim()) && new URL(a.href).origin===location.origin);
        if(logout && !sessionStorage.getItem(key)){sessionStorage.setItem(key,'1');logout.click();return;}
        const loggedOut=/you (?:are|have been) logged out/i.test(document.body.innerText) || document.querySelector('input[type="password"]');
        if(loggedOut){location.assign('/customer/account/create/');return;}
        if(++attempts>=45){done=true;await report('attention','logout');}
        return;
      }
      const d = task.details;
      const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(d.birthday || ''));
      const parsed = match && new Date(Date.UTC(+match[1], +match[2]-1, +match[3]));
      if (!match || parsed.getUTCFullYear() !== +match[1] || parsed.getUTCMonth()+1 !== +match[2] || parsed.getUTCDate() !== +match[3]) {
        done = true; await report('attention', 'birthday'); return;
      }
      const date = match.slice(1);
      // These IDs were inspected on the official signup page. Never infer checkbox order.
      let ok = true;
      // Enrollment is independent of delayed bakery options and formatted fields.
      const rewards = field('thanx-check');
      if (rewards && !rewards.disabled && !rewards.checked) {
        const label = [...(rewards.labels || [])].find(visible);
        if (visible(rewards)) rewards.click();
        else if (label) label.click();
      }
      for (const [id,key] of [['firstname','first_name'],['lastname','last_name'],['email_address','email'],['telephone','phone'],['zip','zip_code'],['password','password'],['password-confirmation','password']]) {
        ok = fill(id, d[key]) && ok;
      }
      // Changing the month repopulates days. Wait a tick before choosing a day.
      const month = field('birth_id'), day = field('day_id');
      if (month?.value !== date[1]) {
        fill('birth_id', date[1]);
        await report('filling_details');
        if (++attempts >= 30) {done = true; await report('attention', 'birthday');}
        return;
      }
      const birthdayOK = visible(day) && [...day.options].some(o => o.value === date[2]) && fill('day_id', date[2]);
      ok = birthdayOK && ok;
      ok = select('bakery_country', d.country) && ok;
      ok = select('bakery_region_id', d.state) && ok;
      ok = select('bakery_id', d.bakery) && ok;
      ok = ok && !!rewards?.checked;
      attempts++;
      if (ok) {
        const submit = field('create-account');
        if (visible(submit) && !submit.disabled && submit.form?.checkValidity() && month.value === date[1] && day.value === date[2]) {
          // Claim once on the desktop before clicking. Reloads and multiple tabs cannot resubmit.
          const claimed = await report('claim_submit');
          if (claimed?.claimed) {submit.click(); attempts = 0;}
        } else if (attempts >= 30) {done = true; await report('attention','validation');}
      }
      else if (attempts >= 30) {done = true; await report('attention', !birthdayOK ? 'birthday' : !rewards?.checked ? 'rewards' : 'fields');}
      else await report('filling_details');
      // Verification challenges remain on the official page; never automatically retry submission.
    } finally {busy = false;}
  }
  setInterval(() => run().catch(() => {}), 1000);
  run().catch(() => {});
})();
