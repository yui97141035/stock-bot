"""
backtest/engine.py
升級版回測引擎：含正確手續費、滑價、樣本外驗證、基準對照
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import backtrader as bt
import pandas as pd
import numpy as np
from data.fetch import get_price_history


# ── 手續費設定 ──────────────────────────────────────────
BUY_COMMISSION      = 0.1425 / 100 * 0.28          # 買入：0.1425% × 2.8折
SELL_COMMISSION     = 0.1425 / 100 * 0.28 + 0.003  # 個股賣出：加證交稅 0.3%
SELL_COMMISSION_ETF = 0.1425 / 100 * 0.28 + 0.001  # ETF 賣出：加證交稅 0.1%
SLIPPAGE            = 0.001                          # 滑價 0.1%

# ETF 代號清單（證交稅 0.1%）
ETF_LIST = {'0050','0051','0052','0053','0054','0055','0056','0057','0058','0059',
            '006200','006201','006203','006204','006205','006206','006207','006208',
            '00625','00628','00630','00631','00632','00633','00636','00637','00638',
            '00639','00640','00642','00643','00646','00647','00648','00650','00652',
            '00653','00655','00656','00657','00658','00659','00660','00661','00662',
            '00664','00665','00668','00669','00670','00671','00672','00673','00674',
            '00675','00676','00677','00678','00679','00680','00681','00682','00683',
            '00685','00686','00687','00688','00689','00690','00692','00694','00695',
            '00696','00697','00698','00699','00700','00701','00702','00703','00704',
            '00706','00707','00708','00709','00710','00711','00712','00713','00714',
            '00715','00716','00717','00718','00719','00720','00721','00722','00724',
            '00725','00726','00728','00730','00731','00733','00734','00735','00736',
            '00737','00739','00740','00741','00742','00743','00744','00745','00748',
            '00750','00751','00752','00753','00754','00755','00756','00757','00758',
            '00759','00760','00761','00762','00763','00764','00765','00766','00768',
            '00770','00771','00772','00774','00775','00776','00780','00781','00782',
            '00783','00784','00785','00786','00787','00791','00793','00795','00797',
            '00820','00830','00850','00878','00881','00882','00883','00884','00885',
            '00886','00887','00888','00889','00891','00893','00894','00895','00896',
            '00897','00898','00899','009816'}


def is_etf(stock_id: str) -> bool:
    return stock_id.strip() in ETF_LIST or stock_id.strip().startswith('00')


class TaiwanCommission(bt.CommInfoBase):
    """台股專用手續費（買賣不同費率，支援ETF）"""
    params = (
        ('buy_comm',  BUY_COMMISSION),
        ('sell_comm', SELL_COMMISSION),
        ('stocklike', True),
        ('commtype',  bt.CommInfoBase.COMM_PERC),
    )

    def getcommission(self, size, price):
        if size > 0:
            return abs(size) * price * self.p.buy_comm
        else:
            return abs(size) * price * self.p.sell_comm


class TradeRecorder(bt.Analyzer):
    """記錄每筆交易細節"""
    def start(self):
        self.trades = []

    def notify_trade(self, trade):
        if trade.isclosed:
            self.trades.append({
                'entry_date': bt.num2date(trade.dtopen).strftime('%Y-%m-%d'),
                'exit_date':  bt.num2date(trade.dtclose).strftime('%Y-%m-%d'),
                'pnl':        round(trade.pnl, 2),
                'pnl_comm':   round(trade.pnlcomm, 2),
            })

    def get_analysis(self):
        return self.trades


def prepare_feed(df: pd.DataFrame) -> bt.feeds.PandasData:
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    col_map = {'open': 'open', 'max': 'high', 'min': 'low',
                'close': 'close', 'Trading_Volume': 'volume'}
    df = df.rename(columns=col_map)
    df = df[['open', 'high', 'low', 'close', 'volume']].dropna()
    return bt.feeds.PandasData(dataname=df), df


def run_single(df: pd.DataFrame, strategy_cls, strategy_params: dict,
               cash: float = 200000, stock_id: str = '') -> dict:
    """跑單次回測，回傳所有指標"""
    feed, price_df = prepare_feed(df)

    cerebro = bt.Cerebro()
    cerebro.addstrategy(strategy_cls, **strategy_params)
    cerebro.adddata(feed)
    cerebro.broker.setcash(cash)
    sell_comm = SELL_COMMISSION_ETF if is_etf(stock_id) else SELL_COMMISSION
    cerebro.broker.addcommissioninfo(TaiwanCommission(sell_comm=sell_comm))
    cerebro.broker.set_slippage_perc(SLIPPAGE)
    # 每次用可用資金的 95%（留 5% 作為手續費緩衝）
    cerebro.addsizer(bt.sizers.PercentSizer, percents=95)

    cerebro.addanalyzer(bt.analyzers.SharpeRatio,  _name='sharpe',
                        riskfreerate=0.02, annualize=True)
    cerebro.addanalyzer(bt.analyzers.DrawDown,      _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns,       _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade_stats')
    cerebro.addanalyzer(TradeRecorder,              _name='trades')

    results = cerebro.run()
    strat = results[0]

    final        = cerebro.broker.getvalue()
    trade_stats  = strat.analyzers.trade_stats.get_analysis()
    trades       = strat.analyzers.trades.get_analysis()
    total_trades = trade_stats.get('total', {}).get('closed', 0)
    won          = trade_stats.get('won', {}).get('total', 0)
    win_rate     = won / total_trades * 100 if total_trades else 0

    # 計算每日資產曲線
    portfolio_values = []
    dates = []
    for d in price_df.index:
        dates.append(d)
    # 用 trades 重建 equity curve（簡化版）
    equity_curve = _build_equity_curve(trades, cash, price_df)

    # 買入持有基準
    bh_return = (price_df['close'].iloc[-1] / price_df['close'].iloc[0] - 1) * 100

    return {
        'cash':         cash,
        'final':        round(final, 2),
        'return_pct':   round((final - cash) / cash * 100, 2),
        'bh_return':    round(bh_return, 2),
        'sharpe':       round(strat.analyzers.sharpe.get_analysis().get('sharperatio') or 0, 3),
        'max_drawdown': round(strat.analyzers.drawdown.get_analysis().get('max', {}).get('drawdown', 0), 2),
        'total_trades': total_trades,
        'win_rate':     round(win_rate, 2),
        'trades':       trades,
        'equity_curve': equity_curve,
        'price_df':     price_df,
    }


def _build_equity_curve(trades: list, cash: float, price_df: pd.DataFrame) -> pd.Series:
    """從交易紀錄重建資產曲線"""
    equity = pd.Series(float(cash), index=price_df.index, dtype=float)
    running = cash
    for t in trades:
        exit_date = pd.to_datetime(t['exit_date'])
        running  += t['pnl_comm']
        if exit_date in equity.index:
            equity[exit_date:] = running
    return equity


def run_in_sample_out_sample(stock_id: str, start: str, split: str, end: str,
                              strategy_cls, strategy_params: dict,
                              cash: float = 200000) -> dict:
    """
    樣本內/樣本外分段回測
    start ~ split：訓練集（In-Sample）
    split ~ end  ：測試集（Out-of-Sample）
    """
    token = os.getenv('FINMIND_TOKEN', '')
    full_df = get_price_history(stock_id, start, end, token or None)

    split_dt = pd.to_datetime(split)
    in_df    = full_df[pd.to_datetime(full_df['date']) <  split_dt]
    out_df   = full_df[pd.to_datetime(full_df['date']) >= split_dt]

    in_result  = run_single(in_df,  strategy_cls, strategy_params, cash, stock_id)
    out_result = run_single(out_df, strategy_cls, strategy_params, cash, stock_id)
    full_result= run_single(full_df,strategy_cls, strategy_params, cash, stock_id)

    return {
        'in':   in_result,
        'out':  out_result,
        'full': full_result,
        'stock_id': stock_id,
        'start': start,
        'split': split,
        'end':   end,
    }
