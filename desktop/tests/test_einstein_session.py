import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from einstein_session import EinsteinSession
class Tests(unittest.TestCase):
 def setUp(self):
  self.s=EinsteinSession();self.s.start({'birthday':'2000-10-14','password':'Example123','email':'test@example.com'});self.id=self.s.task()['session_id']
 def test_approval_once_and_secret_removed(self):
  self.assertFalse(self.s.update('claim_submit',self.id)['claimed'])
  self.s.update('review_required',self.id);self.s.approve()
  self.assertTrue(self.s.update('claim_submit',self.id)['claimed'])
  self.assertFalse(self.s.update('claim_submit',self.id)['claimed'])
  self.assertNotIn('details',self.s.task())
  result=self.s.update('complete',self.id)
  self.assertNotIn('password',result['profile']);self.assertFalse(self.s.task()['active'])
  self.assertTrue(self.s.update('complete',self.id)['ignored'])
 def test_no_false_success_or_stale_completion(self):
  self.assertTrue(self.s.update('complete',self.id)['ignored'])
  self.assertTrue(self.s.update('complete','other')['ignored'])
 def test_bad_password(self):
  with self.assertRaises(ValueError):self.s.start({'birthday':'2000-10-14','password':'short'})
if __name__=='__main__':unittest.main()
