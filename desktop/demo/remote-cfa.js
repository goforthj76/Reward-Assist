// Phone-controlled Chick-fil-A flow for remote iPhone tasks
class PhoneCfaFlow {
  constructor(input, api, onProgress) {
    this.api = api;
    this.onProgress = onProgress || (() => {});
    this.phase = 'starting';
    this.serial = input.android_serial || '';
    this.details = input.details || '';
    this.plan = input.cfa_plan || {
      location: input.location || '75022',
      pickup_method: input.pickup_method || 'Drive-thru',
      reward: input.reward || '',
      auto_submit: true,
      clear_initial: true
    };
  }
  async validate() {
    const d = await this.api('/api/adb?serial=' + encodeURIComponent(this.serial));
    if (!d.ok) throw Error(d.message || 'Connect and authorize an Android device.');
    this.serial = d.serial;
  }
  async start() {
    this.phase = 'running';
    if (this.plan.clear_initial) {
      await this.onProgress('Waking Android tablet & clearing app storage...');
      await this.api('/api/android/reset', {method: 'POST', body: JSON.stringify({app: 'Chick-fil-A', device_serial: this.serial})});
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    const rawBlocks = this.details.split(/\n\s*END(?:\n|$)/i).map(b => b.trim()).filter(Boolean);
    const blocks = rawBlocks.length ? rawBlocks : [this.details];
    let count = 0;
    for (let i = 0; i < blocks.length; i++) {
      const idxText = blocks.length > 1 ? ` (account ${i + 1} of ${blocks.length})` : '';
      await this.onProgress(`Opening Chick-fil-A${idxText}...`);
      await this.api('/api/android/launch', {method: 'POST', body: JSON.stringify({app: 'Chick-fil-A', device_serial: this.serial})});
      const plan = {
        location: this.plan.location || '75022',
        pickup_method: this.plan.pickup_method || 'Drive-thru',
        reward: this.plan.reward || '',
        auto_submit: Boolean(this.plan.auto_submit)
      };
      await this.onProgress(`Preparing & placing order${idxText}...`);
      await this.api('/api/cfa/prepare', {method: 'POST', body: JSON.stringify({device_serial: this.serial, plan})});
      count++;
      if (this.plan.auto_submit || blocks.length > 1) {
        await this.onProgress(`Resetting app storage for next account${idxText}...`);
        await new Promise(resolve => setTimeout(resolve, 1500));
        await this.api('/api/android/reset', {method: 'POST', body: JSON.stringify({app: 'Chick-fil-A', device_serial: this.serial})});
      }
    }
    this.phase = 'complete';
    return {stage: 'complete', message: `Autonomous Chick-fil-A checkout completed for ${count} account(s) and app storage reset.`};
  }
}
if (typeof module !== 'undefined') module.exports = PhoneCfaFlow;
