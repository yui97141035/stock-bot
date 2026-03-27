import sys
sys.path.insert(0, r'C:\Users\yushin_57\projects\stock-bot')
# 只檢查語法，不執行 streamlit
import ast
with open(r'C:\Users\yushin_57\projects\stock-bot\backtest\app.py', encoding='utf-8') as f:
    src = f.read()
try:
    ast.parse(src)
    print("語法正確")
except SyntaxError as e:
    print(f"語法錯誤：{e}")
