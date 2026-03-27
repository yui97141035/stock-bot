import requests
TOKEN = "MTQ3MTMyMTkzMDE5NTAxMzcyNQ.GvAqzi.lk-2eexi6oo2LG1826JCsolzJLErCmTcDeBruY"
CHANNEL = "1471384671651758125"
headers = {"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json"}
r = requests.post(f"https://discord.com/api/v10/channels/{CHANNEL}/messages",
                  json={"content": "🔔 台股監控系統連線測試 - 連線成功！"},
                  headers=headers)
print(r.status_code, r.json())
