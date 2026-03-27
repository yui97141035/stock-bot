# -*- coding: utf-8 -*-
"""
notify/daily_report.py
每日開盤前 + 收盤後報告
包含：技術面、歷史勝率、月營收、EPS 綜合進場判斷
"""
import sys, os, argparse
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from data.cache import get_price_cached, update_all
from data.fundamental import get_monthly_revenue, get_eps

load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'configs', 'accounts.env'))
BOT_TOKEN  = os.getenv('DISCORD_BOT_TOKEN')
CHANNEL_ID = '1471384671651758125'

ETF_LIST = {
    '0050': '元大台灣50',
    '00662': '富邦NASDAQ',
    '009816': '凱基台灣TOP50',
}
STOCK_LIST = {
    '1519': '華城',
    '2330': '台積電',
    '2382': '廣達',
    '3017': '奇鋐',
    '3131': '弘塑',
    '3231': '緯創',
    '3324': '雙鴻',
    '8064': '東捷',
}


def send(msg: str):
    if not BOT_TOKEN:
        print(msg)
        return
    # Discord 2000字限制
    chunks = [msg[i:i+1990] for i in range(0, len(msg), 1990)]
    for chunk in chunks:
        r = requests.post(
            f'https://discord.com/api/v10/channels/{CHANNEL_ID}/messages',
            json={'content': chunk},
            headers={'Authorization': f'Bot {BOT_TOKEN}', 'Content-Type': 'application/json'}
        )
        if r.status_code != 200:
            print(f'推播失敗 {r.status_code}: {r.text}')


def historical_analysis(df: pd.DataFrame, short=5, long=20) -> dict:
    """
    歷史回測：計算均線交叉策略的歷史勝率
    用過去所有資料計算每次買入訊號後持有 N 天的勝率
    """
    df = df.copy()
    df['ma_s'] = df['close'].rolling(short).mean()
    df['ma_l'] = df['close'].rolling(long).mean()
    df['cross_up'] = (df['ma_s'] > df['ma_l']) & (df['ma_s'].shift(1) <= df['ma_l'].shift(1))

    hold_days  = [5, 10, 20]
    results    = {}
    entry_dates = df[df['cross_up']].index.tolist()

    for hd in hold_days:
        wins = 0
        total = 0
        returns = []
        for idx in entry_dates:
            pos = df.index.get_loc(idx)
            if pos + hd < len(df):
                entry_price = df['close'].iloc[pos]
                exit_price  = df['close'].iloc[pos + hd]
                ret = (exit_price / entry_price - 1) * 100
                returns.append(ret)
                if ret > 0:
                    wins += 1
                total += 1
        if total > 0:
            results[hd] = {
                'win_rate': round(wins / total * 100, 1),
                'avg_return': round(np.mean(returns), 2),
                'total': total,
            }
    return results


def analyze(sid: str, name: str, is_etf: bool = False) -> dict:
    df = get_price_cached(sid, '2020-01-01')
    if df.empty:
        raise ValueError(f'{sid} 無快取資料')
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    c    = df['close'].iloc[-1]
    o    = df['open'].iloc[-1]
    h    = df['max'].iloc[-1]
    l    = df['min'].iloc[-1]
    c1   = df['close'].iloc[-2]
    chg  = (c - c1) / c1 * 100
    vol  = df['Trading_Volume'].iloc[-1]
    date = df['date'].iloc[-1]

    # 均線
    ma5  = df['close'].tail(5).mean()
    ma10 = df['close'].tail(10).mean()
    ma20 = df['close'].tail(20).mean()
    ma60 = df['close'].tail(60).mean()
    ma120= df['close'].tail(120).mean()
    pm5  = df['close'].tail(6).head(5).mean()
    pm20 = df['close'].tail(21).head(20).mean()

    trend_up  = ma5 > ma20
    golden    = pm5 <= pm20 and ma5 > ma20
    dead      = pm5 >= pm20 and ma5 < ma20
    above_60  = c > ma60
    above_120 = c > ma120

    # K線
    body  = abs(c - o)
    total = h - l if h != l else 0.0001
    bull_k = c > o and body/total >= 0.6 and c >= (h+l)/2

    # 近20日支撐壓力
    r20     = df.tail(20)
    support = r20['min'].min()
    resist  = r20['max'].max()

    # 歷史勝率（從2020起算）
    hist = historical_analysis(df)

    # 52週高低
    r252    = df.tail(252)
    high52  = r252['max'].max()
    low52   = r252['min'].min()
    pos52   = (c - low52) / (high52 - low52) * 100 if high52 != low52 else 50

    # 月營收 & EPS（個股才抓）
    rev_signal = ''
    eps_signal = ''
    if not is_etf:
        try:
            rev = get_monthly_revenue(sid, '2024-01-01')
            if not rev.empty and len(rev) >= 2:
                mom = (rev['revenue'].iloc[-1] / rev['revenue'].iloc[-2] - 1) * 100
                yoy = None
                if len(rev) >= 13:
                    yoy = (rev['revenue'].iloc[-1] / rev['revenue'].iloc[-13] - 1) * 100
                yoy_str = f" 年增{yoy:+.1f}%" if yoy else ''
                rev_signal = f"月增{mom:+.1f}%{yoy_str}"
        except:
            pass
        try:
            eps_df = get_eps(sid, '2023-01-01')
            if not eps_df.empty:
                e = eps_df['eps'].iloc[-1]
                e1 = eps_df['eps'].iloc[-2] if len(eps_df) >= 2 else e
                eq = (e - e1) / abs(e1) * 100 if e1 != 0 else 0
                eps_signal = f"EPS {e}（季增{eq:+.1f}%）"
        except:
            pass

    # 綜合進場判斷
    score = 0
    reasons = []

    if golden:
        score += 3; reasons.append('黃金交叉')
    elif trend_up and bull_k:
        score += 2; reasons.append('趨勢+強陽線')
    elif trend_up:
        score += 1; reasons.append('上升趨勢')

    if above_60:
        score += 1; reasons.append('站上MA60')
    if above_120:
        score += 1; reasons.append('站上MA120')
    if pos52 > 70:
        score += 1; reasons.append(f'52週高點附近({pos52:.0f}%)')

    if not is_etf:
        if '月增+' in rev_signal and float(rev_signal.split('月增')[1].split('%')[0]) > 5:
            score += 2; reasons.append(f'營收{rev_signal}')
        if eps_signal and '季增+' in eps_signal:
            score += 1; reasons.append(eps_signal)
        if dead or not trend_up:
            score -= 2

    if score >= 5:
        verdict = 'BUY'
    elif score >= 3:
        verdict = 'WATCH'
    else:
        verdict = 'WAIT'

    return {
        'sid': sid, 'name': name, 'date': date, 'is_etf': is_etf,
        'close': c, 'chg': chg, 'vol': vol,
        'ma5': round(ma5,2), 'ma10': round(ma10,2),
        'ma20': round(ma20,2), 'ma60': round(ma60,2), 'ma120': round(ma120,2),
        'trend': '上升' if trend_up else '下降',
        'golden': golden, 'dead': dead,
        'above_60': above_60, 'above_120': above_120,
        'support': round(support,2), 'resist': round(resist,2),
        'high52': round(high52,2), 'low52': round(low52,2), 'pos52': round(pos52,1),
        'hist': hist,
        'rev_signal': rev_signal,
        'eps_signal': eps_signal,
        'score': score, 'verdict': verdict, 'reasons': reasons,
    }


def build_report(mode: str) -> str:
    today = pd.Timestamp.today().strftime('%Y-%m-%d')
    icon  = '🌅' if mode == 'open' else '📊'
    title = '開盤前趨勢' if mode == 'open' else '收盤後報告'

    lines = [f"{icon} **{title}** {today}"]
    lines.append("─" * 30)

    # ETF 持倉
    lines.append("**【ETF 持倉】**")
    for sid, name in ETF_LIST.items():
        try:
            r = analyze(sid, name, is_etf=True)
            trend_icon = '▲' if r['trend'] == '上升' else '▼'
            h5 = r['hist'].get(5, {})
            wr_str = f"  歷史勝率(5日)：{h5.get('win_rate','N/A')}%  平均報酬：{h5.get('avg_return','N/A')}%" if h5 else ''
            lines.append(
                f"`{name}({sid})`  {r['close']:.2f}  {r['chg']:+.2f}%  "
                f"趨勢{trend_icon}  MA5:{r['ma5']}  MA20:{r['ma20']}"
                f"{wr_str}"
            )
        except Exception as e:
            lines.append(f"`{name}({sid})`  取得失敗: {e}")

    lines.append("")
    lines.append("**【個股監控】**")

    buy_list   = []
    watch_list = []
    wait_list  = []

    for sid, name in STOCK_LIST.items():
        try:
            r = analyze(sid, name, is_etf=False)
            if r['verdict'] == 'BUY':
                buy_list.append(r)
            elif r['verdict'] == 'WATCH':
                watch_list.append(r)
            else:
                wait_list.append(r)
        except Exception as e:
            wait_list.append({'sid': sid, 'name': name, 'verdict': 'WAIT',
                               'close': 0, 'chg': 0, 'trend': '?',
                               'reasons': [], 'hist': {}, 'rev_signal': '', 'eps_signal': ''})

    if buy_list:
        lines.append("🟢 **進場訊號**")
        for r in buy_list:
            h5  = r['hist'].get(5, {})
            h10 = r['hist'].get(10, {})
            lines.append(
                f"  **{r['name']}({r['sid']})**  收盤：{r['close']}  {r['chg']:+.1f}%\n"
                f"  趨勢：{r['trend']}  52週位置：{r['pos52']}%  分數：{r['score']}\n"
                f"  歷史勝率 — 5日:{h5.get('win_rate','N/A')}%({h5.get('avg_return','N/A')}%)  "
                f"10日:{h10.get('win_rate','N/A')}%({h10.get('avg_return','N/A')}%)\n"
                f"  {'營收：' + r['rev_signal'] if r['rev_signal'] else ''}"
                f"  {'EPS：' + r['eps_signal'] if r['eps_signal'] else ''}\n"
                f"  根據：{', '.join(r['reasons'])}"
            )

    if watch_list:
        lines.append("🔵 **值得關注**（尚未完全確認）")
        for r in watch_list:
            h5 = r['hist'].get(5, {})
            lines.append(
                f"  {r['name']}({r['sid']})  {r['close']}  {r['chg']:+.1f}%  "
                f"趨勢：{r['trend']}  歷史勝率5日：{h5.get('win_rate','N/A')}%  "
                f"根據：{', '.join(r['reasons']) if r['reasons'] else '訊號不足'}"
            )

    if wait_list:
        wait_names = '  '.join([f"{r['name']}({r['sid']})" for r in wait_list])
        lines.append(f"⚪ **等待**：{wait_names}")

    lines.append("")
    lines.append("_判斷依據：技術面 + 月營收 + EPS + 歷史勝率（2020至今）_")
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['open', 'close'], default='close')
    args = parser.parse_args()

    print(f"執行 {args.mode} 報告...")
    report = build_report(args.mode)
    send(report)
    print("完成")
