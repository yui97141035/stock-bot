import sys, time
sys.path.insert(0, r'C:\Users\yushin_57\projects\stock-bot')
from data.cache import update_revenue, update_eps

STOCKS = ['1519','2330','2382','3017','3131','3231','3324','8064']
for sid in STOCKS:
    print(f'{sid} 月營收...', end=' ', flush=True)
    df = update_revenue(sid)
    print(f'{len(df)} 筆', end='  ')
    print(f'EPS...', end=' ', flush=True)
    df2 = update_eps(sid)
    print(f'{len(df2)} 筆')
    time.sleep(0.5)
print('完成')
