// Phone-controlled Chick-fil-A flow for remote iPhone tasks
class PhoneCfaFlow {
  constructor(input, api) {
    this.api = api;
    this.phase = 'starting';
    this.serial = input.android_serial || '';
    this.details = input.details || '';
    this.plan = input.cfa_plan || {
      location: input.location || '75022',
      pickup_method: input.pickup_method || 'Drive-thru',
      reward: input.reward || '',
      auto_submit: true
    };
  }
  async validate() {
    const d = await this.api('/api/adb?serial=' + encodeURIComponent(this.serial));
    if (!d.ok) throw Error(d.message || 'Connect and authorize an Android device.');
    this.serial = d.serial;
  }
  async start() {
    this.phase = 'running';
    const rawBlocks = this.details.split(/\n\s*END(?:\n|$)/i).map(b => b.trim()).filter(Boolean);
    const blocks = rawBlocks.length ? rawBlocks : [this.details];
    let count = 0;
    for (let i = 0; i < blocks.length; i++) {
      await this.api('/api/android/launch', {method: 'POST', body: JSON.stringify({app: 'Chick-fil-A', device_serial: this.serial})});
      const plan = {
        location: this.plan.location || '75022',
        pickup_method: this.plan.pickup_method || 'Drive-thru',
        reward: this.plan.reward || '',
        auto_submit: Boolean(this.plan.auto_submit)
      };
      await this.api('/api/cfa/prepare', {method: 'POST', body: JSON.stringify({device_serial: this.serial, plan})});
      count++;
      if (this.plan.auto_submit || blocks.length > 1) {
        await new Promise(resolve => setTimeout(resolve, 1500));
        await this.api('/api/android/reset', {method: 'POST', body: JSON.stringify({app: 'Chick-fil-A', device_serial: this.serial})});
      }
    }
    this.phase = 'complete';
    return {stage: 'complete', message: `Autonomous Chick-fil-A checkout completed for ${count} account(s) and app storage reset.`};
  }
}
if (typeof module !== 'undefined') module.exports = PhoneCfaFlow;
