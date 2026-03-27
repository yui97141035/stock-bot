import requests, os, sys
sys.path.insert(0, r'C:\Users\yushin_57\projects\stock-bot')
from dotenv import load_dotenv
load_dotenv(r'C:\Users\yushin_57\projects\stock-bot\configs\accounts.env')
TOKEN   = os.getenv('DISCORD_BOT_TOKEN')
CHANNEL = '1471384671651758125'
r = requests.post(
    f'https://discord.com/api/v10/channels/{CHANNEL}/messages',
    json={'content': 'Token 已更新，推播正常！'},
    headers={'Authorization': f'Bot {TOKEN}', 'Content-Type': 'application/json'}
)
print(r.status_code, 'OK' if r.status_code == 200 else r.text)
