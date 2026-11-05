import unittest
from datetime import datetime, timedelta, timezone
from collect import cutoff, classify, seconds, collect_channel

NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)
def channel(views):
    return dict(complete=True, videos=[dict(id=str(i), kind='long', views=n, published=(NOW-timedelta(days=10)).isoformat()) for i,n in enumerate(views)])

class Tests(unittest.TestCase):
    def test_thresholds_and_self_inclusion(self):
        c=classify(channel([300,50,50,100,0]), NOW)
        self.assertEqual(c['videos'][0]['average'],100)
        self.assertEqual([v['label'] for v in c['videos']],['고성과','저성과','저성과','일반','저성과'])
    def test_zero(self):
        self.assertEqual(classify(channel([0,0]), NOW)['videos'][0]['label'],'보류')
    def test_missing(self):
        self.assertIsNone(classify(channel([100,None]), NOW)['videos'][0]['average'])
    def test_incomplete(self):
        c=channel([300,1]);c['complete']=False
        self.assertIsNone(classify(c,NOW)['videos'][0]['ratio'])
    def test_format_unknown_blocks_mean(self):
        c=channel([300,1]);c['videos'][1]['kind']='unknown'
        self.assertIsNone(classify(c,NOW)['videos'][0]['average'])
        self.assertEqual(classify(c,NOW,{'1':'short'})['videos'][0]['average'],300)
    def test_new_video_excluded(self):
        c=channel([100,900]);c['videos'][1]['published']=(NOW-timedelta(days=6)).isoformat()
        self.assertEqual(classify(c,NOW)['videos'][0]['average'],100)
    def test_boundaries(self):
        c=channel([100,300]);c['videos'][1]['published']=(NOW-timedelta(days=7)).isoformat()
        self.assertEqual(classify(c,NOW)['videos'][0]['average'],200)
    def test_calendar_months(self):
        self.assertEqual(cutoff(datetime(2026,5,31,tzinfo=timezone.utc)).day,28)
    def test_duration(self):
        self.assertEqual(seconds('PT3M1S'),181)
        self.assertIsNone(seconds('bad'))
    def test_api_failure_keeps_partial(self):
        class Broken:
            def get(self,*args,**kwargs):raise RuntimeError('한도 도달')
        c=collect_channel(Broken(),'@x',NOW)
        self.assertFalse(c['complete']);self.assertEqual(c['issues'],['한도 도달'])

if __name__=='__main__':unittest.main()