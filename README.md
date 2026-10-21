# 台股 2026 年 6–7 月急跌後：B 波接 C 波放量紅 K 回測 v4

## 研究範圍

本版本**僅研究 2026 年 6–7 月急跌衍生的型態**，不是一般年份的波浪策略。
使用固定日期：
- 急跌前高：2026-06-01 至 2026-07-31
- 急跌低點：2026-06-01 至 2026-08-15（含部分落後觸底股票；可依研究縮到 2026-07-31）
- 跌幅：原高至收盤至少 30%。
- A：從動態底部先反彈 18% 確認；A 完成前最終反彈幅度至少 25%。
- B：自 A 高回撤至少 25%，不跌破前底，至少整理五根 K 棒。
- 研究目標：以 B 波末端的「量增、收紅 K」為進場事件，隔日開盤買入，檢驗哪種 B 整理形狀及 K 棒位置有最高 **可交易報酬**，並區分是否能收復 6–7 月前高。

## 四種交易訊號（每輪 B 各觸發一次）

所有方案均要求當日量至少為前20日**不含當日**均量的1.5倍；當日收盤高於開盤且高於前一日收盤。

1. `VOL_RED`：只看放量紅 K，不要求結構突破，是你的原始假設。
2. `STRONG_RED`：紅 K 實體至少占全 K 長度50%，收盤在全 K 上方25%。
3. `RECLAIM_3H`：收盤高過前三日最高價、站上 MA5。
4. `BREAK_B10`：收盤高過已知 B 波前十日最高價 0.5% 並且站上 MA20；此為結構確認組。

`STRONG_RED` 與其他組有重疊；**不是四個互斥的股票組合**。

## B 波形態分型

- `W_DOUBLE_BOTTOM`：雙低點相距至少 4 根 K，第二低點與第一低點差不超過5%，期間反彈7%以上。
- `HIGHER_LOW`：相鄰已確認波段低點墊高3%以上。
- `CONTRACTING_TRIANGLE`：短期高點下降、低點上升，價差收斂。
- `TIGHT_BOX`：近10K高低幅不超過12%且量未顯著放大。
- `DESCENDING_CHANNEL`：短期高低點皆下降。
- `SHORT_B_V`：不到9日的短期B波（須先至少5日）。
- `OTHER`：其餘無法可靠分類。以上皆為**程式可重現之代理形態**，不是確定的 Elliott 5 波標記。

## 執行方法

若已經有能正常執行 v3 的 GitHub Repository：

1. 將此專案的 `b2c_volume_redk_study.py` 上傳到**根目錄**，保留原本 `b_wave_breakout.py` 與 `market_abc_core.py`。
2. 將 `tests/test_b2c_study.py` 上傳到 `tests` 資料夾。
3. 用這份專案的 `.github/workflows/tw_abc_scan.yml` 覆蓋原本同一路徑的工作流程檔案。確保在 `main` 分支提交。
4. Actions → `Taiwan ABC v4 B-to-C volume redK` → Run workflow。
5. 執行成功後，從 Artifacts 下載 `taiwan-abc-v4-results-*`；結果內保留原本 v3 報表，**並增加 B2C 前綴的回測檔案**。

可獨立執行（有網路）：

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_*.py' -v
python b2c_volume_redk_study.py --asof auto --min-universe 200 --out results
```

已有合併歷史日線 CSV：

```bash
python b2c_volume_redk_study.py --data your_daily.csv --asof 2026-10-20 --out results
```

## 重要輸出

- `B2C_all_volume_redK_events.csv`：歷史訊號、進場時的波形、量、RSI、MACD、B波回撤比例。
- `B2C_today_redK_signals.csv`：最新交易日剛發生的事件；須核對下一交易日是否可成交。
- `B2C_10day_B_breakout_events.csv`：放量紅 K 同時突破 B 波十日壓力的歷史事件。
- `B2C_completed_trade_backtests.csv`：已成熟交易、固定停損+持有期、持有內最大順向波動及收復前高比率。
- `B2C_strategy_and_shape_performance.csv`：四種策略 + 波形 + RSI/MACD/量比/K棒實體/B 回撤等分箱的比較。
- `B2C_candidate_favorable_shapes_exploratory.csv`：樣本至少30筆、至少10個不同訊號日的形態篩選；不足則為空，不強行排名。
- `B2C_MORPHOLOGY_README.md`：包含研究日期和規則的可讀報告。

## 交易假設、限制

- 訊號於**收盤後**得知，模擬**下一交易日開盤**成交；不允許回頭用B最低點買入。
- 每筆停損設為「B 低點下0.5%」與「進場價下8%」距離較近者；gap 跳空停損以下一開盤價算。依照交易成本使用 `market_abc_core` 的 `COST_BUY/COST_SELL`。
- 無法知道日 K 中分秒撮合、漲跌停排隊與實際成交，開盤價成交存在樂觀偏差；股價是第三方還原行情，正式交易前須做除權息/漲跌停驗證。
- 不能用全期間最大上漲幅度取代實際停損之後的損益；保留 `max_potential_move_pct` 作**事後潛力**而不是策略績效。
- 四種策略的訊號日不同，樣本可能重疊，不能直接以不同組平均值宣稱策略顯著勝出。
- 這是**同一波崩盤的事件研究**；並非跨牛熊週期的樣本外證據，市場同一事件使交易高度相關。
- 沒有夠長的後續日 K 就不計入 20、40 天已成熟交易；請閱讀每組 n、distinct_signal_days 和 median。
