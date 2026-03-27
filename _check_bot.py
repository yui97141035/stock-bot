import requests
TOKEN = "MTQ3MTMyMTkzMDE5NTAxMzcyNQ.GvAqzi.lk-2eexi6oo2LG1826JCsolzJLErCmTcDeBruY"
headers = {"Authorization": f"Bot {TOKEN}"}

# Bot 資訊
r = requests.get("https://discord.com/api/v10/users/@me", headers=headers)
print("Bot 資訊:", r.status_code, r.json())

# 嘗試抓伺服器頻道列表
guild_id = "1471384670754046181"
r2 = requests.get(f"https://discord.com/api/v10/guilds/{guild_id}/channels", headers=headers)
print("\n頻道列表:", r2.status_code)
if r2.status_code == 200:
    for ch in r2.json():
        print(f"  {ch['id']} #{ch['name']} (type={ch['type']})")
else:
    print(r2.json())
