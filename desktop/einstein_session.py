"""Einstein signup: one approved submission, verified success, no saved password."""
from cheesecake_session import CheesecakeSession
import datetime as dt
import re

class EinsteinSession(CheesecakeSession):
    messages = {
        'waiting_extension': 'Opening Einstein Bros. Bagels. Enable the updated Chrome helper.',
        'review_required': 'Review your birthday and email, catering and SMS preferences in Chrome. Approving accepts Bagel Brands terms, including individual arbitration, and its privacy notice.',
        'submitted': 'Join Now clicked once. Waiting for Einstein signup confirmation.',
        'complete': 'Einstein confirmed signup. Account saved. Welcome reward requires a purchase.',
        'attention': 'Einstein needs attention in Chrome. Check validation or verification; signup will not be retried automatically.',
    }
    def start(self, details):
        date = dt.date.fromisoformat(details['birthday'])
        if date > dt.date.today(): raise ValueError('Birthday cannot be in the future.')
        password = details.get('password','')
        if len(password)<8 or not re.search('[A-Z]',password) or not re.search('[0-9]',password):
            raise ValueError('Einstein password needs at least 8 characters, an uppercase letter and a number.')
        super().start(details)
        self.profile = {k:v for k,v in details.items() if k!='password'}
    def stop(self):
        super().stop()
        self.profile = {}
    def update(self, stage, session_id):
        if stage in ('claim_phone','claim_code','waiting_code'): return {'ok':True,'ignored':True}
        if stage == 'complete':
            with self.lock:
                if not self.data.get('active') or session_id!=self.data.get('session_id') or 'claim_submit' not in self.data['claims']:
                    return {'ok':True,'ignored':True}
                profile=self.profile
                self.profile={}; self.data={}
                self.status={'stage':'complete','message':self.messages['complete']}
                return {'ok':True,'profile':profile}
        with self.lock:
            if 'claim_submit' in self.data.get('claims',[]) and stage=='review_required': return {'ok':True}
        result=super().update(stage,session_id)
        if stage=='attention' and not result.get('ignored'): self.profile={}
        return result
