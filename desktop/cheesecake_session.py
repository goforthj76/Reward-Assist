"""Short-lived Cheesecake Factory signup session; secrets never written to disk."""
import copy
import re
import threading
import time
import uuid

class CheesecakeSession:
    messages = {
        'waiting_extension': 'Opening Cheesecake Factory. Enable the updated Chrome helper if nothing happens.',
        'waiting_code': 'Enter the six-digit SMS code below. The website handles resend requests.',
        'filling_details': 'Filling the verified profile and selecting the favorite restaurant.',
        'review_required': 'Review Cheesecake Factory terms in Chrome. Enrollment includes promotional email/SMS. Then click the approval button below.',
        'submitted': 'Sign Up was clicked once. Check Chrome for the result; completion is not confirmed automatically yet.',
        'attention': 'Cheesecake Factory could not complete this step. Check the visible error or verification in Chrome. No automatic retry.',
    }
    def __init__(self):
        self.lock = threading.Lock()
        self.data = {}
        self.status = {'stage':'idle','message':'Start Cheesecake Factory setup first.'}
        self.expires = 0
    def start(self, details):
        with self.lock:
            self.data = {'active':True,'session_id':uuid.uuid4().hex,'details':dict(details),'code':'','approved':False,'claims':[]}
            self.expires = time.monotonic()+1800
            self.status = {'stage':'waiting_extension','message':self.messages['waiting_extension']}
    def task(self):
        with self.lock:
            if self.data and time.monotonic() > self.expires:
                self.data = {}
                self.status = {'stage':'attention','message':'Signup session expired. Check Chrome before starting again.'}
            return copy.deepcopy(self.data or {'active':False})
    def update(self, stage, session_id):
        with self.lock:
            if session_id != self.data.get('session_id') or not self.data.get('active'):
                return {'ok':True,'ignored':True}
            if stage in ('claim_phone','claim_code','claim_submit'):
                if stage in self.data['claims'] or (stage=='claim_submit' and not self.data['approved']):
                    return {'claimed':False}
                self.data['claims'].append(stage)
                if stage=='claim_submit':
                    self.data.pop('details',None)
                    self.data['code']=''
                    self.status={'stage':'submitted','message':self.messages['submitted']}
                return {'claimed':True}
            if stage in self.messages:
                self.status={'stage':stage,'message':self.messages[stage]}
                if stage=='attention':self.data={}
            return {'ok':True}
    def code(self, code):
        if not re.fullmatch(r'\d{6}',code):raise ValueError('Enter the six-digit SMS code.')
        with self.lock:
            if not self.data.get('active') or self.status['stage']!='waiting_code':raise ValueError('Wait for the SMS code screen first.')
            self.data['code']=code
            self.data['claims']=[x for x in self.data['claims'] if x!='claim_code']
    def approve(self):
        with self.lock:
            if not self.data.get('active') or self.status['stage']!='review_required':raise ValueError('Wait for the completed form and review its terms first.')
            self.data['approved']=True
    def stop(self):
        with self.lock:self.data={}
