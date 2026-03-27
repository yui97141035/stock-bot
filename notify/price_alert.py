# -*- coding: utf-8 -*-
"""
notify/price_alert.py
價格警報監控 - 每天收盤後執行一次
用法: python notify/price_alert.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import requests
from dotenv import load_dotenv
from data.cache import get_price_cached
import pandas as pd

load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'configs', 'accounts.env'))

BOT_TOKEN  = os.getenv('DISCORD_BOT_TOKEN')
CHANNEL_ID = '1471384671651758125'   # 一般頻道

# ── 監控清單 ─────────────────────────────────────────────
# 格式：股票代號, 名稱, 帳戶, 持股數, 成本, 停損, 停利
WATCHLIST = [
    # 陳姵語帳戶
    {'id': '0050',   'name': '元大台灣50',    'account': '陳姵語',
     'shares': 146,  'cost': 70.58, 'stop_loss': 59.99, 'take_profit': 81.17},
    {'id': '00662',  'name': '富邦NASDAQ',    'account': '陳姵語',
     'shares': 29,   'cost': 102.35,'stop_loss': 87.00, 'take_profit': 117.70},
    {'id': '009816', 'name': '凱基台灣TOP50', 'account': '陳姵語',
     'shares': 2182, 'cost': 11.31, 'stop_loss': 9.61,  'take_profit': 13.01},
    # 盧譽心帳戶（女兒）
    {'id': '009816', 'name': '凱基台灣TOP50', 'account': '盧譽心',
     'shares': 274,  'cost': 10.87, 'stop_loss': 9.24,  'take_profit': 12.50},
]


def send_discord(message: str):
    if not BOT_TOKEN:
        print(f"[未設定 Token] {message}")
        return
    url = f'https://discord.com/api/v10/channels/{CHANNEL_ID}/messages'
    resp = requests.post(
        url,
        json={'content': message},
        headers={'Authorization': f'Bot {BOT_TOKEN}', 'Content-Type': 'application/json'}
    )
    if resp.status_code == 200:
        print(f"[已推播] {message[:50]}...")
    else:
        print(f"[推播失敗 {resp.status_code}] {resp.text}")


def check_alerts():
    print("=== 股票警報檢查 ===")
    alerts = []
    summary_lines = []

    checked = set()
    for item in WATCHLIST:
        sid = item['id']
        if sid in checked:
            continue
        checked.add(sid)

        try:
            df = get_price_cached(sid, '2025-01-01')
            if df.empty:
                continue
            df = df.sort_values('date')
            price = df['close'].iloc[-1]
            date  = df['date'].iloc[-1]
            chg   = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2] * 100

            # 均線
            ma5  = df['close'].tail(5).mean()
            ma20 = df['close'].tail(20).mean()
            trend = '上升' if ma5 > ma20 else '下降'

            print(f"  {item['name']}({sid}): {price:.2f}  {chg:+.2f}%  趨勢:{trend}")
        except Exception as e:
            print(f"  {sid} 取價失敗: {e}")
            continue

        # 對每個持倉檢查警報
        for item in [x for x in WATCHLIST if x['id'] == sid]:
            acct = item['account']
            cost = item['cost']
            sl   = item['stop_loss']
            tp   = item['take_profit']
            sh   = item['shares']

            if cost:
                pnl_pct = (price / cost - 1) * 100
                pnl_amt = (price - cost) * sh

            lines = []
            if sl and price <= sl:
                msg = (f"🚨 **停損警報** [{acct}]\n"
                       f"`{item['name']}({sid})`\n"
                       f"當前價格 **{price:.2f}** 跌破停損線 **{sl:.2f}**\n"
                       f"損益：{pnl_pct:+.1f}%（{pnl_amt:+.0f}元）\n"
                       f"**建議：考慮出場，保留資金等待重新佈局**")
                alerts.append(msg)

            elif tp and price >= tp:
                msg = (f"✅ **停利提醒** [{acct}]\n"
                       f"`{item['name']}({sid})`\n"
                       f"當前價格 **{price:.2f}** 達到停利線 **{tp:.2f}**\n"
                       f"損益：{pnl_pct:+.1f}%（{pnl_amt:+.0f}元）\n"
                       f"**建議：可考慮停利，或上移停損線至成本保護獲利**")
                alerts.append(msg)

            elif sl and price <= sl * 1.05:
                msg = (f"⚠️ **接近停損** [{acct}]\n"
                       f"`{item['name']}({sid})` 現價 {price:.2f}，"
                       f"停損線 {sl:.2f}（距離 {(price/sl-1)*100:.1f}%）")
                alerts.append(msg)

            if cost:
                summary_lines.append(
                    f"  {acct} {item['name']}({sid}): "
                    f"{price:.2f}  {pnl_pct:+.1f}%（{pnl_amt:+.0f}元）"
                )

    # 發送警報
    if alerts:
        for alert in alerts:
            send_discord(alert)
    else:
        # 無警報時發送每日摘要
        today = pd.Timestamp.today().strftime('%Y-%m-%d')
        summary = f"📊 **每日持倉摘要** {today}\n" + "\n".join(summary_lines) + "\n✅ 目前無警報觸發"
        send_discord(summary)

    print(f"\n共發送 {len(alerts)} 個警報")


if __name__ == '__main__':
    check_alerts()
