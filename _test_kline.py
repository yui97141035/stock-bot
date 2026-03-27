import sys
sys.path.insert(0, r'C:\Users\yushin_57\projects\stock-bot')

from backtest.engine import run_in_sample_out_sample
from strategies.ma_kline import MAKlineStrategy

result = run_in_sample_out_sample(
    stock_id='2330',
    start='2020-01-01',
    split='2023-01-01',
    end='2025-01-01',
    strategy_cls=MAKlineStrategy,
    strategy_params={'short_period': 5, 'long_period': 20, 'body_ratio': 0.6, 'printlog': False},
    cash=200000,
)

for key in ['in', 'out', 'full']:
    r = result[key]
    print(f"\n[{key}]")
    print(f"  報酬率:   {r['return_pct']}%")
    print(f"  買入持有: {r['bh_return']}%")
    print(f"  Sharpe:   {r['sharpe']}")
    print(f"  最大回撤: {r['max_drawdown']}%")
    print(f"  交易次數: {r['total_trades']}")
    print(f"  勝率:     {r['win_rate']}%")

print("\n✅ MAKlineStrategy 驗證完成")
