# -*- coding: utf-8 -*-
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\yushin_57\projects\stock-bot')
import pandas as pd
import numpy as np
from data.fetch import get_price_history

df = get_price_history('009816', '2025-01-01')
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)

latest    = df.iloc[-1]
buy_price = 10.0
shares    = 2182
current   = latest['close']
pnl       = (current - buy_price) * shares
pnl_pct   = (current / buy_price - 1) * 100

print(f"=== 009816 凱基台灣TOP50 現況 ===")
print(f"最新日期   : {latest['date'].date()}")
print(f"當前收盤   : {current:.2f}")
print(f"買入成本   : {buy_price:.2f}")
print(f"未實現損益 : {pnl:+.0f} 元 ({pnl_pct:+.2f}%)")
print()

df['ma5']  = df['close'].rolling(5).mean()
df['ma10'] = df['close'].rolling(10).mean()
df['ma20'] = df['close'].rolling(20).mean()
df['ma60'] = df['close'].rolling(60).mean()

last = df.iloc[-1]
prev = df.iloc[-2]

print("=== 均線狀態 ===")
for ma, label in [('ma5','MA5'),('ma10','MA10'),('ma20','MA20'),('ma60','MA60')]:
    val   = last[ma]
    above = "收盤在均線之上" if current > val else "收盤在均線之下"
    print(f"  {label}: {val:.2f}  -> {above}")

print()

# 趨勢
trend = '上升趨勢' if last['ma5'] > last['ma20'] else '下降趨勢'
cross = ''
if prev['ma5'] <= prev['ma20'] and last['ma5'] > last['ma20']:
    cross = '[剛發生黃金交叉-轉多]'
elif prev['ma5'] >= prev['ma20'] and last['ma5'] < last['ma20']:
    cross = '[剛發生死亡交叉-轉空]'

print("=== 趨勢判斷 ===")
print(f"  MA5({last['ma5']:.2f}) vs MA20({last['ma20']:.2f}): {trend} {cross}")
print(f"  MA5 vs MA60: {'多方' if last['ma5'] > last['ma60'] else '空方'} (MA60={last['ma60']:.2f})")

print()

recent = df.tail(30)
high30 = recent['max'].max()
low30  = recent['min'].min()
mid30  = (high30 + low30) / 2
print("=== 近30日區間 ===")
print(f"  最高: {high30:.2f}  最低: {low30:.2f}  中點: {mid30:.2f}")
print(f"  當前位置: {'上半段（偏強）' if current > mid30 else '下半段（偏弱）'}")

print()

print("=== 近10個交易日走勢 ===")
for _, row in df.tail(10).iterrows():
    chg  = (row['close'] - row['open']) / row['open'] * 100
    sign = 'up' if chg > 0 else 'dn'
    print(f"  {row['date'].date()}  開{row['open']:.2f} 收{row['close']:.2f}  {sign} {abs(chg):.2f}%")

print()

stop_loss   = buy_price * 0.92
take_profit = buy_price * 1.15
print("=== 停損/停利參考 ===")
print(f"  買入成本  : {buy_price:.2f}")
print(f"  停損線    : {stop_loss:.2f} (-8%)   {'[已跌破]' if current < stop_loss else '未觸發'}")
print(f"  停利線    : {take_profit:.2f} (+15%)  {'[已到達]' if current >= take_profit else '未觸發'}")
print(f"  當前價格  : {current:.2f}")

# W底/M頭 簡易判斷
lows  = df['min'].tail(40).values
highs = df['max'].tail(40).values
seg   = 13
low1  = lows[:seg].min()
neck  = highs[seg:seg*2].max()
low2  = lows[seg*2:].min()
tol   = 0.05

print()
print("=== 型態偵測（近40日）===")
w_cond = (abs(low1-low2)/max(low1,low2) <= tol and
          low2 >= low1*(1-tol) and
          current > neck)
m_high1 = highs[:seg].max()
m_neck  = lows[seg:seg*2].min()
m_high2 = highs[seg*2:].max()
m_cond  = (abs(m_high1-m_high2)/max(m_high1,m_high2) <= tol and
           current < m_neck)

print(f"  W底（買入型態）: {'偵測到 -> 看多' if w_cond else '未出現'}")
print(f"  M頭（賣出型態）: {'偵測到 -> 注意' if m_cond else '未出現'}")
print(f"  （low1={low1:.2f}, low2={low2:.2f}, 頸線={neck:.2f}）")
