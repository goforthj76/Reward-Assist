(() => {
const version='2026-10-12';
if(localStorage.getItem('rewardAssistFirstLaunchTermsAccepted')===version)return;
const dialog=document.createElement('dialog');
dialog.style.cssText='border:0;border-radius:24px;max-width:660px;width:calc(100% - 40px);padding:32px;color:#17243a;box-shadow:0 24px 100px #10213d55';
dialog.innerHTML='<p style="color:#167c84;letter-spacing:2px;font-size:12px;font-weight:bold">WELCOME TO REWARD ASSIST</p><h1 style="margin:8px 0">Before you begin</h1><p style="line-height:1.6">Please read our Terms of Use. Use authorized accounts, follow restaurant rules, and review the actions you ask the app to perform.</p><iframe title="Full Terms of Use" src="terms.html" style="width:100%;height:260px;border:1px solid #dde5ec;border-radius:12px"></iframe><p><a href="terms.html" target="_blank" rel="noopener">Read terms in a separate window ↗</a></p><label style="display:flex;gap:12px;line-height:1.5"><input type="checkbox"> I have read and agree to the Terms of Use.</label><button disabled style="margin-top:24px;width:100%;padding:15px;border:0;border-radius:12px;background:#14213d;color:white;font-weight:bold">Agree and continue</button><p style="font-size:12px;color:#637184">If you do not agree, close the app. Acceptance is saved on this device.</p>';
document.body.append(dialog);dialog.addEventListener('cancel',event=>event.preventDefault());
const checkbox=dialog.querySelector('input'),button=dialog.querySelector('button');
checkbox.onchange=()=>{button.disabled=!checkbox.checked;button.style.opacity=checkbox.checked?'1':'.45'};
button.style.opacity='.45';button.onclick=()=>{if(!checkbox.checked)return;localStorage.setItem('rewardAssistFirstLaunchTermsAccepted',version);dialog.close();dialog.remove()};dialog.showModal();
})();

