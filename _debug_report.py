import sys, traceback
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Users\yushin_57\projects\stock-bot')
from notify.daily_report import analyze, STOCK_LIST

for sid, name in list(STOCK_LIST.items())[:2]:
    try:
        r = analyze(sid, name, is_etf=False)
        print(f"{name}: verdict={r['verdict']} score={r['score']} reasons={r['reasons']}")
    except Exception as e:
        traceback.print_exc()
