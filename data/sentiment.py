# -*- coding: utf-8 -*-
"""
data/sentiment.py
市場情緒指標：三大法人買賣超 + 借券賣出 + 成交量分析
"""
import sys, os, requests
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'configs', 'accounts.env'))

API   = 'https://api.finmindtrade.com/api/v4/data'


def _fetch(dataset, stock_id, start='2026-01-01'):
    token = os.getenv('FINMIND_TOKEN', '')
    today = pd.Timestamp.today().strftime('%Y-%m-%d')
    r = requests.get(API, params=dict(
        dataset=dataset, data_id=stock_id,
        start_date=start, end_date=today, token=token
    ), timeout=15)
    data = r.json().get('data', [])
    return pd.DataFrame(data) if data else pd.DataFrame()


def get_institutional(stock_id: str) -> dict:
    """
    三大法人買賣超（外資、投信、自營商）
    正數 = 買超（看多），負數 = 賣超（看空）
    """
    df = _fetch('TaiwanStockInstitutionalInvestorsBuySell', stock_id)
    if df.empty:
        return {}

    df['date'] = pd.to_datetime(df['date'])
    df['net']  = pd.to_numeric(df['buy'], errors='coerce') - \
                 pd.to_numeric(df['sell'], errors='coerce')
    df = df.sort_values('date')

    latest_date = df['date'].max()
    today_df    = df[df['date'] == latest_date]

    result = {'date': str(latest_date.date()), 'details': {}}
    total_net = 0
    for _, row in today_df.iterrows():
        name = row['name']
        net  = row['net']
        result['details'][name] = int(net)
        total_net += net

    result['total_net'] = int(total_net)

    # 近5日累計
    recent5 = df[df['date'] >= latest_date - pd.Timedelta(days=7)]
    result['net_5d'] = int(recent5['net'].sum())

    return result


def get_securities_lending(stock_id: str) -> dict:
    """
    借券賣出（機構借股票來放空）
    量大 = 機構在做空，看空訊號
    """
    df = _fetch('TaiwanStockSecuritiesLending', stock_id)
    if df.empty:
        return {}

    df['date']   = pd.to_datetime(df['date'])
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
    df = df.sort_values('date')

    # 近5日借券賣出量
    latest = df['date'].max()
    recent = df[df['date'] >= latest - pd.Timedelta(days=7)]
    vol_5d = int(recent['volume'].sum())
    vol_today = int(df[df['date'] == latest]['volume'].sum())

    # 跟近30日均量比
    avg30 = df.tail(30)['volume'].mean()

    return {
        'date':      str(latest.date()),
        'today':     vol_today,
        'vol_5d':    vol_5d,
        'avg30':     int(avg30),
        'vs_avg':    round((vol_today / avg30 - 1) * 100, 1) if avg30 > 0 else 0,
    }


def volume_analysis(df_price: pd.DataFrame) -> dict:
    """
    成交量分析（價量配合）
    """
    if len(df_price) < 6:
        return {}

    df   = df_price.copy()
    last = df.iloc[-1]
    prev = df.iloc[-2]

    price_up  = last['close'] > prev['close']
    vol_today = last['Trading_Volume']
    avg5      = df['Trading_Volume'].tail(5).mean()
    avg20     = df['Trading_Volume'].tail(20).mean()

    vol_vs_avg5  = (vol_today / avg5  - 1) * 100
    vol_vs_avg20 = (vol_today / avg20 - 1) * 100

    # 價量配合判斷
    if price_up and vol_vs_avg5 > 20:
        signal = '量增價漲（多方強勢）'
        bullish = True
    elif price_up and vol_vs_avg5 < -20:
        signal = '量縮價漲（反彈力道弱，小心假突破）'
        bullish = False
    elif not price_up and vol_vs_avg5 > 20:
        signal = '量增價跌（空方強勢，賣壓重）'
        bullish = False
    elif not price_up and vol_vs_avg5 < -20:
        signal = '量縮價跌（賣壓輕，可能快止跌）'
        bullish = True
    else:
        signal = '量價正常，無明顯訊號'
        bullish = None

    return {
        'today':       int(vol_today),
        'avg5':        int(avg5),
        'avg20':       int(avg20),
        'vs_avg5_pct': round(vol_vs_avg5, 1),
        'price_up':    price_up,
        'signal':      signal,
        'bullish':     bullish,
    }


def full_sentiment(stock_id: str, df_price: pd.DataFrame) -> dict:
    """
    綜合做空/做多情緒分析
    回傳分數：正數看多，負數看空
    """
    score   = 0
    signals = []
    warnings= []

    # 三大法人
    inst = get_institutional(stock_id)
    if inst:
        net = inst.get('total_net', 0)
        net5 = inst.get('net_5d', 0)
        if net > 0:
            score += 2
            signals.append(f"三大法人今日買超 {net:,} 張")
        elif net < 0:
            score -= 2
            warnings.append(f"三大法人今日賣超 {abs(net):,} 張")
        if net5 < 0:
            score -= 1
            warnings.append(f"三大法人近5日累計賣超 {abs(net5):,} 張")

    # 借券
    lending = get_securities_lending(stock_id)
    if lending:
        vs = lending.get('vs_avg', 0)
        if vs > 50:
            score -= 2
            warnings.append(f"借券賣出量是均量的 {vs+100:.0f}%（機構放空增加）")
        elif vs > 20:
            score -= 1
            warnings.append(f"借券賣出略增（+{vs:.0f}%）")

    # 成交量
    vol = volume_analysis(df_price)
    if vol:
        if vol.get('bullish') == True:
            score += 1
            signals.append(vol['signal'])
        elif vol.get('bullish') == False:
            score -= 1
            warnings.append(vol['signal'])
        else:
            signals.append(vol['signal'])

    # 綜合判斷
    if score >= 2:
        verdict = '多方有利'
    elif score <= -2:
        verdict = '空方警示'
    else:
        verdict = '中性'

    return {
        'score': score, 'verdict': verdict,
        'signals': signals, 'warnings': warnings,
        'institutional': inst,
        'lending': lending,
        'volume': vol,
    }


if __name__ == '__main__':
    from data.cache import get_price_cached
    for sid in ['2330', '3017', '3131', '8064']:
        df = get_price_cached(sid, '2025-01-01')
        r  = full_sentiment(sid, df)
        print(f"\n{sid}  {r['verdict']}（分數 {r['score']:+d}）")
        for s in r['signals']:
            print(f"  + {s}")
        for w in r['warnings']:
            print(f"  - {w}")
