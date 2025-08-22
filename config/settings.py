import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")  # Read as string first
DATABASE_PATH = os.getenv("DATABASE_PATH", "users.db")

if not TOKEN:
    raise ValueError("TOKEN environment variable is not set or is empty.")

if not ADMIN_ID:
    raise ValueError("ADMIN_ID environment variable is not set or is empty.")

try:
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    raise ValueError("ADMIN_ID environment variable must be an integer.")

CLIENT_SCRIPT_PATH = os.getenv("CLIENT_SCRIPT_PATH", "/root/antizapret/client.sh")
VPN_CONFIG_PATH = os.getenv("VPN_CONFIG_PATH", "/root/vpn")
