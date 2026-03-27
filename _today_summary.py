import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\yushin_57\projects\stock-bot')
from data.cache import get_price_cached
import pandas as pd

HOLDINGS = [
    {'sid': '0050',   'name': '元大台灣50',    'shares': 146,  'cost': 70.58,  'account': '陳姵語'},
    {'sid': '00662',  'name': '富邦NASDAQ',    'shares': 29,   'cost': 102.35, 'account': '陳姵語'},
    {'sid': '009816', 'name': '凱基台灣TOP50', 'shares': 2182, 'cost': 11.31,  'account': '陳姵語'},
    {'sid': '009816', 'name': '凱基台灣TOP50', 'shares': 274,  'cost': 10.87,  'account': '盧譽心'},
]

print("=" * 60)
print("持倉停損 & 交易量報告")
print("=" * 60)

seen = {}
for h in HOLDINGS:
    sid = h['sid']
    if sid not in seen:
        df = get_price_cached(sid, '2025-01-01')
        df = df.sort_values('date').reset_index(drop=True)
        seen[sid] = df

total_value = 0
total_cost  = 0

for h in HOLDINGS:
    sid    = h['sid']
    name   = h['name']
    shares = h['shares']
    cost   = h['cost']
    acct   = h['account']
    df     = seen[sid]

    last   = df.iloc[-1]
    prev   = df.iloc[-2]
    price  = last['close']
    vol    = int(last['Trading_Volume'])
    date   = last['date']

    # 近5日均量
    avg_vol5 = int(df['Trading_Volume'].tail(5).mean())

    pnl_pct = (price / cost - 1) * 100
    pnl_amt = (price - cost) * shares
    mkt_val = price * shares

    # 停損線（-15%）
    stop    = round(cost * 0.85, 2)
    stop_gap = (price / stop - 1) * 100

    # 停利線（+15%）
    profit  = round(cost * 1.15, 2)

    total_value += mkt_val
    total_cost  += cost * shares

    print(f"\n【{acct}】{name}（{sid}）")
    print(f"  今日收盤  : {price:.2f}   漲跌: {(price-prev['close'])/prev['close']*100:+.2f}%")
    print(f"  持有成本  : {cost:.2f}   損益: {pnl_pct:+.1f}%（{pnl_amt:+.0f}元）")
    print(f"  市值      : {mkt_val:,.0f} 元（{shares} 股）")
    print(f"  停損線    : {stop:.2f}（-15%）  距離停損: {stop_gap:+.1f}%  {'⚠️ 接近！' if stop_gap < 5 else '安全'}")
    print(f"  停利線    : {profit:.2f}（+15%）  {'✅ 已到達！' if price >= profit else f'差 {(profit/price-1)*100:.1f}%'}")
    print(f"  今日成交量: {vol:,} 股  近5日均量: {avg_vol5:,} 股  {'量縮' if vol < avg_vol5*0.7 else '量增' if vol > avg_vol5*1.3 else '正常'}")

print("\n" + "=" * 60)
print(f"總市值  : {total_value:,.0f} 元")
print(f"總成本  : {total_cost:,.0f} 元")
print(f"總損益  : {total_value - total_cost:+,.0f} 元（{(total_value/total_cost-1)*100:+.1f}%）")
