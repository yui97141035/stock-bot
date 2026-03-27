"""
長期買入持有分析（2019-2025，約6年）
計算年化報酬、最大回撤、波動度
"""
import sys, os
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
]

START = '2019-01-01'
END   = '2025-12-31'

rows = []
for sid, name in WATCHLIST:
    try:
        df = get_price_history(sid, START, END)
        if len(df) < 100:
            continue
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        start_price = df['close'].iloc[0]
        end_price   = df['close'].iloc[-1]
        years = (df['date'].iloc[-1] - df['date'].iloc[0]).days / 365.25

        total_return = (end_price / start_price - 1) * 100
        annual_return = ((end_price / start_price) ** (1 / years) - 1) * 100

        # 最大回撤
        roll_max = df['close'].cummax()
        drawdown = (df['close'] - roll_max) / roll_max * 100
        max_dd   = drawdown.min()

        # 年化波動度（日報酬標準差 × sqrt(252)）
        daily_ret = df['close'].pct_change().dropna()
        volatility = daily_ret.std() * np.sqrt(252) * 100

        rows.append({
            '代號': sid,
            '名稱': name,
            '起始價': f'{start_price:.1f}',
            '現在價': f'{end_price:.1f}',
            '總報酬%': round(total_return, 1),
            '年化報酬%': round(annual_return, 1),
            '最大回撤%': round(max_dd, 1),
            '年化波動%': round(volatility, 1),
            '資料年數': round(years, 1),
        })
        print(f"{name}({sid}): 總報酬 {total_return:.1f}%  年化 {annual_return:.1f}%  最大回撤 {max_dd:.1f}%")
    except Exception as e:
        print(f"{name}({sid}): 錯誤 {e}")

df_out = pd.DataFrame(rows).sort_values('年化報酬%', ascending=False)
print('\n' + '='*70)
print(df_out.to_string(index=False))
