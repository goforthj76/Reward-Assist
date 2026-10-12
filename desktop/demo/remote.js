// Opt-in foreground companion. No shell commands or arbitrary URLs are accepted.
(() => {
  let enabled=false, busy=false, active=null;
  const device=localStorage.rewardAssistComputerID || crypto.randomUUID();
  localStorage.rewardAssistComputerID=device;
  const panel=document.createElement('section');
  panel.style.cssText='padding:16px;margin:16px;border:1px solid #ccd6e4;border-radius:12px';
  panel.innerHTML='<h3>Phone requests</h3><label><input type="checkbox"> Allow my phone to start account setup on this computer</label><p>Keep this app open. Finish any local task before enabling. Phone requests can submit signup forms; use only accounts you are authorized to create.</p><small></small>';
  document.body.append(panel);
  const toggle=panel.querySelector('input'),status=panel.querySelector('small');
  toggle.onchange=()=>{enabled=toggle.checked;status.textContent=enabled?'Connecting…':'New requests paused. An already-started task may continue.';tick()};
  const call=(action,body={})=>cloudApi('/api/remote/'+action,{method:'POST',body:JSON.stringify({device,...body})});
  const allowed=new Set(['Nothing Bundt Cakes','The Cheesecake Factory','Taco Bell','Dutch Bros']);
  async function tick(){
    if(busy||(!enabled&&!active))return;
    if(!cloudKey){status.textContent='Sign in again to unlock the connection.';return}
    busy=true;
    try{
      if(enabled)await call('heartbeat');
      if(!active&&enabled){
        const data=await cloudApi('/api/remote');
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
          const dutch=input.app==='Dutch Bros';
          await api(dutch?'/api/dutch/start':'/api/web/start',{method:'POST',body:JSON.stringify({app:input.app,details:input.details,...(dutch?{save_qr:true,terms_accepted:true}:{})})});
          await call('update',{id:job.id,stage:'running'});
        }catch(error){await call('update',{id:job.id,stage:'attention'});active=null;throw error}
      }
      if(active){
        const s=await api(active.app==='Dutch Bros'?'/api/dutch/status':'/api/web/status?app='+encodeURIComponent(active.app));
        const stage=s.stage==='complete'?'complete':s.stage==='waiting_code'?'waiting_code':['review_required','ready_for_review'].includes(s.stage)?'review_required':['attention','error','failed','stopped'].includes(s.stage)?'attention':'running';
        await call('update',{id:active.id,stage});status.textContent=active.app+' · '+stage.replaceAll('_',' ');
        if(stage==='waiting_code'){
          const {payload}=await call('take-code',{id:active.id});
          if(payload){const {code}=await cloudDecrypt(payload);if(!/^\d{4,8}$/.test(code))throw Error('Invalid code');await api(active.app==='Dutch Bros'?'/api/dutch/code':'/api/web/code',{method:'POST',body:JSON.stringify({app:active.app,code})})}
        }
        if(['complete','attention'].includes(stage)){active=null;if(stage==='complete')await syncWindowsAccounts()}
      }
    }catch(error){status.textContent='Connection needs attention: '+error.message}
    finally{busy=false}
  }
  setInterval(tick,5000);
})();
