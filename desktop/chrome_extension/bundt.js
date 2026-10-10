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
    return e.value === value;
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
      const report = stage => ask({type:'status',payload:{app,session_id:session,stage}});
      if (task.submitted) {
        const registered = /Thank you for registering with Nothing Bundt Cakes\./i.test(document.body.innerText);
        if (location.pathname === '/customer/account/' && registered) {
          done = true; await report('complete');
        } else if (++attempts >= 60) {done = true; await report('attention');}
        return;
      }
      if (!task.details || !location.pathname.startsWith('/customer/account/create')) return;
      const d = task.details, date = d.birthday.split('-');
      // These IDs were inspected on the official signup page. Never infer checkbox order.
      let ok = true;
      for (const [id,key] of [['firstname','first_name'],['lastname','last_name'],['email_address','email'],['telephone','phone'],['zip','zip_code'],['password','password'],['password-confirmation','password']]) {
        ok = fill(id, d[key]) && ok;
      }
      ok = fill('birth_id', date[1]) && ok;
      ok = fill('day_id', date[2]) && ok;
      ok = select('bakery_country', d.country) && ok;
      ok = select('bakery_region_id', d.state) && ok;
      ok = select('bakery_id', d.bakery) && ok;
      const rewards = field('thanx-check');
      if (ok && visible(rewards) && !rewards.checked) rewards.click();
      ok = ok && !!rewards?.checked;
      attempts++;
      if (ok) {
        const submit = field('create-account');
        if (visible(submit) && !submit.disabled && submit.form?.checkValidity()) {
          // Claim once on the desktop before clicking. Reloads and multiple tabs cannot resubmit.
          const claimed = await report('claim_submit');
          if (claimed?.claimed) {submit.click(); attempts = 0;}
        } else if (attempts >= 30) {done = true; await report('attention');}
      }
      else if (attempts >= 30) {done = true; await report('attention');}
      else await report('filling_details');
      // Verification challenges remain on the official page; never automatically retry submission.
    } finally {busy = false;}
  }
  setInterval(() => run().catch(() => {}), 1000);
  run().catch(() => {});
})();
