import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
SUPPORT_ID = os.getenv("SUPPORT_ID")
DATABASE_PATH = os.getenv("DATABASE_PATH", "users.db")

if not TOKEN:
    raise ValueError("TOKEN environment variable is not set or is empty.")
if not ADMIN_ID:
    raise ValueError("ADMIN_ID environment variable is not set or is empty.")
if not SUPPORT_ID:
    raise ValueError("ADMIN_ID environment variable is not set or is empty.")

try:
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    raise ValueError("ADMIN_ID environment variable must be an integer.")

try:
    SUPPORT_ID = int(SUPPORT_ID)
except ValueError:
    raise ValueError("SUPPORT_ID environment variable must be an integer.")

TRIAL_CHANNEL_ID = os.getenv("TRIAL_CHANNEL_ID")
if not TRIAL_CHANNEL_ID:
    raise ValueError("TRIAL_CHANNEL_ID environment variable is not set or is empty.")

try:
    TRIAL_CHANNEL_ID = int(TRIAL_CHANNEL_ID)
except ValueError:
    raise ValueError("TRIAL_CHANNEL_ID environment variable must be an integer.")

TELEGRAM_STARS_PAYMENT_TOKEN = os.getenv("TELEGRAM_STARS_PAYMENT_TOKEN")
if not TELEGRAM_STARS_PAYMENT_TOKEN:
    raise ValueError("TELEGRAM_STARS_PAYMENT_TOKEN environment variable is not set or is empty.")

VPN_CONFIG_PATH = os.getenv("VPN_CONFIG_PATH", "/root/vpn")

OPENVPN_INSTRUCTION_URL = os.getenv("OPENVPN_INSTRUCTION_URL", "")
WIREGUARD_INSTRUCTION_URL = os.getenv("WIREGUARD_INSTRUCTION_URL", "")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
