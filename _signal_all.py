# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\yushin_57\projects\stock-bot')
import pandas as pd
import numpy as np
from data.fetch import get_price_history

WATCHLIST = [
    ('1519', '華城'),
    ('2330', '台積電'),
    ('2382', '廣達'),
    ('3017', '奇鋐'),
    ('3131', '弘塑'),
    ('3231', '緯創'),
    ('3324', '雙鴻'),
    ('8064', '東捷'),
    ('0050', '元大台灣50'),
    ('0052', '富邦科技'),
    ('0056', '元大高股息'),
    ('006208', '富邦台50'),
    ('00662', '富邦NASDAQ'),
    ('00878', '國泰永續高股息'),
    ('009816', '凱基台灣TOP50'),
]

rows = []
for sid, name in WATCHLIST:
    try:
        df = get_price_history(sid, '2025-06-01')
        if len(df) < 20:
            continue
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)

        c   = df['close'].iloc[-1]
        o   = df['open'].iloc[-1]
        h   = df['max'].iloc[-1]
        l   = df['min'].iloc[-1]
        c1  = df['close'].iloc[-2]
        date = df['date'].iloc[-1].date()
        chg  = (c - c1) / c1 * 100

        ma5  = df['close'].tail(5).mean()
        ma10 = df['close'].tail(10).mean()
        ma20 = df['close'].tail(20).mean()

        # 均線趨勢
        trend_short = ma5 > ma20
        prev_ma5  = df['close'].tail(6).head(5).mean()
        prev_ma20 = df['close'].tail(21).head(20).mean()
        cross_up   = prev_ma5 <= prev_ma20 and ma5 > ma20  # 黃金交叉
        cross_down = prev_ma5 >= prev_ma20 and ma5 < ma20  # 死亡交叉

        # K線強弱
        total  = h - l if h != l else 0.0001
        body   = abs(c - o)
        bull_k = c > o and body/total >= 0.6 and c >= (h+l)/2
        bear_k = c < o and body/total >= 0.6 and c <= (h+l)/2

        # 訊號判斷
        if cross_up:
            signal = '🟢 買入（黃金交叉）'
        elif trend_short and bull_k:
            signal = '🟢 買入（趨勢+強陽線）'
        elif cross_down:
            signal = '🔴 賣出（死亡交叉）'
        elif not trend_short and bear_k:
            signal = '🔴 賣出（趨勢+強陰線）'
        elif trend_short:
            signal = '🔵 持有觀察（上升趨勢）'
        else:
            signal = '⚪ 空手等待（下降趨勢）'

        # 近5日方向
        recent5 = df['close'].tail(5).values
        up_days = sum(1 for i in range(1, len(recent5)) if recent5[i] > recent5[i-1])

        rows.append({
            'sid': sid, 'name': name, 'date': date,
            'close': c, 'chg': chg,
            'ma5': round(ma5,2), 'ma20': round(ma20,2),
            'trend': '上升' if trend_short else '下降',
            'signal': signal,
            'up_days': f'{up_days}/4',
        })
    except Exception as e:
        print(f"  {name}({sid}) 錯誤: {e}")

print(f"{'代號':>6}  {'名稱':<10}  {'收盤':>7}  {'漲跌%':>6}  {'MA5':>7}  {'MA20':>7}  {'趨勢':>4}  近4日  訊號")
print('-' * 95)
for r in rows:
    print(f"{r['sid']:>6}  {r['name']:<10}  {r['close']:>7.2f}  {r['chg']:>+6.2f}%  "
          f"{r['ma5']:>7.2f}  {r['ma20']:>7.2f}  {r['trend']:>4}  "
          f"{r['up_days']}上漲  {r['signal']}")
print(f'\n資料日期：{rows[0]["date"] if rows else "N/A"}')
