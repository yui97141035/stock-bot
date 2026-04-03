# -*- coding: utf-8 -*-
"""
notify/discord_bot.py
Discord 推播通知（所有模組統一使用此檔案發送）
"""
import os, sys, time
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'configs', 'accounts.env'))

BOT_TOKEN  = os.getenv('DISCORD_BOT_TOKEN')
CHANNEL_ID = os.getenv('DISCORD_CHANNEL_ID', '1471384671651758125')

# ── 共用股票清單（單一來源） ────────────────────────────
STOCK_LIST = {
    '1519': '華城',   '2330': '台積電', '2382': '廣達',
    '3017': '奇鋐',   '3131': '弘塑',   '3231': '緯創',
    '3324': '雙鴻',   '8064': '東捷',
}
ETF_LIST = {
    '0050': '元大台灣50',  '00662': '富邦NASDAQ',
    '009816': '凱基台灣TOP50',
}
# 持倉資訊
HOLDINGS = [
    {'id': '0050',   'name': '元大台灣50',    'account': '陳姵語',
     'shares': 146,  'cost': 70.58,  'stop_loss': 59.99, 'take_profit': 81.17},
    {'id': '00662',  'name': '富邦NASDAQ',    'account': '陳姵語',
     'shares': 29,   'cost': 102.35, 'stop_loss': 87.00, 'take_profit': 117.70},
    {'id': '009816', 'name': '凱基台灣TOP50', 'account': '陳姵語',
     'shares': 2182, 'cost': 11.31,  'stop_loss': 9.61,  'take_profit': 13.01},
    {'id': '009816', 'name': '凱基台灣TOP50', 'account': '盧譽心',
     'shares': 274,  'cost': 10.87,  'stop_loss': 9.24,  'take_profit': 12.50},
]

# ── 發送函式 ────────────────────────────────────────────
def send_message(message: str, channel_id: str = None):
    """推播訊息到 Discord 頻道（自動切割 2000 字）"""
    cid = channel_id or CHANNEL_ID
    if not cid or not BOT_TOKEN:
        print(f'[Discord] 未設定 Token/Channel，訊息:\n{message}')
        return

    url = f'https://discord.com/api/v10/channels/{cid}/messages'
    headers = {
        'Authorization': f'Bot {BOT_TOKEN}',
        'Content-Type': 'application/json'
    }
    # 自動切割 2000 字限制
    chunks = [message[i:i+1990] for i in range(0, len(message), 1990)]
    for chunk in chunks:
        for attempt in range(3):
            resp = requests.post(url, json={'content': chunk}, headers=headers, timeout=10)
            if resp.status_code == 200:
                print(f'[Discord OK] {chunk[:60]}...')
                break
            elif resp.status_code == 429:
                wait = resp.json().get('retry_after', 2)
                print(f'[Discord 限速] 等待 {wait}s...')
                time.sleep(wait)
            else:
                print(f'[Discord {resp.status_code}] {resp.text[:100]}')
                break
        if len(chunks) > 1:
            time.sleep(0.5)


def notify_signal(account: str, action: str, stock_id: str, price: float):
    """交易訊號通知"""
    emoji = '🟢' if action == '買入' else '🔴'
    send_message(f'{emoji} **{account}** {action} `{stock_id}` @ **{price:.2f}**')


def notify_filled(account: str, action: str, stock_id: str, qty: int, price: float):
    """成交通知"""
    send_message(f'✅ **{account}** 成交 {action} `{stock_id}` x{qty} @ **{price:.2f}**')


if __name__ == '__main__':
    send_message('🚀 台股監控系統啟動')
