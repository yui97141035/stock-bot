# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\yushin_57\projects\stock-bot')
from FinMind.data import DataLoader
dl = DataLoader()

# 直接用 get_data 測試各資料集
for dataset in [
    'TaiwanStockMonthRevenue',
    'TaiwanStockFinancialStatements',
    'TaiwanStockShareholderMeeting',
    'TaiwanStockDividendResult',
    'TaiwanStockBalanceSheet',
    'TaiwanStockCashFlowsStatement',
    'TaiwanStockNews',
]:
    try:
        import requests, os
        token = os.getenv('FINMIND_TOKEN','')
        params = dict(dataset=dataset, data_id='2330',
                      start_date='2024-01-01', end_date='2025-01-01',
                      token=token)
        r = requests.get('https://api.finmindtrade.com/api/v4/data', params=params, timeout=10)
        d = r.json()
        n = len(d.get('data', []))
        print(f"  {'OK' if n>0 else '--'}  {dataset}: {n} 筆")
        if n > 0:
            print(f"      欄位: {list(d['data'][0].keys())}")
    except Exception as e:
        print(f"  !!  {dataset}: {e}")
