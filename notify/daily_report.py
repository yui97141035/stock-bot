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
from data.sentiment import full_sentiment

load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'configs', 'accounts.env'))

# 台灣國定假日（每年補充）
TW_HOLIDAYS = {
    '2026-01-01','2026-01-27','2026-01-28','2026-01-29','2026-01-30',
    '2026-02-02','2026-02-27','2026-02-28','2026-04-03','2026-04-04',
    '2026-04-05','2026-05-01','2026-06-19','2026-09-04','2026-10-01',
    '2026-10-02','2026-10-10',
}

def next_trading_day() -> str:
    """找下一個交易日（排除週末+國定假日）"""
    d = pd.Timestamp.today() + pd.Timedelta(days=1)
    for _ in range(14):
        if d.weekday() < 5 and d.strftime('%Y-%m-%d') not in TW_HOLIDAYS:
            return d.strftime('%Y-%m-%d（%A）').replace(
                'Monday','一').replace('Tuesday','二').replace(
                'Wednesday','三').replace('Thursday','四').replace('Friday','五')
        d += pd.Timedelta(days=1)
    return '下個交易日'
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
    title = '開盤前' if mode == 'open' else '收盤後'

    buy_list   = []
    watch_list = []
    wait_list  = []

    # 分析個股
    for sid, name in STOCK_LIST.items():
        try:
            r = analyze(sid, name, is_etf=False)
            if r['verdict'] == 'BUY':
                buy_list.append(r)
            elif r['verdict'] == 'WATCH':
                watch_list.append(r)
            else:
                wait_list.append(r)
        except:
            wait_list.append({'sid': sid, 'name': name, 'verdict': 'WAIT',
                              'close': 0, 'chg': 0, 'trend': '下降',
                              'reasons': [], 'hist': {}, 'rev_signal': '',
                              'eps_signal': '', 'score': 0, 'pos52': 0})

    # 分析 ETF
    etf_results = {}
    for sid, name in ETF_LIST.items():
        try:
            etf_results[sid] = analyze(sid, name, is_etf=True)
        except:
            pass

    def etf_buy_signal(r, sent) -> tuple[str, list]:
        """ETF 加碼買入判斷，回傳（建議, 原因清單）"""
        reasons = []
        score   = 0

        # 1. 52週低點附近
        if r['pos52'] < 30:
            score += 2; reasons.append(f"52週低點區（位置{r['pos52']:.0f}%，歷史便宜價）")
        elif r['pos52'] < 45:
            score += 1; reasons.append(f"52週中低位（位置{r['pos52']:.0f}%）")

        # 2. 均線轉多
        if r.get('golden'):
            score += 2; reasons.append("均線黃金交叉（趨勢轉多）")
        elif r['trend'] == '上升':
            score += 1; reasons.append("均線上升趨勢")

        # 3. 法人買超
        inst_net = sent.get('institutional', {}).get('total_net', 0)
        if inst_net > 0:
            score += 1; reasons.append(f"法人買超 {inst_net:,} 張")

        # 4. 跌破MA60後站回來
        if r['close'] > r['ma60'] and r['close'] < r['ma60'] * 1.03:
            score += 1; reasons.append("剛站回MA60（逢低反彈）")

        if score >= 3:
            return '🟢 建議加碼', reasons
        elif score >= 2:
            return '🔵 可以考慮加碼', reasons
        else:
            return '⚪ 正常定期定額即可', reasons

    lines = []
    lines.append(f"{icon} **台股{title}報告** {today}")
    lines.append("━" * 28)

    # ── 最重要：今天能不能進場 ──────────────────
    lines.append("")
    if buy_list:
        next_day = next_trading_day()
        action_word = "今天開盤可以考慮進場" if mode == 'open' else f"{next_day} 開盤可以考慮進場"
        lines.append(f"🟢 **{action_word}**")
        for r in buy_list:
            h5  = r['hist'].get(5, {})
            h10 = r['hist'].get(10, {})
            wr5  = h5.get('win_rate', '?')
            avg5 = h5.get('avg_return', '?')
            # 進場建議價
            entry = round(r['close'] * 1.005, 1)
            stop  = round(r['close'] * 0.92, 1)
            next_day = next_trading_day()
            tip = f"{next_day} 開盤站穩再進，不要追高" if mode == 'close' else "今天開盤確認方向再進"
            # 情緒分析
            try:
                df_p = get_price_cached(r['sid'], '2025-01-01')
                sent = full_sentiment(r['sid'], df_p)
                sent_icon = '🟢' if sent['verdict']=='多方有利' else '🔴' if sent['verdict']=='空方警示' else '⚪'
                sent_str  = f"\n│ 法人/量能：{sent_icon}{sent['verdict']}（{', '.join(sent['signals'][:1] + sent['warnings'][:1])}）"
            except:
                sent_str = ''
            lines.append(
                f"┌ **{r['name']} {r['sid']}**  現價 {r['close']}（{r['chg']:+.1f}%）\n"
                f"│ 進場參考：{entry} 以下  停損：{stop}（-8%）\n"
                f"│ 歷史勝率：買進後5天 {wr5}%，平均報酬 {avg5}%\n"
                f"│ 技術原因：{'、'.join(r['reasons'])}"
                f"{sent_str}\n"
                f"└ ⚠️ {tip}"
            )
    else:
        lines.append("⚪ **今天沒有明確進場訊號，空手等待**")

    if watch_list:
        lines.append("")
        lines.append("🔵 **快要到了，盯著這幾支**")
        for r in watch_list:
            missing = []
            if r['trend'] != '上升':
                missing.append("等均線轉多")
            else:
                missing.append("等強陽線確認")
            lines.append(f"  • **{r['name']}（{r['sid']}）** {r['close']}（{r['chg']:+.1f}%）— {missing[0]}")

    # ── 持倉狀況 ──────────────────────────────
    lines.append("")
    lines.append("📦 **ETF 持倉 & 加碼建議**")
    HOLDINGS = {
        '0050':   {'name': '元大台灣50',    'cost': 70.58},
        '00662':  {'name': '富邦NASDAQ',    'cost': 102.35},
        '009816': {'name': '凱基台灣TOP50', 'cost': 11.31},
    }
    for sid, info in HOLDINGS.items():
        r = etf_results.get(sid)
        if not r:
            continue
        cost  = info['cost']
        pnl   = (r['close'] / cost - 1) * 100
        stop  = round(cost * 0.85, 2)
        trend_icon = '▲' if r['trend'] == '上升' else '▼'
        action = '⚠️ 接近停損' if pnl < -12 else ''

        # ETF 情緒分析
        try:
            df_p = get_price_cached(sid, '2025-01-01')
            sent = full_sentiment(sid, df_p)
        except:
            sent = {}

        buy_tip, buy_reasons = etf_buy_signal(r, sent)

        lines.append(
            f"\n  **{info['name']}（{sid}）**\n"
            f"  現價 {r['close']}  成本 {cost}  損益 {pnl:+.1f}%  趨勢{trend_icon}  停損 {stop}  {action}\n"
            f"  加碼建議：{buy_tip}\n"
            f"  {'原因：' + '、'.join(buy_reasons) if buy_reasons else '無明顯加碼訊號，維持定期定額'}"
        )

    # ── 等待清單（簡短）──────────────────────
    if wait_list:
        lines.append("")
        wait_names = "、".join([f"{r['name']}" for r in wait_list])
        lines.append(f"⏳ **繼續等待**：{wait_names}")

    lines.append("")
    lines.append(f"_資料：{today}收盤　訊號依據：均線+K線+月營收+EPS_")
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['open', 'close'], default='close')
    args = parser.parse_args()

    print(f"執行 {args.mode} 報告...")
    report = build_report(args.mode)
    send(report)
    print("完成")
