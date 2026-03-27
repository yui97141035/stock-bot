"""
notify/discord_bot.py
Discord 推播通知
用法: python notify/discord_bot.py
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv('configs/accounts.env')

DISCORD_BOT_TOKEN  = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_CHANNEL_ID = os.getenv('DISCORD_CHANNEL_ID')


def send_message(message: str, channel_id: str = None):
    """推播訊息到 Discord 頻道"""
    cid = channel_id or DISCORD_CHANNEL_ID
    if not cid or not DISCORD_BOT_TOKEN:
        print(f'[Discord] 未設定 Token/Channel，訊息: {message}')
        return

    url = f'https://discord.com/api/v10/channels/{cid}/messages'
    headers = {
        'Authorization': f'Bot {DISCORD_BOT_TOKEN}',
        'Content-Type': 'application/json'
    }
    resp = requests.post(url, json={'content': message}, headers=headers)
    if resp.status_code == 200:
        print(f'[Discord] 已發送: {message}')
    else:
        print(f'[Discord] 發送失敗 {resp.status_code}: {resp.text}')


def notify_signal(account: str, action: str, stock_id: str, price: float):
    """交易訊號通知"""
    emoji = '🟢' if action == '買入' else '🔴'
    msg = f'{emoji} **{account}** {action} `{stock_id}` @ **{price:.2f}**'
    send_message(msg)


def notify_filled(account: str, action: str, stock_id: str, qty: int, price: float):
    """成交通知"""
    emoji = '✅'
    msg = f'{emoji} **{account}** 成交 {action} `{stock_id}` x{qty} @ **{price:.2f}**'
    send_message(msg)


if __name__ == '__main__':
    # 測試（需先填 accounts.env）
    send_message('🚀 台股監控系統啟動')
