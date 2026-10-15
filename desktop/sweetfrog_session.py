"""Memory-only sweetFrog signup with distinct consent and one-shot actions."""
from cheesecake_session import CheesecakeSession
import datetime as dt
import copy


class SweetFrogSession(CheesecakeSession):
    messages = {
        'waiting_extension': 'Opening sweetFrog. Enable the updated Chrome helper.',
        'waiting_code': 'Enter the six-digit sweetFrog SMS code. Resend is available on the official page.',
        'filling_details': 'Checking birthday, profile and participating favorite store.',
        'submitted': 'Profile submitted once. Waiting for the sweetFrog rewards page.',
        'complete': 'sweetFrog rewards page confirmed. Account saved locally.',
        'attention': 'sweetFrog needs attention in Chrome. No automatic resubmission.',
    }

    def start(self, details):
        birthday = dt.date.fromisoformat(details['birthday'])
        today = dt.date.today()
        age = today.year-birthday.year-((today.month,today.day)<(birthday.month,birthday.day))
        if age < 13: raise ValueError('sweetFrog requires age 13 or older.')
        super().start(details)
        self.phase = ''

    def update(self, stage, session_id):
        with self.lock:
            if session_id != self.data.get('session_id') or not self.data.get('active'):
                return {'ok': True, 'ignored': True}
            claims = self.data['claims']
            if stage in ('review_phone', 'review_profile'):
                phase = stage.removeprefix('review_')
                if (phase == 'phone' and 'claim_phone' in claims) or 'claim_submit' in claims:
                    return {'ok': True}
                if phase == 'profile' and 'claim_code' not in claims:
                    return {'ok': True, 'ignored': True}
                if self.phase != phase: self.data['approved'] = False
                self.phase = phase
                message = ('Review sweetFrog terms in Chrome, then approve requesting the signup SMS.' if phase == 'phone'
                           else 'Review your birthday, selected store, email/SMS preferences and Spendgo terms in Chrome, then approve signup.')
                self.status = {'stage': 'review_required', 'message': message, 'reviewText': message}
                return {'ok': True}
            if stage in ('claim_phone', 'claim_code', 'claim_submit'):
                valid = (stage == 'claim_phone' and self.phase == 'phone' and self.data['approved']
                         or stage == 'claim_code' and self.status['stage'] == 'waiting_code' and bool(self.data['code'])
                         or stage == 'claim_submit' and self.phase == 'profile' and self.data['approved'])
                if stage in claims or not valid: return {'claimed': False}
                claims.append(stage)
                if stage == 'claim_code': self.data['code'] = ''
                if stage == 'claim_phone': self.data['approved'] = False
                if stage == 'claim_submit': self.status = {'stage':'submitted','message':self.messages['submitted']}
                return {'claimed': True}
            if stage == 'complete':
                if 'claim_submit' not in claims: return {'ok':True,'ignored':True}
                profile = copy.deepcopy(self.data['details'])
                self.data = {}
                self.status = {'stage':'complete','message':self.messages['complete']}
                return {'ok':True,'profile':profile}
            if stage in self.messages:
                if stage == 'filling_details' and 'claim_submit' in claims: return {'ok':True}
                self.status = {'stage':stage,'message':self.messages[stage]}
                if stage == 'attention': self.data = {}
            return {'ok':True}
