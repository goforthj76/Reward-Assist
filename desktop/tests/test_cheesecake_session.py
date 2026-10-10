import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cheesecake_session import CheesecakeSession
class SessionTests(unittest.TestCase):
 def setUp(self):
  self.s=CheesecakeSession();self.s.start({'password':'test-secret','email':'test@example.com'});self.id=self.s.task()['session_id']
 def test_claim_once_and_approval(self):
  self.assertFalse(self.s.update('claim_submit',self.id)['claimed'])
  self.s.update('review_required',self.id);self.s.approve()
  self.assertTrue(self.s.update('claim_submit',self.id)['claimed'])
  self.assertFalse(self.s.update('claim_submit',self.id)['claimed'])
  self.assertNotIn('details',self.s.task())
  self.assertEqual(self.s.status['stage'],'submitted')
 def test_code_requires_waiting(self):
  with self.assertRaises(ValueError):self.s.code('123456')
  self.s.update('waiting_code',self.id);self.s.code('123456')
  self.assertEqual(self.s.task()['code'],'123456')
  with self.assertRaises(ValueError):self.s.code('123')
 def test_old_status_and_expiry(self):
  self.assertTrue(self.s.update('attention','stale')['ignored'])
  self.s.expires=0;self.assertFalse(self.s.task()['active'])
  self.assertNotIn('test-secret',str(self.s.status))
 def test_attention_clears_secrets(self):
  self.s.update('attention',self.id);self.assertFalse(self.s.task()['active'])
if __name__=='__main__':unittest.main()
