import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sweetfrog_session import SweetFrogSession

class SweetFrogTests(unittest.TestCase):
    def setUp(self):
        self.s = SweetFrogSession()
        self.s.start({'birthday':'1990-10-21','phone':'2025550100','email':'test@example.com'})
        self.id = self.s.task()['session_id']
    def step(self, stage): return self.s.update(stage,self.id)
    def test_each_consent_and_submission_is_separate(self):
        self.assertFalse(self.step('claim_phone')['claimed'])
        self.step('review_phone'); self.s.approve()
        self.assertTrue(self.step('claim_phone')['claimed'])
        self.assertFalse(self.step('claim_phone')['claimed'])
        self.step('waiting_code');self.s.code('123456')
        self.assertTrue(self.step('claim_code')['claimed'])
        self.assertEqual(self.s.task()['code'],'')
        self.step('review_profile')
        self.assertFalse(self.step('claim_submit')['claimed'])
        self.s.approve()
        self.assertTrue(self.step('claim_submit')['claimed'])
        self.assertFalse(self.step('claim_submit')['claimed'])
        self.assertIn('profile',self.step('complete'))
        self.assertNotIn('profile',self.step('complete'))
        self.assertFalse(self.s.task()['active'])
    def test_existing_rewards_page_is_not_success(self):
        self.assertTrue(self.step('complete')['ignored'])
        self.assertNotEqual(self.s.status['stage'],'complete')
    def test_stale_session_cannot_change_state(self):
        self.assertTrue(self.s.update('attention','other-session')['ignored'])
        self.assertTrue(self.s.task()['active'])
    def test_failure_and_expiry_clear_details(self):
        self.step('attention');self.assertNotIn('details',self.s.task())
        self.setUp();self.s.expires=0
        self.assertFalse(self.s.task()['active'])
    def test_birthday_validation(self):
        for birthday in ['2025-01-01','1990-02-31']:
            with self.assertRaises(ValueError): self.s.start({'birthday':birthday})

if __name__ == '__main__': unittest.main()
