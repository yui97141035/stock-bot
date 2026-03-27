"""
backtest/run.py
執行回測
用法: python backtest/run.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import backtrader as bt
import pandas as pd
from data.fetch import get_price_history
from strategies.ma_cross import MACrossStrategy


def run_backtest(stock_id: str, start: str, end: str = None,
                 cash: float = 100000, commission: float = 0.001425 * 0.28):
    """
    stock_id : 股票代號
    start    : 開始日期 'YYYY-MM-DD'
    end      : 結束日期（不填到今天）
    cash     : 初始資金（預設 10 萬）
    commission: 手續費率（預設玉山 2.8 折）
    """
    print(f"\n=== 回測 {stock_id}  {start} ~ {end or '今天'} ===")

    # 抓資料
    df = get_price_history(stock_id, start, end)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df.rename(columns={
        'open': 'open', 'max': 'high', 'min': 'low',
        'close': 'close', 'Trading_Volume': 'volume'
    })
    df = df[['open', 'high', 'low', 'close', 'volume']].dropna()

    # Backtrader feed
    feed = bt.feeds.PandasData(dataname=df)

    cerebro = bt.Cerebro()
    cerebro.addstrategy(MACrossStrategy)
    cerebro.adddata(feed)
    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=commission)

    # 績效分析
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.02)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

    print(f'初始資金: {cerebro.broker.getvalue():.2f}')
    results = cerebro.run()
    strat = results[0]

    final = cerebro.broker.getvalue()
    print(f'最終資金: {final:.2f}')
    print(f'報酬率  : {(final - cash) / cash * 100:.2f}%')
    sharpe = strat.analyzers.sharpe.get_analysis().get('sharperatio', 'N/A')
    dd = strat.analyzers.drawdown.get_analysis().get('max', {}).get('drawdown', 'N/A')
    print(f'Sharpe  : {sharpe}')
    print(f'最大回撤: {dd}%')

    return cerebro


if __name__ == '__main__':
    stock_id = sys.argv[1] if len(sys.argv) > 1 else '2330'
    start    = sys.argv[2] if len(sys.argv) > 2 else '2023-01-01'
    run_backtest(stock_id, start)
