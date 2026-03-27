# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\yushin_57\projects\stock-bot')
from FinMind.data import DataLoader

dl = DataLoader()

# 測試可用的企業基本面資料集
tests = [
    ('TaiwanStockDividend',         '股利資料（現金股利+股票股利）'),
    ('TaiwanStockDividendResult',   '除權息結果'),
    ('TaiwanStockMonthRevenue',     '月營收'),
    ('TaiwanStockFinancialStatements', '財務報表'),
    ('TaiwanStockShareholderMeeting','股東會資料'),
    ('TaiwanStockNews',             '重大訊息'),
]

for dataset, label in tests:
    try:
        df = getattr(dl, dataset.lower().replace('taiwan','taiwan_').replace('stock','stock_'))
        print(f"  OK  {label}（{dataset}）")
    except Exception as e:
        # 試另一種呼叫方式
        try:
            df = dl.get_data(dataset=dataset, stock_id='2330', start_date='2025-01-01', end_date='2025-03-01')
            print(f"  OK  {label}（{dataset}）筆數: {len(df)}")
        except Exception as e2:
            print(f"  --  {label}（{dataset}）: {str(e2)[:60]}")
