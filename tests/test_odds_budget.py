import tempfile,unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import requests
from topdown.odds_budget import OddsBudget,cadence
class BudgetTests(unittest.TestCase):
 def test_schedule(self):
  self.assertEqual(cadence([1100],1000),120);self.assertEqual(cadence([11000],1000),1800);self.assertEqual(cadence([],1000),21600)
 def test_cache_budget_and_restart(self):
  now=[1000];calls=[]
  def fetch(*a,**kw):
   calls.append(1);r=requests.Response();r.status_code=200;r._content=b'[{"last_update":"original"}]';return r
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'budget.sqlite';b=OddsBudget(path,limit=3,clock=lambda:now[0],fetch=fetch)
   self.assertEqual(b.get('https://test',{},{}).json()[0]['last_update'],'original')
   b=OddsBudget(path,limit=3,clock=lambda:now[0],fetch=fetch)
   b.get('https://test',{},{});self.assertEqual(len(calls),1)
   now[0]+=1801
   with self.assertRaises(requests.RequestException):b.get('https://test',{},{} )
   self.assertEqual(b.status()['reserved_credits'],3)
 def test_quota_response_pauses_other_endpoints(self):
  def fetch(*a,**kw):
   r=requests.Response();r.status_code=403;r._content=b'{}';return r
  with tempfile.TemporaryDirectory() as d:
   b=OddsBudget(Path(d)/'budget.sqlite',clock=lambda:1000,fetch=fetch)
   self.assertEqual(b.get('https://one',{},{}).status_code,403)
   with self.assertRaises(requests.RequestException):b.get('https://two',{},{} )
if __name__=='__main__':unittest.main()
