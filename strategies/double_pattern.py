"""
strategies/double_pattern.py
W底（雙底）+ M頭（雙頂）策略，搭配均線趨勢過濾

索引說明：self.data.low[-i]
  i=0  → 當根K棒（最新）
  i=1  → 前1根
  i=lb → 最舊的一根

時間順序：lows[lb-1]=最舊 ... lows[0]=最新（當前）

W底流程（時間由左到右）：
  [舊區] 出現 low1（第一個底）
  [中區] 出現反彈高點 neckline
  [近區] 出現 low2（第二個底，與 low1 相近）
  [現在] 收盤突破 neckline → 買入

M頭流程：
  [舊區] 出現 high1（第一個頂）
  [中區] 出現回落低點 neckline
  [近區] 出現 high2（第二個頂，與 high1 相近）
  [現在] 收盤跌破 neckline → 賣出
"""
import backtrader as bt


class DoublePatternStrategy(bt.Strategy):
    params = (
        ('long_period', 20),   # 趨勢均線週期
        ('lookback',    40),   # 往回看幾根K棒找型態
        ('tolerance',   0.05), # 兩底/兩頂差異容忍度（5%以內算相近）
        ('printlog',    True),
    )

    def __init__(self):
        self.ma_long = bt.indicators.SMA(self.data.close, period=self.p.long_period)

    def _get_series(self):
        lb = self.p.lookback
        lows   = [self.data.low[-i]   for i in range(lb)]  # lows[0]=當前, lows[lb-1]=最舊
        highs  = [self.data.high[-i]  for i in range(lb)]
        return lows, highs

    def find_w_bottom(self):
        lb  = self.p.lookback
        if len(self.data) < lb + 5:
            return False, 0
        lows, highs = self._get_series()
        seg = lb // 3

        # 舊區：lows[2*seg : lb]  (時間較早，索引較大)
        old_lows  = lows[2*seg:]
        # 中區：lows[seg : 2*seg]
        mid_highs = highs[seg:2*seg]
        # 近區：lows[0 : seg]     (最近，索引較小)
        new_lows  = lows[:seg]

        if not old_lows or not mid_highs or not new_lows:
            return False, 0

        low1     = min(old_lows)
        neckline = max(mid_highs)
        low2     = min(new_lows)
        tol      = self.p.tolerance
        current  = self.data.close[0]

        # 條件：兩底相近 + 第二底不低於第一底太多 + 突破頸線
        if (abs(low1 - low2) / max(low1, low2) <= tol and
                low2 >= low1 * (1 - tol) and
                current > neckline):
            return True, neckline
        return False, 0

    def find_m_top(self):
        lb  = self.p.lookback
        if len(self.data) < lb + 5:
            return False, 0
        lows, highs = self._get_series()
        seg = lb // 3

        old_highs = highs[2*seg:]
        mid_lows  = lows[seg:2*seg]
        new_highs = highs[:seg]

        if not old_highs or not mid_lows or not new_highs:
            return False, 0

        high1    = max(old_highs)
        neckline = min(mid_lows)
        high2    = max(new_highs)
        tol      = self.p.tolerance
        current  = self.data.close[0]

        # 條件：兩頂相近 + 跌破頸線
        if (abs(high1 - high2) / max(high1, high2) <= tol and
                high2 <= high1 * (1 + tol) and
                current < neckline):
            return True, neckline
        return False, 0

    def next(self):
        trend_up   = self.data.close[0] > self.ma_long[0]
        trend_down = self.data.close[0] < self.ma_long[0]

        if not self.position:
            w_found, neckline = self.find_w_bottom()
            if w_found and trend_up:
                self.buy()
                self.log(f'買入（W底突破 {neckline:.2f}）  收盤: {self.data.close[0]:.2f}')
        else:
            m_found, neckline = self.find_m_top()
            if m_found:
                self.sell()
                self.log(f'賣出（M頭跌破 {neckline:.2f}）  收盤: {self.data.close[0]:.2f}')
            elif trend_down:
                self.sell()
                self.log(f'賣出（趨勢轉空）  收盤: {self.data.close[0]:.2f}')

    def log(self, txt):
        if self.p.printlog:
            dt = self.datas[0].datetime.date(0)
            print(f'[{dt}] {txt}')

    def stop(self):
        self.log(f'策略結束  最終資產: {self.broker.getvalue():.2f}')
