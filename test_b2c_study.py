import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from b2c_volume_redk_study import b_morphology, locate_events, evaluate


def sample(candle_spike=True):
    dates=pd.bdate_range('2026-04-01',periods=165)
    p=np.ones(len(dates))*101.
    p[0:60]=101
    p[60:68]=np.linspace(98,60,8)
    p[68:74]=np.linspace(62,84,6)
    p[74:82]=[82,81,80,78,76,74,72,73]
    p[82:88]=[73,73,74,74,75,75]
    p[88]=80 if candle_spike else 75
    p[89:]=np.linspace(82,110,len(dates)-89) if candle_spike else 75
    op=p.copy();op[88]=76 if candle_spike else 74
    vol=np.ones(len(dates))*1e6;vol[88]=3.0e6
    d=pd.DataFrame(dict(date=dates,open=op,high=np.maximum(op,p)+1,
                low=np.minimum(op,p)-1,close=p,volume=vol))
    return d


class MorphTests(unittest.TestCase):
    def test_lows_no_future(self):
        d=pd.DataFrame({'high':[11,10.5,10.4,11,10.8,10.3],
                        'low':[10,9.8,9.7,10,9.9,9.6],
                        'volume':[100]*6})
        self.assertIn(b_morphology(d),
                      {'INSUFFICIENT','SHORT_B_V','OTHER','HIGHER_LOW','W_DOUBLE_BOTTOM'})

    def test_later_future_does_not_change_past_signal(self):
        d=sample(True)
        args=('2026-06-01','2026-07-31','2026-06-01','2026-08-15',1e7)
        a,_,_=locate_events('6456',d.iloc[:100],*args)
        b,_,_=locate_events('6456',d,*args)
        self.assertTrue(a)
        self.assertEqual([(r['trigger'],r['signal_date']) for r in a],
                         [(r['trigger'],r['signal_date']) for r in b])
        self.assertTrue(all(r['red_candle'] for r in b))

    def test_stop_and_next_open(self):
        d=sample(True)
        a,_,enriched=locate_events('6456',d,'2026-06-01','2026-07-31',
                                   '2026-06-01','2026-08-15',1e7)
        ev=a[0];i=ev['signal_index']
        self.assertEqual(ev['signal_date'],str(d.loc[i,'date'].date()))
        result=evaluate(enriched,ev,10)
        self.assertIsNotNone(result)
        self.assertEqual(result['entry'],float(d.iloc[i+1].open))
        self.assertIsNone(evaluate(enriched,ev,len(d)))

    def test_not_trigger_without_big_volume(self):
        d=sample(True)
        d.loc[88,'volume']=1e6
        events,_,_=locate_events('6456',d,'2026-06-01','2026-07-31',
                                 '2026-06-01','2026-08-15',1e7)
        self.assertEqual(events,[])


if __name__=='__main__':unittest.main()
