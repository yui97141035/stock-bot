"""
backtest/batch.py
批次回測：一次跑多支股票，輸出比較表
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
from data.cache import get_price_cached
from backtest.engine import run_single, is_etf
from dotenv import load_dotenv
load_dotenv('configs/accounts.env')

# ── 你的自選股清單 ─────────────────────────────────────
WATCHLIST = [
    # 個股
    {'id': '1519', 'name': '華城'},
    {'id': '2330', 'name': '台積電'},
    {'id': '2382', 'name': '廣達'},
    {'id': '3017', 'name': '奇鋐'},
    {'id': '3131', 'name': '弘塑'},
    {'id': '3231', 'name': '緯創'},
    {'id': '3324', 'name': '雙鴻'},
    {'id': '8064', 'name': '東捷'},
    # ETF（證交稅 0.1%）
    {'id': '0050',   'name': '元大台灣50'},
    {'id': '0052',   'name': '富邦科技'},
    {'id': '0056',   'name': '元大高股息'},
    {'id': '006208', 'name': '富邦台50'},
    {'id': '00662',  'name': '富邦NASDAQ'},
    {'id': '00878',  'name': '國泰永續高股息'},
    {'id': '009816', 'name': '凱基台灣TOP50'},
]


def run_batch(strategy_cls, strategy_params: dict,
              start: str, end: str,
              cash: float = 200000,
              token: str = None) -> pd.DataFrame:
    """
    批次跑所有自選股，回傳比較 DataFrame
    """
    rows = []
    total = len(WATCHLIST)
    for i, stock in enumerate(WATCHLIST):
        sid  = stock['id']
        name = stock['name']
        etf  = is_etf(sid)
        print(f'[{i+1}/{total}] {name}({sid}) {"ETF" if etf else "個股"}...', end=' ', flush=True)
        try:
            df = get_price_cached(sid, start)
            if df.empty:
                print('無快取資料，跳過')
                continue
            # 截到指定結束日
            if end:
                df = df[df['date'] <= pd.to_datetime(end)]
            if len(df) < 30:
                print('資料不足，跳過')
                continue
            r = run_single(df, strategy_cls, strategy_params,
                           cash=cash, stock_id=sid)
            rows.append({
                '代號':       sid,
                '名稱':       name,
                '類型':       'ETF' if etf else '個股',
                '策略報酬%':  r['return_pct'],
                '買入持有%':  r['bh_return'],
                '超額報酬%':  round(r['return_pct'] - r['bh_return'], 2),
                'Sharpe':     r['sharpe'],
                '最大回撤%':  r['max_drawdown'],
                '交易次數':   r['total_trades'],
                '勝率%':      r['win_rate'],
            })
            print(f"報酬 {r['return_pct']:+.1f}%  買入持有 {r['bh_return']:+.1f}%")
        except Exception as e:
            print(f'錯誤: {e}')

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows).sort_values('超額報酬%', ascending=False)
    return result


if __name__ == '__main__':
    import os
    from strategies.double_pattern import DoublePatternStrategy

    token = os.getenv('FINMIND_TOKEN', '')
    df = run_batch(
        strategy_cls    = DoublePatternStrategy,
        strategy_params = {'long_period': 20, 'lookback': 40,
                           'tolerance': 0.05, 'printlog': False},
        start = '2022-01-01',
        end   = '2025-01-01',
        cash  = 200000,
        token = token or None,
    )
    if not df.empty:
        print('\n' + '='*70)
        print('批次回測結果（依超額報酬排序）')
        print('='*70)
        print(df.to_string(index=False))
