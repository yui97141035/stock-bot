import time, subprocess
t = time.time()
subprocess.run(['python', 'notify/daily_report.py', '--mode', 'close'],
               cwd=r'C:\Users\yushin_57\projects\stock-bot')
print(f'\n耗時: {time.time()-t:.1f} 秒')
