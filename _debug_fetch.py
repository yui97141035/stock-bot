import sys
sys.path.insert(0, r'C:\Users\yushin_57\projects\stock-bot')
from FinMind.data import DataLoader
dl = DataLoader()
df = dl.taiwan_stock_daily(stock_id='2330', start_date='2026-03-25', end_date='2026-03-27')
print(df.columns.tolist())
print(df.head())
