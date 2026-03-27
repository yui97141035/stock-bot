"""
trade/client.py
多帳號下單管理（Fugle Trade API）
API 審核通過後，填入 configs/accounts.env 即可啟用
"""
import os
from dotenv import load_dotenv

load_dotenv('configs/accounts.env')

# ── 審核通過後取消註解並 pip install fugle-trade ──
# from fugle_trade.sdk import SDK
# from fugle_trade.order import MarketOrder

class AccountManager:
    def __init__(self, name: str, config_key_prefix: str):
        self.name = name
        self.api_key      = os.getenv(f'{config_key_prefix}_API_KEY')
        self.api_secret   = os.getenv(f'{config_key_prefix}_API_SECRET')
        self.cert_path    = os.getenv(f'{config_key_prefix}_CERT_PATH')
        self.cert_password= os.getenv(f'{config_key_prefix}_CERT_PASSWORD')
        self._sdk = None

    def connect(self):
        """API 審核通過後啟用"""
        raise NotImplementedError("API 尚未審核通過，請先取消 client.py 內的註解")
        # self._sdk = SDK(...)
        # self._sdk.login()

    def buy(self, stock_id: str, quantity: int, price: float = None):
        """market order（price=None）或 limit order"""
        print(f'[{self.name}] 買入 {stock_id} x{quantity} @ {"市價" if not price else price}')
        # 實際下單：self._sdk.order(...)

    def sell(self, stock_id: str, quantity: int, price: float = None):
        print(f'[{self.name}] 賣出 {stock_id} x{quantity} @ {"市價" if not price else price}')

    def get_positions(self):
        print(f'[{self.name}] 查詢持倉（API 啟用後生效）')
        return []


# 兩個帳號
my_account       = AccountManager('自己', 'MY')
daughter_account = AccountManager('女兒', 'DAUGHTER')


if __name__ == '__main__':
    my_account.buy('2330', 1, 950.0)
    daughter_account.buy('0050', 1, 185.0)
