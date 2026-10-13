// Opt-in foreground companion. No shell commands or arbitrary URLs are accepted.
(() => {
  let enabled=false, busy=false, active=null;
  const device=localStorage.rewardAssistComputerID || crypto.randomUUID();
  localStorage.rewardAssistComputerID=device;
  const panel=document.createElement('section');
  panel.id='phoneConnectionPanel';
  panel.hidden=true;
  panel.innerHTML='<div class="phone-heading"><span class="phone-symbol">↔</span><div><p class="phone-eyebrow">YOUR PHONE + YOUR COMPUTER</p><h2>Connected, wherever you are.</h2><p>Start setup from your iPhone while this computer does the work.</p></div></div><div class="phone-steps"><article><b>01 · Sign in</b><p>Use the same Reward Assist account on both devices.</p></article><article><b>02 · Enable this computer</b><p>Finish any local task, then turn on phone requests below.</p></article><article><b>03 · Connect on iPhone</b><p>Computer → Sync accounts → Start a computer task. Match the computer ID shown here.</p></article></div><div class="phone-control"><label><input type="checkbox"> Allow phone requests</label><p>Computer ID: <strong class="computer-id"></strong></p><p>Remote Wake (Ethernet MAC): <strong class="computer-mac">Detecting…</strong></p><details class="wake-guide-details" style="margin-top:12px;background:#f3f6fa;border:1px solid #d3dee8;border-radius:10px;padding:12px 14px;font-size:13px;line-height:1.5;color:#243a53;"><summary style="font-weight:700;cursor:pointer;color:#0c5b52;">⚡ How to enable Remote Wake (Ethernet or Wi-Fi)</summary><div style="margin-top:10px;"><p><b>1. Motherboard BIOS (Required for both)</b>: Restart PC, tap <b>Del</b> or <b>F2</b> to enter BIOS. Under <i>Advanced → Wake Up Event Setup</i> (or APM Configuration), set <b>Resume By PCI-E Device</b> to <b>Enabled</b> and ensure <b>ErP Ready</b> is <b>Disabled</b>.</p><p style="margin-top:8px;"><b>2. If on Ethernet (Recommended)</b>: In Device Manager → Network adapters → your LAN card Properties → <i>Advanced</i>: set <b>WOL & Shutdown Link Speed</b> to <b>100 Mbps First</b> (or Not Speed Down) and <b>Green Ethernet</b> to <b>Disabled</b>. In <i>Power Management</i>, check <b>Allow this device to wake the computer</b>.</p><p style="margin-top:8px;"><b>3. If on Wi-Fi (WoWLAN)</b>: In Device Manager → Wi-Fi adapter Properties → <i>Power Management</i>: check <b>Allow this device to wake the computer</b>. In <i>Advanced</i>: enable <b>Wake on Magic Packet</b> & <b>WoWLAN</b>. Turn off Windows Fast Startup in Power Options.</p><p style="margin-top:8px;"><b>4. Auto-sign-in on Wake</b>: In Windows Settings → Accounts → Sign-in options, set <i>If you have been away, require sign-in</i> to <b>Never</b> so automation tasks proceed immediately without a password prompt.</p></div></details><small role="status" aria-live="polite"></small></div><p class="phone-footnote">Keep Reward Assist open and your computer awake. Android workflows need a USB-connected phone. Turning this off pauses new requests; a task already started may continue. Requests can submit signup forms. Use only authorized accounts.</p>';
  const nav=document.createElement('nav');nav.className='companion-tabs';nav.setAttribute('aria-label','Workspace');
  nav.innerHTML='<button type="button" aria-pressed="true">Rewards workspace</button><button type="button" aria-pressed="false">↔ Phone connection</button>';
  const workspace=document.querySelector('.shell');
  if(workspace){workspace.before(nav);workspace.after(panel)}else{document.body.prepend(nav);document.body.append(panel)}
  panel.querySelector('.computer-id').textContent=device.slice(0,8);
  api('/api/status').then(res=>{if(res&&res.mac){const m=panel.querySelector('.computer-mac');if(m)m.textContent=res.mac}}).catch(()=>{});
  nav.querySelectorAll('button').forEach((button,index)=>button.onclick=()=>{panel.hidden=index===0;if(workspace)workspace.hidden=index===1;nav.querySelectorAll('button').forEach((item,i)=>item.setAttribute('aria-pressed',String(i===index)))});
  const toggle=panel.querySelector('input'),status=panel.querySelector('small');
  toggle.onchange=()=>{enabled=toggle.checked;status.textContent=enabled?'Connecting…':'New requests paused. An already-started task may continue.';tick()};
  const call=(action,body={})=>cloudApi('/api/remote/'+action,{method:'POST',body:JSON.stringify({device,...body})});
  const recovery=document.createElement('button');recovery.textContent='Stop abandoned web tasks and clear queue';recovery.type='button';recovery.className='secondary';panel.querySelector('.phone-control').append(recovery);
  const configBtn=document.createElement('button');configBtn.textContent='⚡ Configure Android for sleep & automation';configBtn.type='button';configBtn.className='secondary';configBtn.style.marginTop='6px';panel.querySelector('.phone-control').append(configBtn);
  configBtn.onclick=async()=>{status.textContent='Configuring connected Android phone…';try{const res=await api('/api/system/configure-android',{method:'POST'});status.textContent=res.message||'Android configured!';}catch(e){status.textContent='Could not configure Android: '+e.message}};
  async function stopWeb(){for(const app of ['Nothing Bundt Cakes','The Cheesecake Factory','Taco Bell',"Wendy's"])await api('/api/web/cancel',{method:'POST',body:JSON.stringify({app})})}
  recovery.onclick=async()=>{
    if(busy){status.textContent='Wait for the current step to finish.';return}
    if(!confirm('Stop web automation and cancel queued requests? This does not undo accounts or orders already submitted.'))return;
    busy=true;
    try{const dutch=await api('/api/dutch/status');if(dutch.stage&&!['idle','complete','attention','error','failed','stopped'].includes(dutch.stage))throw Error('An Android helper is active. Finish it before recovery.');await stopWeb();const data=await cloudApi('/api/remote');for(const j of data.jobs.filter(j=>j.device===device&&['queued','starting','running','waiting_code','review_required'].includes(j.stage))){await call('cancel',{id:j.id});if(j.stage!=='queued')await call('update',{id:j.id,stage:'cancelled'})}active=null;status.textContent='Queue cleared. Check previous signup results before starting a new task.';}catch(e){status.textContent=e.message}finally{busy=false}
  };
  async function tick(){
    if(busy||(!enabled&&!active))return;
    if(!cloudKey){status.textContent='Sign in again to unlock the connection.';return}
    busy=true;
    try{
      if(enabled)await call('heartbeat');
      const remoteState=await cloudApi('/api/remote');
      if(active && remoteState.jobs.find(j=>j.id===active.id)?.cancel_requested){
        if(active.app==='Dutch Bros' || (active.taco && active.taco.phase!=='web')){status.textContent='Cancellation requested. Check and stop the Android task on the computer before clearing this request.';return}
        await api('/api/web/cancel',{method:'POST',body:JSON.stringify({app:active.app})});
        await call('update',{id:active.id,stage:'cancelled'});active=null;status.textContent='Task cancelled. Already-submitted actions are not undone.';return;
      }
      if(!active&&enabled){
        const data=remoteState;
        const abandoned=data.jobs.filter(j=>j.device===device&&['starting','running','waiting_code','review_required'].includes(j.stage));
        for(const j of abandoned.filter(j=>j.cancel_requested)){const d=await api('/api/dutch/status');if(d.stage&&!['idle','complete','attention','error','failed','stopped'].includes(d.stage))throw Error('Check the Android helper on the computer.');await stopWeb();await call('update',{id:j.id,stage:'cancelled'});return}
        if(data.jobs.some(j=>j.device===device&&['starting','running','waiting_code','review_required'].includes(j.stage))){status.textContent='An earlier task needs checking on this computer. It will not be restarted automatically.';return}
        const queued=data.jobs.find(j=>j.device===device&&j.stage==='queued');
        if(!queued){status.textContent='Ready · computer '+device.slice(0,8);return}
        const {job}=await call('claim',{id:queued.id});if(!job)return;
        try{
          const input=await cloudDecrypt(job.payload);
          if(!allowed.has(input.app)||typeof input.details!=='string'||input.details.length>20000||input.confirmed!==true)throw Error('Invalid phone request');
          const current=await api(input.app==='Dutch Bros'?'/api/dutch/status':'/api/web/status?app='+encodeURIComponent(input.app));
          if(current.stage && !['idle','complete','attention','error','failed','stopped'].includes(current.stage))throw Error('Finish the existing task on this computer first');
          active={id:job.id,app:input.app};
          if(input.app==='Taco Bell'){active.taco=new PhoneTacoFlow(input,api);await active.taco.validate()}
          const dutch=input.app==='Dutch Bros';
          await api(dutch?'/api/dutch/start':'/api/web/start',{method:'POST',body:JSON.stringify({app:input.app,details:input.details,...(dutch?{save_qr:true,terms_accepted:true}:{})})});
          await call('update',{id:job.id,stage:'running'});
        }catch(error){await call('update',{id:job.id,stage:'attention'});active=null;throw error}
      }
      if(active){
        let s=active.state || await api(active.app==='Dutch Bros'?'/api/dutch/status':'/api/web/status?app='+encodeURIComponent(active.app));
        if(active.taco && s.stage==='complete' && active.taco.phase==='web')s=active.state=await active.taco.afterWeb();
        const stage=s.stage==='complete'?'complete':s.stage==='waiting_code'?'waiting_code':['review_required','ready_for_review'].includes(s.stage)?'review_required':['attention','error','failed','stopped'].includes(s.stage)?'attention':'running';
        if(stage==='review_required' && !active.reviewNonce)active.reviewNonce=crypto.randomUUID();
        const payload=await cloudEncrypt({app:active.app,message:s.message||'',codePhase:s.codePhase||'website',reviewKind:s.reviewKind||'signup',reviewText:s.reviewText||'',nonce:active.reviewNonce||''});
        if(stage==='complete')await syncWindowsAccounts();
        await call('update',{id:active.id,stage,payload});status.textContent=active.app+' · '+(s.message||stage.replaceAll('_',' '));
        if(stage==='waiting_code'){
          const {payload}=await call('take-code',{id:active.id});
          if(payload){const command=await cloudDecrypt(payload);const code=command.code;if(!/^\d{4,8}$/.test(code))throw Error('Invalid code');
            if(command.codePhase && command.codePhase!==(s.codePhase||'website'))throw Error('This code belongs to an earlier step.');
            if(active.taco?.phase==='android_code')active.state=await active.taco.code(code);
            else await api(active.app==='Dutch Bros'?'/api/dutch/code':'/api/web/code',{method:'POST',body:JSON.stringify({app:active.app,code})});
          }
        }
        if(stage==='review_required'){
          const {payload}=await call('take-approval',{id:active.id});
          if(payload){const command=await cloudDecrypt(payload);
            if(command.accepted!==true||command.nonce!==active.reviewNonce)throw Error('The review changed. Review it again on your phone.');
            active.reviewNonce=null;
            if(active.taco?.phase==='checkout_review')active.state=await active.taco.submit();
            else if(s.stage==='review_required')await api('/api/web/approve',{method:'POST',body:JSON.stringify({app:active.app})});
            else throw Error('This step needs attention on the host device.');
          }
        }
        if(['complete','attention'].includes(stage)){active=null}
      }
    }catch(error){status.textContent='Connection needs attention: '+error.message;if(active){active.state={stage:'attention',message:error.message};try{await call('update',{id:active.id,stage:'attention',payload:await cloudEncrypt({app:active.app,message:error.message})});active=null}catch{}}}
    finally{busy=false}
  }
  setInterval(tick,5000);
})();
