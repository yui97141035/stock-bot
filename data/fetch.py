"""
data/fetch.py
從 FinMind 抓取台股歷史資料
"""
from FinMind.data import DataLoader
import pandas as pd
import os

def get_price_history(stock_id: str, start: str, end: str = None, token: str = None) -> pd.DataFrame:
    """
    抓取個股日線資料
    stock_id: 股票代號，例如 '2330'
    start: 開始日期，格式 'YYYY-MM-DD'
    end: 結束日期，不填則到今天
    """
    dl = DataLoader()
    if token:
        dl.login_by_token(api_token=token)

    df = dl.taiwan_stock_daily(
        stock_id=stock_id,
        start_date=start,
        end_date=end or pd.Timestamp.today().strftime('%Y-%m-%d')
    )
    if df.empty or 'date' not in df.columns:
        return pd.DataFrame()
    df = df.sort_values('date').reset_index(drop=True)
    return df


if __name__ == '__main__':
    # 測試抓台積電近一年資料
    df = get_price_history('2330', '2024-01-01')
    print(df.tail())
    print(f"共 {len(df)} 筆資料")
