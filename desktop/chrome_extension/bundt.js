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
      if (!task?.active || !task.details) return;
      if (session !== task.session_id) {session = task.session_id; attempts = 0; done = false;}
      if (done) return;
      const report = stage => ask({type:'status',payload:{app,session_id:session,stage}});
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
      if (ok) {done = true; await report('ready_for_review');}
      else if (attempts >= 30) {done = true; await report('attention');}
      else await report('filling_details');
      // No submit click, CAPTCHA handling or success inference in this test integration.
    } finally {busy = false;}
  }
  setInterval(() => run().catch(() => {}), 1000);
  run().catch(() => {});
})();
