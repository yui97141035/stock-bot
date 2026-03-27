# -*- coding: utf-8 -*-
"""
data/backup.py
每日資料更新 + Git 備份
"""
import sys, os, subprocess
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from data.cache import update_all
import pandas as pd

REPO = r'C:\Users\yushin_57\projects\stock-bot'


def git_push():
    today = pd.Timestamp.today().strftime('%Y-%m-%d')
    cmds = [
        ['git', 'add', 'cache/'],
        ['git', 'commit', '-m', f'data: 更新 {today}'],
        ['git', 'push'],
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        if r.returncode != 0:
            # commit 沒有新內容時不算錯誤
            if 'nothing to commit' in r.stdout + r.stderr:
                print(f'  [{" ".join(cmd[1:])}] 無新資料，略過')
            else:
                print(f'  [{" ".join(cmd[1:])}] 失敗: {r.stderr.strip()}')
        else:
            print(f'  [{" ".join(cmd[1:])}] OK')


if __name__ == '__main__':
    print(f'=== 每日備份 {pd.Timestamp.today().strftime("%Y-%m-%d %H:%M")} ===')
    print('1. 更新快取...')
    update_all()
    print('\n2. Git 備份...')
    git_push()
    print('\n完成')
