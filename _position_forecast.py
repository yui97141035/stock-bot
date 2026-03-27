# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\yushin_57\projects\stock-bot')
import pandas as pd
import numpy as np
from data.fetch import get_price_history

# 現有持倉
POSITIONS = [
    {'id': '0050',   'name': '元大台灣50',    'account': '陳姵語', 'shares': 146,  'cost': 70.58},
    {'id': '00662',  'name': '富邦NASDAQ',    'account': '陳姵語', 'shares': 29,   'cost': 102.35},
    {'id': '009816', 'name': '凱基台灣TOP50', 'account': '陳姵語', 'shares': 2182, 'cost': 11.31},
    {'id': '009816', 'name': '凱基台灣TOP50', 'account': '盧譽心', 'shares': 274,  'cost': 10.87},
]

def analyze(sid, name, shares, cost):
    df = get_price_history(sid, '2025-01-01')
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    c    = df['close'].iloc[-1]
    o    = df['open'].iloc[-1]
    h    = df['max'].iloc[-1]
    l    = df['min'].iloc[-1]
    date = df['date'].iloc[-1].date()

    # 均線
    ma5  = df['close'].tail(5).mean()
    ma10 = df['close'].tail(10).mean()
    ma20 = df['close'].tail(20).mean()
    ma60 = df['close'].tail(60).mean()

    # 前一根
    pm5  = df['close'].tail(6).head(5).mean()
    pm20 = df['close'].tail(21).head(20).mean()

    # 趨勢
    trend_up   = ma5 > ma20
    golden     = pm5 <= pm20 and ma5 > ma20
    dead       = pm5 >= pm20 and ma5 < ma20

    # K線
    total  = h - l if h != l else 0.0001
    body   = abs(c - o)
    bull_k = c > o and body/total >= 0.6 and c >= (h+l)/2
    bear_k = c < o and body/total >= 0.6 and c <= (h+l)/2

    # 近期支撐壓力
    recent20 = df.tail(20)
    support  = recent20['min'].min()
    resist   = recent20['max'].max()

    # 波動率（20日）
    vol = df['close'].pct_change().tail(20).std() * np.sqrt(252) * 100

    # 進場條件
    entry_conds = []
    if not trend_up:
        entry_conds.append('等待MA5重新站上MA20（趨勢轉多）')
    if trend_up and not bull_k:
        entry_conds.append('等待強陽線確認（實體>60%，收在上半段）')
    if c < ma60:
        entry_conds.append(f'最好等收盤站上MA60（{ma60:.2f}）再考慮加碼')

    entry_price = round(ma20 * 1.005, 2)  # MA20上方0.5%

    # 出場條件
    if cost:
        stop_loss   = round(cost * 0.85, 2)   # -15%（ETF寬鬆）
        take_profit = round(cost * 1.15, 2)   # +15%
        pnl_pct     = (c / cost - 1) * 100
        pnl_amt     = (c - cost) * shares
    else:
        stop_loss   = round(support * 0.97, 2)
        take_profit = round(resist  * 1.05, 2)
        pnl_pct     = None
        pnl_amt     = None

    # 綜合判斷
    if golden:
        verdict = '買入訊號（黃金交叉剛發生）'
    elif trend_up and bull_k:
        verdict = '買入訊號（趨勢+強陽線）'
    elif dead:
        verdict = '出場訊號（死亡交叉）'
    elif not trend_up and bear_k:
        verdict = '出場訊號（趨勢+強陰線）'
    elif trend_up:
        verdict = '持有，等強陽線加碼'
    else:
        verdict = '觀望，不加碼，持有注意停損'

    return {
        'sid': sid, 'name': name, 'date': date,
        'close': c, 'cost': cost, 'shares': shares,
        'pnl_pct': pnl_pct, 'pnl_amt': pnl_amt,
        'ma5': ma5, 'ma20': ma20, 'ma60': ma60,
        'trend_up': trend_up,
        'support': support, 'resist': resist, 'vol': vol,
        'stop_loss': stop_loss, 'take_profit': take_profit,
        'entry_price': entry_price,
        'entry_conds': entry_conds,
        'verdict': verdict,
    }

seen = set()
results = {}
for p in POSITIONS:
    sid = p['id']
    if sid not in seen:
        seen.add(sid)
        results[sid] = analyze(sid, p['name'], p['shares'], p['cost'])

print("=" * 65)
print("  持倉預判報告  —  " + str(list(results.values())[0]['date']))
print("=" * 65)

for p in POSITIONS:
    sid  = p['id']
    r    = results[sid]
    acct = p['account']
    sh   = p['shares']
    cost = p['cost']

    pnl_str = ''
    if cost:
        pnl_pct = (r['close'] / cost - 1) * 100
        pnl_amt = (r['close'] - cost) * sh
        pnl_str = f"  損益：{pnl_pct:+.1f}%（{pnl_amt:+.0f}元）"

    print(f"\n【{acct}】{r['name']}（{sid}）  {sh}股")
    print(f"  收盤：{r['close']:.2f}  成本：{cost if cost else 'N/A'}{pnl_str}")
    print(f"  MA5：{r['ma5']:.2f}  MA20：{r['ma20']:.2f}  MA60：{r['ma60']:.2f}")
    print(f"  趨勢：{'上升' if r['trend_up'] else '下降'}  年化波動：{r['vol']:.1f}%")
    print(f"  近20日支撐：{r['support']:.2f}  壓力：{r['resist']:.2f}")
    print(f"  停損線：{r['stop_loss']:.2f}  停利線：{r['take_profit']:.2f}")
    print(f"  判斷：{r['verdict']}")
    if r['entry_conds']:
        print(f"  進場條件：")
        for ec in r['entry_conds']:
            print(f"    - {ec}")
    else:
        print(f"  進場條件：已滿足，參考進場價 {r['entry_price']:.2f}")
