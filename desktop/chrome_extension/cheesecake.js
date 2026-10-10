(() => {
 if(window.__cheesecakeHelper) return; window.__cheesecakeHelper=true;
 const app='The Cheesecake Factory';
 const ask=m=>new Promise(resolve=>{try{chrome.runtime.sendMessage(m,r=>resolve(chrome.runtime.lastError?null:r))}catch{resolve(null)}});
 const visible=e=>e&&e.getClientRects().length>0;
 const buttons=()=>[...document.querySelectorAll('button')].filter(visible);
 const button=label=>buttons().find(e=>e.textContent.trim().toUpperCase()===label&&!e.disabled);
 const input=id=>document.getElementById(id);
 function fill(e,value){if(!visible(e)||e.disabled)return false;if(e.value!==value){Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,value);for(const type of ['input','change','blur'])e.dispatchEvent(new Event(type,{bubbles:true}))}return e.value===value}
 let busy=false,session='',ticks=0,searchStarted=false,locationOpened=false;
 async function run(){if(busy)return;busy=true;try{
  const task=await ask({type:'task',app});if(!task?.active)return;
  if(session!==task.session_id){session=task.session_id;ticks=0;searchStarted=false;locationOpened=false}
  const report=stage=>ask({type:'status',payload:{app,session_id:session,stage}});
  const body=document.body.innerText;
  if(/Http failure response|something went wrong|invalid verification code|code has expired/i.test(body)){await report('attention');return}
  if(task.claims?.includes('claim_submit'))return;
  if(++ticks>600){await report('attention');return}
  const d=task.details;if(!d)return;
  const textMe=button('TEXT ME');
  if(textMe||/Enter the mobile phone number you want to use/.test(body)){
    const fields=[...document.querySelectorAll('input')].filter(e=>visible(e)&&!e.disabled&&['text','tel','number'].includes(e.type));
    if(fields.length!==1)return;
    const phone=fields[0], digits=value=>String(value||'').replace(/\D/g,'');
    if(digits(phone.value)!==digits(d.phone))fill(phone,d.phone);
    if(digits(phone.value)===digits(d.phone)){const btn=button('TEXT ME');if(btn&&(await report('claim_phone'))?.claimed)btn.click()}
    return;
  }
  if(/Enter Your Code/.test(body)){
    await report('waiting_code');
    const e=document.querySelector('input[placeholder="Enter 6-Digit Code"]');
    if(task.code&&fill(e,task.code)){const btn=button('CONTINUE');if(btn&&(await report('claim_code'))?.claimed)btn.click()}
    return;
  }
  if(!visible(input('first-name')))return;
  await report('filling_details');
  let ok=true;
  for(const [id,key] of [['first-name','first_name'],['last-name','last_name'],['email','email'],['zip','zip_code'],['password','password'],['password-confirmation','password']])ok=fill(input(id),d[key])&&ok;
  const date=d.birthday.split('-');ok=fill(input('birthday'),`${date[1]}/${date[2]}/${date[0]}`)&&ok;
  const search=input('locationSearch');
  if(visible(search)){
    if(!searchStarted){fill(search,d.zip_code);searchStarted=true;return}
    const suggestion=buttons().find(e=>e.textContent.trim().startsWith(d.zip_code+',')&&!e.disabled);
    if(suggestion){suggestion.click();return}
    const match=buttons().find(e=>e.id===d.restaurant&&!e.disabled);
    if(match){match.click();return}
    if(/No nearby locations found/.test(body)&&ticks>30){await report('attention')}
    return;
  }
  const favorite=buttons().find(e=>e.textContent.trim().toLowerCase()===d.restaurant.toLowerCase());
  if(!favorite){const add=button('ADD FAVORITE RESTAURANT*');if(add&&!locationOpened){locationOpened=true;add.click()}return}
  if(!ok)return;
  await report('review_required');
  if(!task.approved)return;
  const terms=input('terms_and_conditions');if(!visible(terms))return;
  if(!terms.checked)terms.click();if(!terms.checked)return;
  const signup=buttons().find(e=>e.textContent.trim()==='SIGN UP'&&!e.disabled&&e.getBoundingClientRect().top>terms.getBoundingClientRect().top);
  if(signup&&(await report('claim_submit'))?.claimed)signup.click();
 }finally{busy=false}}
 setInterval(()=>run().catch(()=>{}),1000);run().catch(()=>{});
})();
