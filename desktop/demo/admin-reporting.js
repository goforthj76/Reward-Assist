const diagnosticStages=new Set(['started','waiting_code','filling_details','review_required','complete','attention','android_signin','checkout','payment','review','stopped']);
let diagnosticRun=null;
function diagnosticsEnabled(){return localStorage.getItem('requiredDiagnosticsNoticeV1')==='accepted'}
function acknowledgeDiagnostics(){
 if(diagnosticsEnabled())return true;
 if(!confirm('Guided setup requires basic diagnostic reporting. Reward Assist sends the restaurant program, app version, run ID, timestamps and workflow stage, linked to your account, through Cloudflare for the administrator to review. Reports cover the last 90 days. Passwords, verification codes, payment details and raw messages are excluded. Continue with reporting?'))return false;
 localStorage.setItem('requiredDiagnosticsNoticeV1','accepted');return true;
}
async function reportDiagnostic(stage){
 if(!diagnosticsEnabled()||!diagnosticRun||!diagnosticStages.has(stage)||diagnosticRun.last===stage)return;
 const run=diagnosticRun;
 try{await cloudApi('/api/reports',{method:'POST',body:JSON.stringify({run_id:run.id,program:run.program,version:document.getElementById('buildVersion').textContent.replace('LOCAL BETA v',''),stage})});run.last=stage}catch{}
}
const diagnosticApi=api;
api=async function(path,options={}){
 if(['/api/web/start','/api/dutch/start','/api/paris/start'].includes(path)&&!acknowledgeDiagnostics())throw new Error('Setup was not started. Basic diagnostic reporting is required to use guided setup.');
 let payload={};try{payload=JSON.parse(options.body||'{}')}catch{}
 try{
 const result=await diagnosticApi(path,options);
 if(['/api/web/start','/api/dutch/start','/api/paris/start'].includes(path)&&diagnosticsEnabled()){
 diagnosticRun={id:crypto.randomUUID(),program:payload.app||(path.includes('dutch')?'Dutch Bros':'Paris Baguette'),last:''};void reportDiagnostic('started');
 }else if(path.includes('/status')&&result.stage){void reportDiagnostic(result.stage)}
 else if(path==='/api/taco/signin')void reportDiagnostic('android_signin');
 else if(path==='/api/taco/prepare')void reportDiagnostic('checkout');
 else if(path==='/api/taco/payment')void reportDiagnostic('payment');
 else if(path==='/api/web/cancel')void reportDiagnostic('stopped');
 return result;
 }catch(error){if(diagnosticRun&&options.method==='POST')void reportDiagnostic('attention');throw error}
};
showAdminPanel=async function(){
 document.getElementById('modalTitle').textContent='Admin dashboard';
 const body=document.getElementById('modalBody');body.textContent='Loading statistics…';document.getElementById('overlay').classList.add('show');
 try{const cloud=await cloudApi('/api/admin/stats');
 body.innerHTML='<p>Required diagnostics · last 90 days. Counts cover reported runs only. “Complete” means the signup helper reported completion, not a confirmed restaurant order. A last step may be a normal wait or a closed app, not necessarily a failure.</p>'+['users','synced_vaults','active_sessions'].map(k=>'<div class="credential"><small>'+esc(k.replaceAll('_',' '))+'</small><strong>'+esc(String(cloud.totals?.[k]??'Unavailable'))+'</strong></div>').join('')+'<h3>Runs by last reported step</h3>'+(cloud.summary?.length?cloud.summary.map(r=>'<p>'+esc(r.program)+' · '+esc(r.stage)+' · '+Number(r.count)+' runs</p>').join(''):'<p>No diagnostic reports yet. Reports appear after users acknowledge the reporting notice and start guided setup in the updated app.</p>')+'<h3>Recent runs</h3>'+(cloud.runs||[]).map(r=>'<p>'+esc(r.program)+' · '+esc(r.stage)+' · v'+esc(r.version)+' · '+esc(new Date(r.updated_at).toLocaleString())+'</p>').join('')+'<h3>Registered users</h3>'+(cloud.users||[]).map(u=>'<p>'+esc(u.email)+'</p>').join('');
 }catch(error){body.textContent='Could not load admin statistics: '+error.message}
};
const diagnosticControl=document.createElement('section');diagnosticControl.style.cssText='padding:16px;margin:16px;border:1px solid #d8e0ef;border-radius:12px';
diagnosticControl.innerHTML='<strong>Required diagnostic reporting</strong><p>Guided setup sends program, version, run ID, timestamps and stage, associated with your account, to Reward Assist through Cloudflare. Reports cover 90 days. Passwords, codes, payments and raw messages are excluded.</p>';document.querySelector('main')?.append(diagnosticControl);

