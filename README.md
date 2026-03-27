# 台股監控 + 回測系統

## 結構

```
stock-bot/
├── configs/
│   ├── accounts.env.example   # 金鑰範本（複製成 accounts.env 填入）
│   └── *.p12                  # 憑證檔案（API 審核後放這裡）
├── data/
│   └── fetch.py               # FinMind 抓歷史資料
├── strategies/
│   └── ma_cross.py            # 均線交叉策略（範例）
├── backtest/
│   └── run.py                 # 執行回測
├── trade/
│   └── client.py              # 多帳號下單（API 審核後啟用）
└── notify/
    └── discord_bot.py         # Discord 推播
```

## 快速開始

### 1. 設定金鑰
```
cp configs/accounts.env.example configs/accounts.env
# 填入 Discord Bot Token 和 Channel ID
```

### 2. 跑回測
```bash
python backtest/run.py 2330 2023-01-01
python backtest/run.py 0050 2022-01-01
```

### 3. 測試 Discord 推播
```bash
python notify/discord_bot.py
```

### 4. API 審核通過後
- 把 .p12 憑證放到 configs/
- 填入 accounts.env 的 API 金鑰
- 取消 trade/client.py 內的 fugle-trade 註解

## 待辦
- [ ] 玉山 API 審核通過
- [ ] 接入 fugle-trade SDK
- [ ] 加入更多策略（RSI、布林通道等）
- [ ] 盤中監控 + 自動下單
