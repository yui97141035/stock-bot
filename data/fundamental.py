# -*- coding: utf-8 -*-
"""
data/fundamental.py
基本面資料：月營收、財報、股東會日程、除權息
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os, requests
import pandas as pd

FINMIND_API = 'https://api.finmindtrade.com/api/v4/data'
TWSE_API    = 'https://www.twse.com.tw/exchangeReport/STOCK_DAY'


def _finmind(dataset, stock_id, start='2023-01-01', end=None):
    token = os.getenv('FINMIND_TOKEN', '')
    end   = end or pd.Timestamp.today().strftime('%Y-%m-%d')
    params = dict(dataset=dataset, data_id=stock_id,
                  start_date=start, end_date=end, token=token)
    r = requests.get(FINMIND_API, params=params, timeout=15)
    data = r.json().get('data', [])
    return pd.DataFrame(data) if data else pd.DataFrame()


def get_monthly_revenue(stock_id: str, start='2023-01-01') -> pd.DataFrame:
    """月營收（每月10日更新）"""
    df = _finmind('TaiwanStockMonthRevenue', stock_id, start)
    if df.empty:
        return df
    df['date'] = pd.to_datetime(df['date'])
    df['revenue'] = pd.to_numeric(df['revenue'], errors='coerce')
    df = df.sort_values('date').reset_index(drop=True)
    df['yoy'] = df['revenue'].pct_change(12) * 100   # 年增率
    df['mom'] = df['revenue'].pct_change(1) * 100    # 月增率
    return df


def get_eps(stock_id: str, start='2022-01-01') -> pd.DataFrame:
    """EPS（從財務報表取出）"""
    df = _finmind('TaiwanStockFinancialStatements', stock_id, start)
    if df.empty:
        return df
    eps = df[df['type'] == 'EPS'][['date', 'value']].copy()
    eps.columns = ['date', 'eps']
    eps['date'] = pd.to_datetime(eps['date'])
    eps['eps']  = pd.to_numeric(eps['eps'], errors='coerce')
    return eps.sort_values('date').reset_index(drop=True)


def get_shareholder_meeting(year: int = None) -> pd.DataFrame:
    """
    股東會日程（從公開資訊觀測站）
    回傳今年所有股東常會日期
    """
    import datetime
    year = year or datetime.date.today().year
    url  = f'https://mops.twse.com.tw/mops/web/ajax_t108sb01'
    params = {
        'encodeURIComponent': 1,
        'step': 1,
        'firstin': 1,
        'off': 1,
        'keyword4': '',
        'code1': '',
        'TYPEK2': '',
        'checkbtn': '',
        'queryName': 'co_id',
        'inpuType': 'co_id',
        'TYPEK': 'all',
        'isnew': 'false',
        'co_id': '',
        'year': str(year - 1911),  # 民國年
        'month': '',
        'b_date': '',
        'e_date': '',
    }
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://mops.twse.com.tw/'}
    try:
        r = requests.post(url, data=params, headers=headers, timeout=15)
        # 解析 HTML 表格
        tables = pd.read_html(r.text, encoding='utf-8')
        if tables:
            df = tables[0]
            df.columns = df.columns.droplevel(0) if isinstance(df.columns, pd.MultiIndex) else df.columns
            return df
    except Exception as e:
        print(f"股東會資料取得失敗: {e}")
    return pd.DataFrame()


def get_dividend(stock_id: str, start='2020-01-01') -> pd.DataFrame:
    """除權息結果"""
    df = _finmind('TaiwanStockDividendResult', stock_id, start)
    if df.empty:
        return df
    df['date'] = pd.to_datetime(df['date'])
    return df.sort_values('date').reset_index(drop=True)


if __name__ == '__main__':
    # 測試
    print("=== 月營收（台積電最近6個月）===")
    rev = get_monthly_revenue('2330', '2025-06-01')
    if not rev.empty:
        print(rev[['date','revenue','yoy','mom']].tail(6).to_string(index=False))

    print("\n=== EPS（台積電近8季）===")
    eps = get_eps('2330', '2024-01-01')
    if not eps.empty:
        print(eps.tail(8).to_string(index=False))
