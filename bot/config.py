import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SHOP_OWNER_ID = os.getenv("SHOP_OWNER_ID", "default_shop")
SHOP_NAME = os.getenv("SHOP_NAME", "My Kirana Store")
SHOP_GSTIN = os.getenv("SHOP_GSTIN", "")