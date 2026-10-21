import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from b_wave_breakout import inspect_symbol, trade, fivewave_proxy, summarize

class ModelTests(unittest.TestCase):
    def test_flat_stock_has_no_signal(self):
        date=pd.bdate_range('2025-11-03',periods=170)
        px=np.linspace(100,104,170)
        d=pd.DataFrame(dict(date=date,open=px,high=px*1.01,
                            low=px*.99,close=px,volume=1000000))
        row,events,_=inspect_symbol('2330',d,np.datetime64('2026-06-01'),
                         np.datetime64('2026-08-31'),1e7)
        self.assertEqual(row['stage'],'NO_PATTERN')
        self.assertEqual(events,[])
        self.assertFalse(row['actionable_buy'])

    def test_no_future_data_or_unmatured_trade(self):
        n=100;dt=pd.bdate_range('2026-05-01',periods=n)
        d=pd.DataFrame(dict(date=dt,open=[100.0]*n,high=[102.0]*n,
                            low=[99.0]*n,close=[100.0]*n,volume=[1000000]*n,
                            ma20=[100.0]*n,ma60=[100.0]*n))
        e=dict(signal_index=90,b_low=95.,a_high=110.,bottom=75.,symbol='2330',
               signal_type='B_上緣突破',signal_date=dt[90].date().isoformat(),
               quality_hypothesis=False)
        self.assertIsNone(trade(d,e,10))
        self.assertIsNotNone(trade(d,e,5))

    def test_next_day_gap_stop_uses_open(self):
        n=100;date=pd.bdate_range('2026-04-01',periods=n)
        d=pd.DataFrame(dict(date=date,open=[100.]*n,high=[101.]*n,
                            low=[99.]*n,close=[100.]*n,volume=[1000000]*n,
                            ma20=[100.]*n,ma60=[100.]*n))
        d.loc[72,'open']=88.;d.loc[72,'low']=86.;d.loc[72,'high']=90.
        e=dict(signal_index=70,b_low=96.,a_high=110.,bottom=75.,symbol='2330',
               signal_type='B_上緣突破',signal_date=date[70].date().isoformat())
        result=trade(d,e,5)
        self.assertEqual(result['entry'],100.)
        self.assertEqual(result['exit'],88.)
        self.assertEqual(result['exit_reason'],'跳空停損')

    def test_trailing_stop_not_updated_using_current_day_high(self):
        n=110;date=pd.bdate_range('2026-04-01',periods=n)
        d=pd.DataFrame(dict(date=date,open=[100.]*n,high=[101.]*n,
                            low=[99.]*n,close=[100.]*n,volume=[1000000]*n,
                            ma20=[100.]*n,ma60=[100.]*n))
        d.loc[72,'open']=100.;d.loc[72,'high']=112.;d.loc[72,'low']=100.;d.loc[72,'close']=111.
        d.loc[73,'open']=111.;d.loc[73,'high']=111.;d.loc[73,'low']=100.;d.loc[73,'close']=106.
        e=dict(signal_index=70,b_low=95.,a_high=110.,bottom=75.,symbol='2330',
               signal_type='B_上緣突破',signal_date=date[70].date().isoformat())
        result=trade(d,e,20,'runner')
        # After closing above 110, next day's stop should move to at least 100.5.
        self.assertAlmostEqual(result['exit'],100.5,places=5)
        self.assertEqual(result['exit_reason'],'移動停損')

    def test_smooth_trend_is_not_five_oscillations(self):
        q=pd.DataFrame(dict(high=np.linspace(20,30,40),low=np.linspace(19,29,40)))
        self.assertFalse(fivewave_proxy(q,0,39,18))

    def test_failed_breakout_can_recover_without_auto_buy(self):
        # 僅使用歷史可觀察價格，確保失敗後重新跨越A高不再永久FAILED。
        p=np.full(160,100.)
        p[55:65]=101.
        p[65:69]=[65,64,62,60]
        p[69:72]=[62,67,72]
        p[72:78]=[75,77,79,79,78,79]
        p[78:90]=[74,73,72,71,72,73,71,70,71,72,73,74]
        p[90:94]=[76,78,80,84]
        p[94:100]=[81,79,78,77,77,76]
        p[100]=66
        p[101:111]=np.linspace(70,83,10)
        p[111:]=np.linspace(85,100,49)
        dates=pd.bdate_range('2026-04-01',periods=160)
        d=pd.DataFrame(dict(date=dates,open=p,high=p+1,low=p-1,close=p,
                            volume=np.ones(160)*1000000))
        failed,_,_=inspect_symbol('6456',d.iloc[:105],np.datetime64('2026-06-01'),
                                  np.datetime64('2026-08-31'),1e7)
        recovered,_,_=inspect_symbol('6456',d.iloc[:117],np.datetime64('2026-06-01'),
                                     np.datetime64('2026-08-31'),1e7)
        self.assertEqual(failed['stage'],'FAILED')
        self.assertEqual(recovered['stage'],'R_RUN')
        self.assertTrue(recovered['recovered_after_failure'])
        self.assertFalse(recovered['actionable_buy'])

if __name__=='__main__':unittest.main()
