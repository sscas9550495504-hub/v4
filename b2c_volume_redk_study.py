#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026 六七月崩盤後的 B→C 放量紅K / B形態事件研究。

訊號只使用當日收盤以前已知的資訊；隔日開盤進場。四個訊號規格在每個
B波週期各觸發至多一次；結果不是互相獨立的交易組合績效。
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from market_abc_core import get_data, enrich, COST_BUY, COST_SELL

TRIGGERS = ('VOL_RED', 'STRONG_RED', 'RECLAIM_3H', 'BREAK_B10')
HORIZONS = (5, 10, 20, 40)


def fmt(v):
    try:
        a=float(v)
        return a if np.isfinite(a) else np.nan
    except (TypeError, ValueError):
        return np.nan


def b_morphology(bars):
    """全部在觸發日以前的 B 波 K 線判斷形態；局部低點需2根右側K確認。"""
    if len(bars)<5:
        return 'INSUFFICIENT'
    hi=bars.high.to_numpy(float);lo=bars.low.to_numpy(float)
    vols=bars.volume.to_numpy(float)
    piv=[]
    for j in range(2,len(bars)-2):
        if lo[j]<min(lo[j-2],lo[j-1],lo[j+1],lo[j+2]):
            piv.append((j,lo[j]))
    for k in range(len(piv)-1):
        a,la=piv[k]
        for l in range(k+1,len(piv)):
            b,lb=piv[l]
            if b-a<4:continue
            mid=max(hi[a:b+1])
            if abs(lb/la-1)<=.05 and mid/max(la,lb)-1>=.07:
                return 'W_DOUBLE_BOTTOM'
            if lb/la>=1.03 and mid/la-1>=.06:
                return 'HIGHER_LOW'
    if len(bars)>=10:
        left,right=bars.iloc[-10:-5],bars.iloc[-5:]
        range_left=left.high.max()-left.low.min()
        range_right=right.high.max()-right.low.min()
        narrower=(range_left>0 and range_right/range_left<=.70)
        higher_lows=right.low.min()>left.low.min()
        lower_highs=right.high.max()<left.high.max()
        if narrower and higher_lows and lower_highs:return 'CONTRACTING_TRIANGLE'
        box=(bars.iloc[-10:].high.max()/bars.iloc[-10:].low.min()-1)
        if box<=.12 and fmt(np.nanmean(vols[-5:]))<=fmt(np.nanmean(vols[-10:-5]))*1.10:
            return 'TIGHT_BOX'
        if lower_highs and right.low.min()<left.low.min():return 'DESCENDING_CHANNEL'
    if len(bars)<9:return 'SHORT_B_V'
    return 'OTHER'


def locate_events(code, raw, peak_from, peak_to, bottom_from, bottom_to, turnover_limit):
    """以有限狀態機由左至右尋找崩跌、A反彈、B盤整，再看放量紅K。"""
    d=enrich(raw.sort_values('date')).reset_index(drop=True)
    d['ma60']=d.close.rolling(60).mean()
    d['turnover20']=(d.close*d.volume).shift(1).rolling(20).mean()
    n=len(d)
    if n<100:return [],None,d
    hi=d.high.to_numpy(float);lo=d.low.to_numpy(float);cl=d.close.to_numpy(float)
    op=d.open.to_numpy(float);vol=d.volume.to_numpy(float)
    dt=d.date.to_numpy(dtype='datetime64[D]')
    peak_from=np.datetime64(peak_from);peak_to=np.datetime64(peak_to)
    bottom_from=np.datetime64(bottom_from);bottom_to=np.datetime64(bottom_to)
    state='SEARCH';ev=[];fired=set()
    ph=bottom=a_hi=b_lo=np.nan;peak_i=bottom_i=a_i=b_start=None
    last_bar_info={}
    for i in range(65,n):
        if vol[i]<=0:continue
        today=dt[i]
        if state=='SEARCH':
            if today<bottom_from or today>bottom_to:continue
            # 只以6、7月的高點作為待收復的原始前高（依資料當時可見最高點）
            cand=[j for j in range(max(0,i-65),i) if peak_from<=dt[j]<=peak_to]
            if not cand:continue
            j=max(cand,key=lambda t:hi[t]);peak=hi[j]
            if i-j<=55 and cl[i]/peak<=.70:
                ph=peak;peak_i=j;bottom=lo[i];bottom_i=i
                state='BOTTOM'
        elif state=='BOTTOM':
            if lo[i]<bottom:bottom=lo[i];bottom_i=i
            if dt[bottom_i]>bottom_to or i-bottom_i>45 or i-peak_i>120:
                state='SEARCH';continue
            if i-bottom_i>=2 and cl[i]>=bottom*1.18:
                a_hi=hi[i];a_i=i;state='A'
        elif state=='A':
            if hi[i]>a_hi:a_hi=hi[i];a_i=i
            if i-a_i>=3 and a_hi>=bottom*1.25 and lo[i]<=a_hi-.25*(a_hi-bottom):
                b_start=i;b_lo=lo[i];state='B';fired=set()
            elif i-bottom_i>130:state='END'
        elif state=='B':
            b_lo=min(b_lo,lo[i]);depth=(a_hi-b_lo)/(a_hi-bottom)
            if b_lo<=bottom*1.005 or depth>=.94 or i-bottom_i>150:
                state='END';continue
            if i-b_start<5:continue
            if not np.isfinite(d.iloc[i].turnover20) or d.iloc[i].turnover20<turnover_limit:continue
            prev_vol=d.iloc[i].vol_ratio
            if not np.isfinite(prev_vol):continue
            is_red=(cl[i]>op[i] and cl[i]>cl[i-1])
            is_volume=(prev_vol>=1.5)
            bar_range=hi[i]-lo[i]
            body=(cl[i]-op[i])/bar_range if bar_range>0 else 0
            close_loc=(cl[i]-lo[i])/bar_range if bar_range>0 else .5
            b_hist=d.iloc[b_start:i]
            refstart=max(a_i+1,i-10)
            resistance=min(float(np.max(hi[refstart:i])),a_hi) if i-refstart>=3 else np.nan
            trig={
                'VOL_RED':bool(is_red and is_volume),
                'STRONG_RED':bool(is_red and is_volume and body>=.50 and close_loc>=.75),
                'RECLAIM_3H':bool(is_red and is_volume and cl[i]>np.max(hi[i-3:i]) and cl[i]>d.iloc[i].ma5),
                'BREAK_B10':bool(is_red and is_volume and np.isfinite(resistance) and
                                  cl[i]>resistance*1.005 and cl[i]>d.iloc[i].ma20),
            }
            mor=b_morphology(b_hist)
            bmean=fmt(b_hist.volume.mean());amean=fmt(d.iloc[bottom_i:a_i+1].volume.mean())
            b_vs_a=bmean/amean if np.isfinite(amean) and amean>0 else np.nan
            gap=100*(op[i]/cl[i-1]-1) if cl[i-1]>0 else np.nan
            base=dict(symbol=code,signal_date=str(today),signal_index=i,
                bottom_date=str(dt[bottom_i]),peak_date=str(dt[peak_i]),
                peak_6_7=fmt(ph),bottom=fmt(bottom),a_high=fmt(a_hi),b_low=fmt(b_lo),
                crash_pct=100*(bottom/ph-1),a_up_pct=100*(a_hi/bottom-1),
                b_retrace=fmt(depth),b_days=i-b_start,morphology=mor,
                b_volume_vs_a=b_vs_a,vol_ratio=fmt(prev_vol),
                body_share=fmt(body),close_location=fmt(close_loc),gap_pct=fmt(gap),
                rsi=fmt(d.iloc[i].rsi),macd_hist=fmt(d.iloc[i].macd_hist),
                ma20_slope5_pct=fmt(100*(d.iloc[i].ma20/d.iloc[i-5].ma20-1)),
                resistance_B10=fmt(resistance),
                dist_to_A_pct=fmt(100*(a_hi/cl[i]-1)),
                risk_to_B_pct=fmt(100*(cl[i]/b_lo-1)),
                avg_turnover20=fmt(d.iloc[i].turnover20),
                red_candle=bool(is_red),red_body_pct=100*(cl[i]/op[i]-1),
                precrash_peak_distance_pct=fmt(100*(ph/cl[i]-1)))
            for t in TRIGGERS:
                if trig[t] and t not in fired:
                    ev.append(dict(**base,trigger=t))
                    fired.add(t)
            if np.isfinite(resistance) and cl[i]>resistance*1.005 and cl[i]>a_hi*1.01:
                state='C'
            elif 'BREAK_B10' in fired and cl[i]>resistance*1.005:
                state='C'
            last_bar_info=dict(state='B',b_low=b_lo,a_high=a_hi,resistance_B10=resistance,
                               b_retrace=depth,morphology=mor,peak_6_7=ph)
        elif state=='C':
            if cl[i]<b_lo*.995 or lo[i]<=bottom:state='END'
            if i-bottom_i>185:state='END'
        elif state=='END':
            pass
    current=dict(symbol=code,last_date=str(dt[-1]),close=fmt(cl[-1]),stage=state,
        **last_bar_info)
    return ev,current,d


def evaluate(d,e,h):
    """隔日開盤進場，最大停損8%與B低點的較近者；持滿期或停損。"""
    i=int(e['signal_index']);start=i+1;end=start+h-1
    if end>=len(d):return None
    if d.iloc[start].volume<=0:return None
    entry=fmt(d.iloc[start].open)
    if not np.isfinite(entry) or entry<=0:return None
    stop=max(entry*.92,e['b_low']*.995)
    if stop>=entry:return None
    sell=fmt(d.iloc[end].close);exit_i=end;reason='期滿'
    for j in range(start,end+1):
        bar=d.iloc[j]
        if bar.volume<=0:continue
        if bar.open<=stop:
            sell=float(bar.open);exit_i=j;reason='跳空停損';break
        if bar.low<=stop:
            sell=stop;exit_i=j;reason='結構停損';break
    if d.iloc[exit_i].volume<=0:return None
    held=d.iloc[start:exit_i+1];future=d.iloc[start:end+1]
    if future.empty:return None
    net=100*((sell*(1-COST_SELL))/(entry*(1+COST_BUY))-1)
    return dict(**{k:v for k,v in e.items() if k!='signal_index'},horizon=h,
                entry_date=d.iloc[start].date.date().isoformat(),entry=entry,
                exit_date=d.iloc[exit_i].date.date().isoformat(),exit=sell,
                exit_reason=reason,net_pct=net,
                win=bool(net>0),mae_pct=100*(held.low.min()/entry-1),
                mfe_pct=100*(held.high.max()/entry-1),
                hit_A_while_held=bool((held.close>e['a_high']*1.01).any()),
                regain_peak_while_held=bool((held.close>e['peak_6_7']*1.01).any()),
                regain_peak_in_horizon=bool((future.close>e['peak_6_7']*1.01).any()),
                max_potential_move_pct=100*(future.high.max()/entry-1),
                stop_pct=100*(stop/entry-1),
                gap_next_open_pct=100*(entry/d.iloc[i].close-1))


def performance(q):
    if q.empty:return {}
    r=q.net_pct
    bydate=q.groupby('signal_date').net_pct.mean()
    losses=r[r<0];wins=r[r>0]
    return dict(n=len(q),tickers=q.symbol.nunique(),distinct_signal_days=q.signal_date.nunique(),
                win_pct=round(100*(r>0).mean(),2),avg_net_pct=round(r.mean(),3),
                median_net_pct=round(r.median(),3),date_equal_avg_pct=round(bydate.mean(),3),
                p10_net_pct=round(r.quantile(.1),3),p90_net_pct=round(r.quantile(.9),3),
                best_single_net_pct=round(r.max(),3),
                gain_over_10pct=round(100*(r>=10).mean(),2),
                gain_over_20pct=round(100*(r>=20).mean(),2),
                avg_mae_pct=round(q.mae_pct.mean(),3),
                avg_mfe_pct=round(q.mfe_pct.mean(),3),p90_mfe_pct=round(q.mfe_pct.quantile(.9),3),
                stop_rate_pct=round(100*q.exit_reason.str.contains('停損').mean(),2),
                a_break_while_held_pct=round(100*q.hit_A_while_held.mean(),2),
                original_peak_regain_while_held_pct=round(100*q.regain_peak_while_held.mean(),2),
                original_peak_regain_horizon_pct=round(100*q.regain_peak_in_horizon.mean(),2),
                profit_factor=round(wins.sum()/(-losses.sum()),3) if len(losses) else np.nan,
                eligible_30_10=bool(len(q)>=30 and q.signal_date.nunique()>=10))


def dump_csv(df,path):
    df.to_csv(path,index=False,encoding='utf-8-sig')


def make_reports(args):
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    data=get_data(args)
    asof=data.date.max() if args.asof=='auto' else pd.Timestamp(args.asof)
    data=data[data.date<=asof]
    if data.empty:raise RuntimeError('找不到指定截止日前的行情')
    newest=data.date.max();valid=data.groupby('symbol').date.max()
    valid=valid[valid>=newest-pd.Timedelta(days=7)].index
    data=data[data.symbol.isin(valid)]
    n=data.symbol.nunique()
    if n<args.min_universe:raise RuntimeError(f'實際僅 {n} 檔，低於要求 {args.min_universe}')
    events=[];trades=[];curr=[]
    for k,(symbol,g) in enumerate(data.groupby('symbol'),1):
        ev,c,d=locate_events(symbol,g,args.peak_from,args.peak_to,
                             args.bottom_from,args.bottom_to,args.min_turnover)
        if c:curr.append(c)
        for e in ev:
            events.append({k:v for k,v in e.items() if k!='signal_index'})
            for h in HORIZONS:
                t=evaluate(d,e,h)
                if t is not None:trades.append(t)
        if k%350==0:print(f'[研究] {k}/{n} 檔',flush=True)
    e=pd.DataFrame(events);t=pd.DataFrame(trades);current=pd.DataFrame(curr)
    dump_csv(e,out/'B2C_all_volume_redK_events.csv')
    dump_csv(t,out/'B2C_completed_trade_backtests.csv')
    if len(e):
        today=str(newest.date())
        dump_csv(e[e.signal_date==today],out/'B2C_today_redK_signals.csv')
        dump_csv(e[e.signal_date>=str((newest-pd.Timedelta(days=7)).date())],out/'B2C_last_week_signals.csv')
        dump_csv(e[e.trigger=='BREAK_B10'],out/'B2C_10day_B_breakout_events.csv')
    else:
        for name in ['B2C_today_redK_signals.csv','B2C_last_week_signals.csv','B2C_10day_B_breakout_events.csv']:
            dump_csv(e,out/name)
    out_rows=[]
    if len(t):
        for (trigger,h),q in t.groupby(['trigger','horizon']):
            out_rows.append(dict(group_by='trigger',group=str(trigger),horizon=h,**performance(q)))
        for h in (10,20):
            for (trigger,form),q in t[t.horizon==h].groupby(['trigger','morphology']):
                out_rows.append(dict(group_by='morphology',group=f'{trigger} | {form}',horizon=h,**performance(q)))
            z=t[t.horizon==h].copy()
            z['B_depth_band']=pd.cut(z.b_retrace,[-1,.382,.5,.618,.75,1.1])
            z['vol_band']=pd.cut(z.vol_ratio,[0,1.5,2,3,5,np.inf])
            z['body_band']=pd.cut(z.body_share,[-np.inf,.35,.5,.7,np.inf])
            z['b_days_band']=pd.cut(z.b_days,[0,7,12,20,35,200])
            z['b_vs_a_volume_band']=pd.cut(z.b_volume_vs_a,[-1,.5,.7,.9,1.2,np.inf])
            z['rsi_band']=pd.cut(z.rsi,[0,40,50,60,70,100])
            z['macd_positive']=z.macd_hist>0
            z['ma20_rising']=z.ma20_slope5_pct>0
            z['dist_to_A_band']=pd.cut(z.dist_to_A_pct,[-100,0,5,15,30,np.inf])
            z['risk_to_B_band']=pd.cut(z.risk_to_B_pct,[-100,6,12,20,40,np.inf])
            for col in ['B_depth_band','vol_band','body_band','b_days_band',
                        'b_vs_a_volume_band','rsi_band','macd_positive',
                        'ma20_rising','dist_to_A_band','risk_to_B_band']:
                for (trigger,bucket),q in z.groupby(['trigger',col],observed=True):
                    out_rows.append(dict(group_by=col,group=f'{trigger} | {bucket}',horizon=h,**performance(q)))
    perf=pd.DataFrame(out_rows)
    dump_csv(perf,out/'B2C_strategy_and_shape_performance.csv')
    if len(perf):
        robust=perf[(perf.horizon==20)&(perf.eligible_30_10)&(perf.group_by!='trigger')]
        dump_csv(robust.sort_values(['avg_net_pct','median_net_pct'],ascending=False),out/'B2C_candidate_favorable_shapes_exploratory.csv')
    else:
        dump_csv(pd.DataFrame(),out/'B2C_candidate_favorable_shapes_exploratory.csv')
    # 注意: latest watchlist 非最新盤中交易訊號，current stage只作客觀參考。
    if len(current):
        dump_csv(current,out/'B2C_crash_wave_current_states.csv')
    lines=['# 6–7 月崩盤後 B→C 放量紅K事件研究','',
      f'- 股票池：{n} 檔；行情最後日期：{newest.date()}（requested asof={asof.date()}）',
      f'- 期間：崩盤前高 {args.peak_from}–{args.peak_to}；底部 {args.bottom_from}–{args.bottom_to}',
      f'- 事件：{len(e)} 筆；已成熟交易列：{len(t)}（事件跨策略／期間會重複）',
      f'- 當日放量紅K事件：{int((e.signal_date==str(newest.date())).sum()) if len(e) else 0} 筆',
      '', '## 研究設計','',
      '- VOL_RED：成交量 ≥ 前20日均量1.5倍，收盤 > 開盤且 > 昨收；不要求突破。',
      '- STRONG_RED：再要求實體佔整根K棒 ≥50%，收盤位於全K高點區的上25%。',
      '- RECLAIM_3H：再要求站上前3根K最高價與MA5。',
      '- BREAK_B10：再要求站上當時B波前10根K最高點0.5%及MA20。',
      '- 各型態在同一輪B波最多記一次，若早期放量出現而B波仍延續，會另外記更晚的突破事件。',
      '- W底/更高低點/收斂/盤整/下降通道的形態只能使用觸發前已完成的K棒。',
      '- 隔日開盤買入、距B低點或8%初始停損擇較近者，持有5/10/20/40日；假設含交易成本。',
      '- 另計停損前實際收復原始高點，以及停損後行情曾收復的不同結果，避免紙上最大漲幅誤導。',
      '- 訊號有高度同日群聚；要求樣本≥30且分布≥10個訊號日才標記較可信，非統計顯著檢驗。',
      '', '## 限制','',
      '- 僅研究2026年這波急跌，樣本外驗證尚無法完成；切勿把同一波市場反彈誤當多年獨立樣本。',
      '- 不假設可在當日收盤價提前買入，隔日開盤遇到跳空或漲停可能無法成交。',
      '- W底與波浪是可重複計算的代理形態，與人工主觀畫線不同；交易成本/日K撮合是近似。',
      '- 歷史回測資訊不是即時推薦，交易所原始行情與除權息仍須另核對。']
    if len(perf):
        lines.extend(['','## 四種進場規則：20日成熟績效'])
        subset=perf[(perf.group_by=='trigger')&(perf.horizon==20)]
        if not subset.empty:
            lines+=['','|訊號|n|勝率%|平均淨報酬%|中位數%|收復原前高(持股內)%|',
                    '|---|---:|---:|---:|---:|---:|']
            for _,r in subset.iterrows():
                lines.append(f'|{r.group}|{r.n}|{r.win_pct:.2f}|{r.avg_net_pct:.2f}|{r.median_net_pct:.2f}|{r.original_peak_regain_while_held_pct:.2f}|')
    text='\n'.join(lines)+'\n'
    (out/'B2C_MORPHOLOGY_README.md').write_text(text,encoding='utf-8')
    (out/'B2C_GITHUB_SUMMARY.md').write_text(text[:7500],encoding='utf-8')
    print(f'[完成] 研究事件 {len(e)}、成熟交易列 {len(t)}、股票 {n}',flush=True)
    return {'n':n,'events':len(e),'matured':len(t)}


def main():
    p=argparse.ArgumentParser(description='2026 六七月崩盤後 B→C 放量紅K與形態學回測')
    p.add_argument('--data',default=None)
    p.add_argument('--asof',default='auto')
    p.add_argument('--out',default='results')
    p.add_argument('--workers',type=int,default=10)
    p.add_argument('--max-symbols',type=int,default=0)
    p.add_argument('--min-universe',type=int,default=200)
    p.add_argument('--min-turnover',type=float,default=1e7)
    p.add_argument('--peak-from',default='2026-06-01')
    p.add_argument('--peak-to',default='2026-07-31')
    p.add_argument('--bottom-from',default='2026-06-01')
    p.add_argument('--bottom-to',default='2026-08-15')
    args=p.parse_args();make_reports(args)

if __name__=='__main__':main()
