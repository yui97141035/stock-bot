# 移機安裝說明

## 需求
- Python 3.10 以上
- Git

## 步驟

### 1. 複製專案
```bash
git clone <你的 repo URL> stock-bot
cd stock-bot
```
或直接把整個資料夾複製過去（含 cache/ 目錄）。

### 2. 安裝套件
```bash
pip install -r requirements.txt
```

### 3. 設定金鑰
```bash
copy configs\accounts.env.example configs\accounts.env
```
編輯 `configs/accounts.env`，填入：
- `DISCORD_BOT_TOKEN` — Discord Bot Token
- `DISCORD_CHANNEL_ID` — 1471384671651758125
- `FINMIND_TOKEN` — （可選，免費版不需要）
- Fugle API 金鑰（API 審核通過後）

### 4. 更新快取資料
```bash
python data/cache.py
```
第一次會從 2020 年開始下載，約需 2-3 分鐘。

### 5. 測試 Discord 推播
```bash
python notify/price_alert.py
```

### 6. 啟動回測介面
```bash
streamlit run backtest/app.py
```
開啟瀏覽器 http://localhost:8501

### 7. 設定每日排程
在新電腦重新設定 OpenClaw 排程（或用 Windows 工作排程器）：

| 時間 | 指令 |
|------|------|
| 週一～五 08:30 | `python notify/daily_report.py --mode open` |
| 週一～五 13:40 | `python notify/daily_report.py --mode close` |
| 週一～五 14:00 | `python data/cache.py` |
| 週一～五 16:30 | `python notify/price_alert.py` |
| 每週五 17:00   | `python notify/stock_monitor.py` |

## 目錄結構
```
stock-bot/
├── cache/          ← 歷史資料（每日自動累加）
├── configs/        ← 金鑰設定（不要上傳到 Git）
├── data/           ← 資料抓取與快取
├── strategies/     ← 交易策略
├── backtest/       ← 回測引擎與介面
├── notify/         ← Discord 推播
├── trade/          ← 下單模組（API 審核後啟用）
└── requirements.txt
```
