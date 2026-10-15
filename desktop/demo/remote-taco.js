// Phone-controlled Taco Bell stages. Each mutating transition is claimed in memory first.
class PhoneTacoFlow {
  constructor(input, api) {
    this.api=api; this.phase='web'; this.serial=input.android_serial || '';
    this.email=(input.details.match(/^email:\s*(.+)$/mi)||[])[1]?.trim();
    this.plan=input.taco_plan;
    if(!this.email || !this.plan || !this.plan.location || !['venmo','gift_card'].includes(this.plan.payment_method)) throw Error('Choose Taco Bell pickup and payment on your phone before starting.');
  }
  async validate() {
    const d=await this.api('/api/adb?serial='+encodeURIComponent(this.serial));
    if(!d.ok)throw Error(d.message || 'Connect and authorize one Android device.');
    this.serial=d.serial;
  }
  post(path,body={}) {return this.api('/api/taco/'+path,{method:'POST',body:JSON.stringify({device_serial:this.serial,...body})})}
  async afterWeb() {
    this.phase='starting_android';
    await this.post('signin',{email:this.email});
    this.phase='android_code';
    return this.status();
  }
  status() {return {stage:'waiting_code',message:'Website signup finished. Enter the verification code sent for Taco Bell on Android.',codePhase:'android'}}
  async code(code) {
    this.phase='verifying_android';
    const s=await this.post('verify',{code});
    if(s.stage!=='signed_in'){this.phase='android_code';return { ...this.status(),message:s.message }}
    this.phase='preparing_checkout';
    await this.post('prepare',{plan:{...this.plan,checkout_confirmed:true}});
    const payment=await this.post('payment',{payment_method:this.plan.payment_method});
    if(!payment.payment_ready)throw Error(payment.message || 'Payment needs configuration on Android.');
    this.phase='submitting';
    const s=await this.post('submit',{payment_method:this.plan.payment_method,submit_confirmed:true});
    await this.post('reset',{previous_person_finished:true});
    this.phase='submission_attempted';
    return {stage:'complete',message:s.message + ' Order submitted and Android app data cleared automatically.'};
  }
  async submit() {
    if(this.phase!=='checkout_review')throw Error('This order is not waiting for review.');
    const current=await this.post('review');
    if(current.text!==this.reviewText)throw Error('Checkout changed after your review. Check the order on Android; it was not submitted.');
    this.phase='submitting';
    const s=await this.post('submit',{payment_method:this.plan.payment_method,submit_confirmed:true});
    this.phase='submission_attempted';
    return {stage:'attention',message:s.message + ' Submission was attempted once; success is not yet verified.'};
  }
}
if(typeof module!=='undefined')module.exports=PhoneTacoFlow;

