(() => {
 if(window.__einsteinHelper)return;window.__einsteinHelper=true;
 const app='Einstein Bros. Bagels';
 const ask=m=>new Promise(resolve=>{try{chrome.runtime.sendMessage(m,r=>resolve(chrome.runtime.lastError?null:r))}catch{resolve(null)}});
 const visible=e=>e&&e.getClientRects().length>0;
 const inputs=()=>[...document.querySelectorAll('input')].filter(visible);
 const field=pattern=>inputs().find(e=>pattern.test([e.id,e.name,e.type,e.placeholder,e.getAttribute('aria-label'),...[...(e.labels||[])].map(l=>l.textContent)].join(' ')));
 function fill(e,v){if(!visible(e)||e.disabled)return false;if(e.value!==v){Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,v);for(const type of ['input','change','blur'])e.dispatchEvent(new Event(type,{bubbles:true}))}return e.value===v}
 const button=name=>[...document.querySelectorAll('button')].find(e=>visible(e)&&!e.disabled&&e.textContent.trim().toUpperCase()===name);
 let busy=false,session='',ticks=0;
 async function run(){if(busy)return;busy=true;try{
  const task=await ask({type:'task',app});if(!task?.active)return;
  if(session!==task.session_id){session=task.session_id;ticks=0}
  const report=stage=>ask({type:'status',payload:{app,session_id:session,stage}});
  const body=document.body?.innerText||'';
  if(++ticks>300){await report('attention');return}
  if(task.claims?.includes('claim_submit')){
   if((/Welcome!/.test(body)&&/Get ready for perks, points/.test(body))||(/My Rewards/.test(body)&&/Welcome: Free Bagel & Shmear w\/Purchase/.test(body)))await report('complete');
   else if(/already exists|unable to|something went wrong|invalid|please enter/i.test(body))await report('attention');
   return;
  }
  if(location.pathname!='/signup'){await report('attention');return}
  const d=task.details;if(!d)return;
  let ok=true;
  for(const [id,key] of [['formBasicFirstName','first_name'],['formBasicLastName','last_name'],['formBasicZipCode','zip_code']])ok=fill(document.getElementById(id),d[key])&&ok;
  ok=fill(field(/email/i),d.email)&&ok;
  const phone=field(/phone|tel/i);if(String(phone?.value||'').replace(/\D/g,'')!==d.phone)fill(phone,d.phone);
  ok=String(phone?.value||'').replace(/\D/g,'')===d.phone&&ok;
  const [y,m,day]=d.birthday.split('-');
  const date=new Date(Date.UTC(+y,+m-1,+day));
  if(date.getUTCFullYear()!==+y||date.getUTCMonth()!==+m-1||date.getUTCDate()!==+day){await report('attention');return}
  ok=fill(document.getElementById('formBasicDOB'),m+'/'+day+'/'+y)&&ok;
  const passwords=inputs().filter(e=>e.type==='password');
  if(passwords.length!==2)return;
  for(const e of passwords)ok=fill(e,d.password)&&ok;
  const join=button('JOIN NOW');if(!ok||!join)return;
  await report('review_required');
  if(task.approved&&(await report('claim_submit'))?.claimed)join.click();
 }finally{busy=false}}
 setInterval(()=>run().catch(()=>{}),1000);run().catch(()=>{});
})();
