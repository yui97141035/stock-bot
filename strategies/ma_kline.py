"""
strategies/ma_kline.py
均線趨勢 + K線形態確認策略

買入條件（兩個都要成立）：
  1. 趨勢確認：短均線 > 長均線（上升趨勢）
  2. K線確認：當根K棒是「強勢陽線」
     - 實體（收盤-開盤）佔整體波動（最高-最低）的比例 >= body_ratio
     - 收盤價在整根K棒的上半段
     - 陽線（收盤 > 開盤）

賣出條件（任一成立）：
  1. 趨勢反轉：短均線 < 長均線（死亡交叉）
  2. 出現「強勢陰線」（收盤 < 開盤，實體大，收在下半段）
"""
import backtrader as bt


class MAKlineStrategy(bt.Strategy):
    params = (
        ('short_period', 5),    # 短均線週期
        ('long_period',  20),   # 長均線週期
        ('body_ratio',   0.6),  # K線實體佔比門檻（實體 / 全長 >= 此值才算強勢）
        ('printlog',     True),
    )

    def __init__(self):
        self.ma_short  = bt.indicators.SMA(self.data.close, period=self.p.short_period)
        self.ma_long   = bt.indicators.SMA(self.data.close, period=self.p.long_period)
        self.crossover = bt.indicators.CrossOver(self.ma_short, self.ma_long)

    def is_bullish_candle(self):
        """強勢陽線：實體大 + 收在上半段"""
        o = self.data.open[0]
        h = self.data.high[0]
        l = self.data.low[0]
        c = self.data.close[0]
        total = h - l
        if total == 0:
            return False
        body  = c - o          # 陽線 body > 0
        mid   = (h + l) / 2
        return (body > 0 and
                body / total >= self.p.body_ratio and
                c >= mid)

    def is_bearish_candle(self):
        """強勢陰線：實體大 + 收在下半段"""
        o = self.data.open[0]
        h = self.data.high[0]
        l = self.data.low[0]
        c = self.data.close[0]
        total = h - l
        if total == 0:
            return False
        body  = o - c          # 陰線 body > 0
        mid   = (h + l) / 2
        return (body > 0 and
                body / total >= self.p.body_ratio and
                c <= mid)

    def next(self):
        in_uptrend = self.ma_short[0] > self.ma_long[0]

        if not self.position:
            # 上升趨勢 + 強勢陽線 → 買入
            if in_uptrend and self.is_bullish_candle():
                self.buy()
                self.log(f'買入（均線↑+強陽線）  價格: {self.data.close[0]:.2f}')
        else:
            # 趨勢反轉（死亡交叉）→ 出場
            if self.crossover < 0:
                self.sell()
                self.log(f'賣出（趨勢反轉）  價格: {self.data.close[0]:.2f}')
            # 出現強勢陰線 → 出場
            elif self.is_bearish_candle():
                self.sell()
                self.log(f'賣出（強陰線警示）  價格: {self.data.close[0]:.2f}')

    def log(self, txt):
        if self.p.printlog:
            dt = self.datas[0].datetime.date(0)
            print(f'[{dt}] {txt}')

    def stop(self):
        self.log(f'策略結束  最終資產: {self.broker.getvalue():.2f}')
