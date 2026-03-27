import sys, traceback
sys.path.insert(0, r'C:\Users\yushin_57\projects\stock-bot')
from data.cache import update_price

try:
    df = update_price('2330')
    print(f'OK: {len(df)} 筆')
except Exception as e:
    traceback.print_exc()
