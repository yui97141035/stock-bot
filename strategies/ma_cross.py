"""
strategies/ma_cross.py
均線交叉策略（範例）
- 短均線向上穿越長均線 → 買入訊號
- 短均線向下穿越長均線 → 賣出訊號
"""
import backtrader as bt


class MACrossStrategy(bt.Strategy):
    params = (
        ('short_period', 5),   # 短均線週期
        ('long_period', 20),   # 長均線週期
        ('printlog', True),
    )

    def __init__(self):
        self.ma_short = bt.indicators.SMA(self.data.close, period=self.p.short_period)
        self.ma_long  = bt.indicators.SMA(self.data.close, period=self.p.long_period)
        self.crossover = bt.indicators.CrossOver(self.ma_short, self.ma_long)

    def next(self):
        if self.crossover > 0:   # 黃金交叉
            if not self.position:
                self.buy()
                self.log(f'買入  價格: {self.data.close[0]:.2f}')

        elif self.crossover < 0: # 死亡交叉
            if self.position:
                self.sell()
                self.log(f'賣出  價格: {self.data.close[0]:.2f}')

    def log(self, txt):
        if self.p.printlog:
            dt = self.datas[0].datetime.date(0)
            print(f'[{dt}] {txt}')

    def stop(self):
        self.log(f'策略結束  最終資產: {self.broker.getvalue():.2f}')
