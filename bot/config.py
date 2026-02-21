import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DB_PATH = os.getenv("DB_PATH", "shop.db")
PICKUP_EXPIRY_HOURS = int(os.getenv("PICKUP_EXPIRY_HOURS", "24"))
CRYPTO_WALLET_BTC = os.getenv("CRYPTO_WALLET_BTC", "")
CRYPTO_WALLET_ETH = os.getenv("CRYPTO_WALLET_ETH", "")
SHOP_NAME = os.getenv("SHOP_NAME", "Sørlandets Shop")
