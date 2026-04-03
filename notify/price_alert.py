# -*- coding: utf-8 -*-
"""
notify/price_alert.py
價格警報監控 - 每天收盤後執行一次
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from data.cache import get_price_cached
from notify.discord_bot import send_message, HOLDINGS


def check_alerts():
    print("=== 股票警報檢查 ===")
    alerts = []
    summary_lines = []
    checked = set()

    for item in HOLDINGS:
        sid = item['id']
        if sid not in checked:
            checked.add(sid)
            try:
                df = get_price_cached(sid, '2025-01-01')
                if df.empty:
                    continue
                df = df.sort_values('date')
                price = df['close'].iloc[-1]
                chg   = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2] * 100
                ma5   = df['close'].tail(5).mean()
                ma20  = df['close'].tail(20).mean()
                trend = '上升' if ma5 > ma20 else '下降'
                print(f"  {item['name']}({sid}): {price:.2f}  {chg:+.2f}%  趨勢:{trend}")
            except Exception as e:
                print(f"  {sid} 取價失敗: {e}")
                continue

        # 對每個帳戶的持倉檢查
        for pos in [x for x in HOLDINGS if x['id'] == sid]:
            acct = pos['account']
            cost = pos['cost']
            sl   = pos['stop_loss']
            tp   = pos['take_profit']
            sh   = pos['shares']

            try:
                df = get_price_cached(sid, '2025-01-01')
                price = df.sort_values('date')['close'].iloc[-1]
            except Exception:
                continue

            pnl_pct = (price / cost - 1) * 100
            pnl_amt = (price - cost) * sh

            if sl and price <= sl:
                alerts.append(
                    f"🚨 **停損警報** [{acct}]\n"
                    f"`{pos['name']}({sid})`\n"
                    f"當前價格 **{price:.2f}** 跌破停損線 **{sl:.2f}**\n"
                    f"損益：{pnl_pct:+.1f}%（{pnl_amt:+.0f}元）\n"
                    f"**建議：考慮出場，保留資金等待重新佈局**"
                )
            elif tp and price >= tp:
                alerts.append(
                    f"✅ **停利提醒** [{acct}]\n"
                    f"`{pos['name']}({sid})`\n"
                    f"當前價格 **{price:.2f}** 達到停利線 **{tp:.2f}**\n"
                    f"損益：{pnl_pct:+.1f}%（{pnl_amt:+.0f}元）\n"
                    f"**建議：可考慮停利，或上移停損線至成本保護獲利**"
                )
            elif sl and price <= sl * 1.05:
                alerts.append(
                    f"⚠️ **接近停損** [{acct}]\n"
                    f"`{pos['name']}({sid})` 現價 {price:.2f}，"
                    f"停損線 {sl:.2f}（距離 {(price / sl - 1) * 100:.1f}%）"
                )

            summary_lines.append(
                f"  {acct} {pos['name']}({sid}): "
                f"{price:.2f}  {pnl_pct:+.1f}%（{pnl_amt:+.0f}元）"
            )

    # 發送
    if alerts:
        for alert in alerts:
            send_message(alert)
    else:
        today = pd.Timestamp.today().strftime('%Y-%m-%d')
        summary = f"📊 **每日持倉摘要** {today}\n" + "\n".join(summary_lines) + "\n✅ 目前無警報觸發"
        send_message(summary)

    print(f"\n共發送 {len(alerts)} 個警報")


if __name__ == '__main__':
    check_alerts()
