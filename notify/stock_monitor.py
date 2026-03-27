# -*- coding: utf-8 -*-
"""
notify/stock_monitor.py
個股基本面 + 技術面綜合監控
每月10日（營收公布後）+ 每週五收盤後執行
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
import pandas as pd
from dotenv import load_dotenv
from data.cache import get_price_cached, update_revenue, update_eps, load_revenue, load_eps

load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'configs', 'accounts.env'))

BOT_TOKEN  = os.getenv('DISCORD_BOT_TOKEN')
CHANNEL_ID = '1471384671651758125'

# 監控個股
STOCKS = [
    {'id': '1519', 'name': '華城'},
    {'id': '2330', 'name': '台積電'},
    {'id': '2382', 'name': '廣達'},
    {'id': '3017', 'name': '奇鋐'},
    {'id': '3131', 'name': '弘塑'},
    {'id': '3231', 'name': '緯創'},
    {'id': '3324', 'name': '雙鴻'},
    {'id': '8064', 'name': '東捷'},
]


def send_discord(msg: str):
    if not BOT_TOKEN:
        print(f"[未設定Token] {msg[:80]}")
        return
    r = requests.post(
        f'https://discord.com/api/v10/channels/{CHANNEL_ID}/messages',
        json={'content': msg},
        headers={'Authorization': f'Bot {BOT_TOKEN}', 'Content-Type': 'application/json'}
    )
    print(f"[{'OK' if r.status_code==200 else r.status_code}] {msg[:60]}...")


def analyze_stock(sid: str, name: str) -> dict:
    result = {'sid': sid, 'name': name, 'signals': [], 'warnings': [], 'verdict': ''}

    # ── 技術面 ──────────────────────────────────────────
    try:
        price_df = get_price_cached(sid, '2020-01-01')
        price_df = price_df.sort_values('date').reset_index(drop=True)
        c     = price_df['close'].iloc[-1]
        o     = price_df['open'].iloc[-1]
        h     = price_df['max'].iloc[-1]
        l     = price_df['min'].iloc[-1]
        date  = price_df['date'].iloc[-1]
        chg   = (c - price_df['close'].iloc[-2]) / price_df['close'].iloc[-2] * 100
        ma5   = price_df['close'].tail(5).mean()
        ma20  = price_df['close'].tail(20).mean()
        ma60  = price_df['close'].tail(60).mean()
        pm5   = price_df['close'].tail(6).head(5).mean()
        pm20  = price_df['close'].tail(21).head(20).mean()

        trend_up   = ma5 > ma20
        golden     = pm5 <= pm20 and ma5 > ma20
        dead       = pm5 >= pm20 and ma5 < ma20
        body       = abs(c - o)
        total      = h - l if h != l else 0.0001
        bull_k     = c > o and body/total >= 0.6 and c >= (h+l)/2

        result['price'] = c
        result['chg']   = chg
        result['trend'] = '上升' if trend_up else '下降'
        result['ma5']   = ma5
        result['ma20']  = ma20
        result['ma60']  = ma60

        if golden:
            result['signals'].append('技術：黃金交叉（MA5穿越MA20）')
        elif trend_up and bull_k:
            result['signals'].append('技術：上升趨勢 + 強陽線')
        if dead:
            result['warnings'].append('技術：死亡交叉（轉空）')
        elif not trend_up:
            result['warnings'].append('技術：下降趨勢，不宜進場')

    except Exception as e:
        result['warnings'].append(f'技術面取得失敗: {e}')

    # ── 月營收 ──────────────────────────────────────────
    try:
        rev = update_revenue(sid)
        if not rev.empty and len(rev) >= 2:
            latest_rev = rev.iloc[-1]
            prev_rev   = rev.iloc[-2]
            mom = (latest_rev['revenue'] / prev_rev['revenue'] - 1) * 100
            # 年增率（跟去年同月比）
            if len(rev) >= 13:
                yoy_rev = rev.iloc[-13]['revenue']
                yoy = (latest_rev['revenue'] / yoy_rev - 1) * 100
            else:
                yoy = None

            result['rev_mom'] = round(mom, 1)
            result['rev_yoy'] = round(yoy, 1) if yoy else None
            result['rev_date'] = str(latest_rev['date'].date())

            if mom > 10:
                result['signals'].append(f"營收：月增 +{mom:.1f}%（強勁成長）")
            elif mom > 0:
                result['signals'].append(f"營收：月增 +{mom:.1f}%（溫和成長）")
            else:
                result['warnings'].append(f"營收：月減 {mom:.1f}%（注意）")

            if yoy and yoy > 20:
                result['signals'].append(f"營收：年增 +{yoy:.1f}%（高速成長）")
            elif yoy and yoy < -10:
                result['warnings'].append(f"營收：年減 {yoy:.1f}%（衰退）")

    except Exception as e:
        result['warnings'].append(f'營收資料取得失敗: {e}')

    # ── EPS ─────────────────────────────────────────────
    try:
        eps_df = update_eps(sid)
        if not eps_df.empty and len(eps_df) >= 2:
            latest_eps = eps_df.iloc[-1]
            prev_eps   = eps_df.iloc[-2]
            eps_chg    = (latest_eps['eps'] - prev_eps['eps']) / abs(prev_eps['eps']) * 100 \
                         if prev_eps['eps'] != 0 else 0
            result['eps']      = latest_eps['eps']
            result['eps_date'] = str(latest_eps['date'].date())
            result['eps_chg']  = round(eps_chg, 1)

            if eps_chg > 20:
                result['signals'].append(f"EPS：{latest_eps['eps']} 季增 +{eps_chg:.1f}%（加速成長）")
            elif latest_eps['eps'] > 0:
                result['signals'].append(f"EPS：{latest_eps['eps']}（獲利中）")
            else:
                result['warnings'].append(f"EPS：{latest_eps['eps']}（虧損）")

    except Exception as e:
        result['warnings'].append(f'EPS資料取得失敗: {e}')

    # ── 綜合判斷 ─────────────────────────────────────────
    tech_ok = '技術：' in ' '.join(result['signals'])
    rev_ok  = '營收：' in ' '.join(result['signals'])

    if len(result['signals']) >= 3 and tech_ok and rev_ok:
        result['verdict'] = 'BUY'
    elif len(result['signals']) >= 2 and tech_ok:
        result['verdict'] = 'WATCH'
    elif result['warnings']:
        result['verdict'] = 'WAIT'
    else:
        result['verdict'] = 'WAIT'

    return result


def format_discord_msg(r: dict) -> str:
    verdict_map = {
        'BUY':   '🟢 進場訊號',
        'WATCH': '🔵 值得關注',
        'WAIT':  '⚪ 繼續等待',
    }
    v = verdict_map.get(r['verdict'], '⚪ 繼續等待')

    lines = [f"**{r['name']}（{r['sid']}）** {v}"]
    lines.append(f"收盤 {r.get('price','N/A')} ({r.get('chg',0):+.1f}%)  趨勢：{r.get('trend','N/A')}")

    if r.get('eps'):
        lines.append(f"最新EPS：{r['eps']} ({r.get('eps_date','')})  季增：{r.get('eps_chg',0):+.1f}%")
    if r.get('rev_mom') is not None:
        yoy_str = f"  年增：{r['rev_yoy']:+.1f}%" if r.get('rev_yoy') else ''
        lines.append(f"最新營收月增：{r['rev_mom']:+.1f}%{yoy_str}  ({r.get('rev_date','')})")

    if r['signals']:
        lines.append("正面訊號：" + "、".join([s.split('：')[1] for s in r['signals']]))
    if r['warnings']:
        lines.append("注意事項：" + "、".join([w.split('：')[1] if '：' in w else w for w in r['warnings']]))

    return '\n'.join(lines)


def run_monitor():
    today = pd.Timestamp.today().strftime('%Y-%m-%d')
    print(f"=== 個股監控 {today} ===\n")

    buy_signals  = []
    watch_signals = []
    wait_list    = []

    for s in STOCKS:
        print(f"分析 {s['name']}({s['id']})...", end=' ', flush=True)
        r = analyze_stock(s['id'], s['name'])
        print(r['verdict'])

        if r['verdict'] == 'BUY':
            buy_signals.append(r)
        elif r['verdict'] == 'WATCH':
            watch_signals.append(r)
        else:
            wait_list.append(r)

    # 組合 Discord 訊息
    msg_parts = [f"📈 **個股監控週報** {today}"]

    if buy_signals:
        msg_parts.append("\n**——— 進場訊號 ———**")
        for r in buy_signals:
            msg_parts.append(format_discord_msg(r))

    if watch_signals:
        msg_parts.append("\n**——— 值得關注 ———**")
        for r in watch_signals:
            msg_parts.append(format_discord_msg(r))

    if wait_list:
        names = '、'.join([f"{r['name']}({r['sid']})" for r in wait_list])
        msg_parts.append(f"\n**——— 繼續等待 ———**\n{names}")

    msg_parts.append("\n_技術面 + 月營收 + EPS 三項綜合判斷_")

    full_msg = '\n'.join(msg_parts)

    # Discord 限制 2000 字，超過就切割
    if len(full_msg) <= 2000:
        send_discord(full_msg)
    else:
        send_discord(msg_parts[0] + '\n（詳細見下方）')
        for r in buy_signals + watch_signals:
            send_discord(format_discord_msg(r))
        if wait_list:
            names = '、'.join([f"{r['name']}({r['sid']})" for r in wait_list])
            send_discord(f"繼續等待：{names}")


if __name__ == '__main__':
    run_monitor()
