# -*- coding: utf-8 -*-
"""
data/cache.py
本地資料快取：歷史資料存 CSV，每次只補抓最新部分
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import time
from pathlib import Path
from data.fetch import get_price_history
from data.fundamental import get_monthly_revenue, get_eps

CACHE_DIR = Path(os.path.dirname(__file__)).parent / 'cache'
CACHE_DIR.mkdir(exist_ok=True)

START_DATE = '2020-01-01'   # 快取起始日期

ALL_STOCKS = [
    '1519', '2330', '2382', '3017', '3131',
    '3231', '3324', '8064',
    '0050', '0052', '0056', '006208', '00662', '00878', '009816',
]


def cache_path(sid: str, dtype: str = 'price') -> Path:
    return CACHE_DIR / f'{sid}_{dtype}.csv'


def load_price(sid: str) -> pd.DataFrame:
    """讀本地快取，沒有就回傳空 DataFrame"""
    p = cache_path(sid, 'price')
    if p.exists():
        df = pd.read_csv(p, parse_dates=['date'])
        return df.sort_values('date').reset_index(drop=True)
    return pd.DataFrame()


def save_price(sid: str, df: pd.DataFrame):
    df.to_csv(cache_path(sid, 'price'), index=False)


def update_price(sid: str, force: bool = False) -> pd.DataFrame:
    """
    更新單支股票快取
    - 本地有資料：只補抓「上次最新日期+1天」到今天
    - 本地沒資料：從 START_DATE 全部抓
    - force=True：強制重抓全部
    """
    existing = pd.DataFrame() if force else load_price(sid)
    today = pd.Timestamp.today().strftime('%Y-%m-%d')

    if existing.empty:
        start = START_DATE
    else:
        last_date = existing['date'].max()
        # 如果今天已經是最新，不需要更新
        if pd.to_datetime(last_date).strftime('%Y-%m-%d') >= today:
            return existing
        start = (last_date + pd.Timedelta(days=1)).strftime('%Y-%m-%d')

    token = os.getenv('FINMIND_TOKEN', '')
    new_df = get_price_history(sid, start, today, token or None)

    if new_df.empty:
        return existing

    new_df['date'] = pd.to_datetime(new_df['date'])

    if existing.empty:
        combined = new_df
    else:
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)

    save_price(sid, combined)
    return combined


def get_price_cached(sid: str, start: str = None) -> pd.DataFrame:
    """
    取得股價資料（優先從快取，自動補抓最新）
    """
    df = update_price(sid)
    if df.empty:
        return df
    if start:
        df = df[df['date'] >= pd.to_datetime(start)]
    return df.reset_index(drop=True)


def update_all(force: bool = False):
    """更新所有股票快取"""
    total = len(ALL_STOCKS)
    results = {'ok': [], 'fail': []}

    for i, sid in enumerate(ALL_STOCKS):
        print(f'[{i+1}/{total}] {sid}...', end=' ', flush=True)
        try:
            df = update_price(sid, force=force)
            last = df['date'].max().strftime('%Y-%m-%d') if not df.empty else 'N/A'
            rows = len(df)
            print(f'OK  {rows} 筆  最新:{last}')
            results['ok'].append(sid)
        except Exception as e:
            print(f'失敗: {e}')
            results['fail'].append(sid)
        time.sleep(0.3)  # 避免觸發 API 限速

    print(f"\n完成：{len(results['ok'])} 支成功，{len(results['fail'])} 支失敗")
    if results['fail']:
        print(f"失敗清單：{results['fail']}")
    return results


def load_revenue(sid: str) -> pd.DataFrame:
    p = cache_path(sid, 'revenue')
    if p.exists():
        df = pd.read_csv(p, parse_dates=['date'])
        return df.sort_values('date').reset_index(drop=True)
    return pd.DataFrame()


def update_revenue(sid: str) -> pd.DataFrame:
    """更新月營收快取（月更新）"""
    existing = load_revenue(sid)
    today = pd.Timestamp.today()

    if not existing.empty:
        last = existing['date'].max()
        # 月營收每月10日更新，若本月已有最新就跳過
        if last.year == today.year and last.month == today.month:
            return existing

    try:
        new_df = get_monthly_revenue(sid, '2020-01-01')
        if not new_df.empty:
            new_df.to_csv(cache_path(sid, 'revenue'), index=False)
            return new_df
    except Exception as e:
        print(f'  {sid} 月營收失敗: {e}')
    return existing


def load_eps(sid: str) -> pd.DataFrame:
    p = cache_path(sid, 'eps')
    if p.exists():
        df = pd.read_csv(p, parse_dates=['date'])
        return df.sort_values('date').reset_index(drop=True)
    return pd.DataFrame()


def update_eps(sid: str) -> pd.DataFrame:
    """更新 EPS 快取（季更新）"""
    existing = load_eps(sid)
    today = pd.Timestamp.today()

    if not existing.empty:
        last = existing['date'].max()
        # 超過 45 天才重抓（季報公布週期）
        if (today - last).days < 45:
            return existing

    try:
        new_df = get_eps(sid, '2020-01-01')
        if not new_df.empty:
            new_df.to_csv(cache_path(sid, 'eps'), index=False)
            return new_df
    except Exception as e:
        print(f'  {sid} EPS 失敗: {e}')
    return existing


def cache_status():
    """顯示目前快取狀態"""
    print(f"\n{'代號':>8}  {'筆數':>6}  {'最舊':>12}  {'最新':>12}  {'檔案大小':>10}")
    print('-' * 60)
    total_size = 0
    for sid in ALL_STOCKS:
        p = cache_path(sid, 'price')
        if p.exists():
            df = pd.read_csv(p, parse_dates=['date'])
            size = p.stat().st_size / 1024
            total_size += size
            print(f'{sid:>8}  {len(df):>6}  {df["date"].min().strftime("%Y-%m-%d"):>12}  '
                  f'{df["date"].max().strftime("%Y-%m-%d"):>12}  {size:>8.1f} KB')
        else:
            print(f'{sid:>8}  {"無資料":>6}')
    print(f'\n總計快取大小：{total_size:.1f} KB（{total_size/1024:.2f} MB）')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--force',  action='store_true', help='強制重抓全部資料')
    parser.add_argument('--status', action='store_true', help='顯示快取狀態')
    args = parser.parse_args()

    if args.status:
        cache_status()
    else:
        print(f'開始更新快取（{"強制重抓" if args.force else "只補最新"}）...\n')
        update_all(force=args.force)
        print()
        cache_status()
