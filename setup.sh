#!/bin/bash

# --- Configuration Variables ---
PROJECT_ROOT="/root/bot"
SERVICE_NAME="bot"
PYTHON_EXEC="python3"
VENV_DIR="venv"
REQUIREMENTS_FILE="requirements.txt"
MAIN_APP_FILE="main.py"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
ENV_FILE="${PROJECT_ROOT}/.env"

echo "--------------------------------------------------"
echo "MatrixVPN Setup Script"
echo "This script will guide you through setting up your MatrixVPN bot."
echo "It will configure environment variables, set up a Python virtual"
echo "environment, install dependencies, and create a systemd service."
echo "--------------------------------------------------"
echo ""

# --- Prompt for Environment Variables ---

echo "Please provide the following information:"

# TOKEN
read -p "Enter your Telegram Bot Token (from BotFather): " TOKEN_INPUT
echo "TOKEN=\"${TOKEN_INPUT}\"" > "${ENV_FILE}"

# ADMIN_ID
read -p "Enter your Telegram Admin User ID (numeric): " ADMIN_ID_INPUT
echo "ADMIN_ID=\"${ADMIN_ID_INPUT}\"" >> "${ENV_FILE}"

# SUPPORT_ID
read -p "Enter the Telegram User ID for support (numeric) [default: 6522480240]: " SUPPORT_ID_INPUT
SUPPORT_ID_INPUT=${SUPPORT_ID_INPUT:-6522480240}
echo "SUPPORT_ID=\"${SUPPORT_ID_INPUT}\"" >> "${ENV_FILE}"

# DATABASE_PATH
read -p "Enter the path for the SQLite database (default: users.db): " DATABASE_PATH_INPUT
DATABASE_PATH_INPUT=${DATABASE_PATH_INPUT:-"users.db"}
echo "DATABASE_PATH=\"${DATABASE_PATH_INPUT}\"" >> "${ENV_FILE}"

# CLIENT_SCRIPT_PATH
read -p "Enter the absolute path to the client management script (e.g., /root/antizapret/client.sh): " CLIENT_SCRIPT_PATH_INPUT
CLIENT_SCRIPT_PATH_INPUT=${CLIENT_SCRIPT_PATH_INPUT:-"/root/antizapret/client.sh"}
echo "CLIENT_SCRIPT_PATH=\"${CLIENT_SCRIPT_PATH_INPUT}\"" >> "${ENV_FILE}"

# VPN_CONFIG_PATH
read -p "Enter the absolute path to the VPN configuration directory (default: /root/antizapret/client): " VPN_CONFIG_PATH_INPUT
VPN_CONFIG_PATH_INPUT=${VPN_CONFIG_PATH_INPUT:-"/root/antizapret/client"}
echo "VPN_CONFIG_PATH=\"${VPN_CONFIG_PATH_INPUT}\"" >> "${ENV_FILE}"

# OPENVPN_INSTRUCTION_URL
read -p "Enter the URL for OpenVPN instructions [default: https://teletype.in/@esc_matrix/Matrix_VPN_OVPN_Instruction]: " OPENVPN_INSTRUCTION_URL_INPUT
OPENVPN_INSTRUCTION_URL_INPUT=${OPENVPN_INSTRUCTION_URL_INPUT:-https://teletype.in/@esc_matrix/Matrix_VPN_OVPN_Instruction}
echo "OPENVPN_INSTRUCTION_URL=\"${OPENVPN_INSTRUCTION_URL_INPUT}\"" >> "${ENV_FILE}"

# WIREGUARD_INSTRUCTION_URL
read -p "Enter the URL for WireGuard/AmneziaWG instructions [default: https://teletype.in/@esc_matrix/Matrix_VPN_AMWG_Instruction]: " WIREGUARD_INSTRUCTION_URL_INPUT
WIREGUARD_INSTRUCTION_URL_INPUT=${WIREGUARD_INSTRUCTION_URL_INPUT:-https://teletype.in/@esc_matrix/Matrix_VPN_AMWG_Instruction}
echo "WIREGUARD_INSTRUCTION_URL=\"${WIREGUARD_INSTRUCTION_URL_INPUT}\"" >> "${ENV_FILE}"

# TIMEZONE
read -p "Enter the timezone for the bot [default: Europe/Moscow]: " TIMEZONE_INPUT
TIMEZONE_INPUT=${TIMEZONE_INPUT:-Europe/Moscow}
echo "TIMEZONE=\"${TIMEZONE_INPUT}\"" >> "${ENV_FILE}"

echo ""
echo "Environment variables saved to ${ENV_FILE}"
echo "--------------------------------------------------"
echo ""

# --- Virtual Environment Setup ---

# --- Locale Setup ---
echo "Setting up locale ru_RU.UTF-8..."
sudo apt-get update && sudo apt-get install -y locales || { echo "Error: Failed to install locales package."; exit 1; }
sudo locale-gen ru_RU.UTF-8 || { echo "Error: Failed to generate ru_RU.UTF8 locale."; exit 1; }
sudo update-locale LANG=ru_RU.UTF-8 || { echo "Error: Failed to set default locale."; exit 1; }
export LANG=ru_RU.UTF-8
export LC_ALL=ru_RU.UTF-8
echo "Locale setup complete."
echo "--------------------------------------------------"
echo ""

echo "Setting up Python virtual environment..."
cd "${PROJECT_ROOT}" || { echo "Error: Could not change to project directory."; exit 1; }

if ! command -v "${PYTHON_EXEC}" &> /dev/null; then
    echo "Error: ${PYTHON_EXEC} is not installed. Please install Python 3."
    exit 1
fi

# Ensure python3-venv is installed for creating virtual environments
sudo apt-get update && sudo apt-get install -y python3-venv || { echo "Error: Failed to install python3-venv. Please install it manually."; exit 1; }

"${PYTHON_EXEC}" -m venv "${VENV_DIR}" || { echo "Error: Failed to create virtual environment."; exit 1; }
echo "Virtual environment created at ${PROJECT_ROOT}/${VENV_DIR}"

source "${VENV_DIR}/bin/activate" || { echo "Error: Failed to activate virtual environment."; exit 1; }
echo "Virtual environment activated."

echo "Installing dependencies from ${REQUIREMENTS_FILE}..."
pip install -r "${REQUIREMENTS_FILE}" || { echo "Error: Failed to install dependencies."; exit 1; }
echo "Dependencies installed."

deactivate
echo "Virtual environment deactivated."
echo "--------------------------------------------------"
echo ""

# --- Systemd Service Creation ---

echo "Creating systemd service file: ${SERVICE_FILE}..."

cat <<EOF | sudo tee "${SERVICE_FILE}"
[Unit]
Description=${SERVICE_NAME} Telegram Bot
After=network.target

[Service]
User=root
WorkingDirectory=${PROJECT_ROOT}
ExecStart=${PROJECT_ROOT}/${VENV_DIR}/bin/${PYTHON_EXEC} ${PROJECT_ROOT}/${MAIN_APP_FILE}
Restart=always
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

if [ $? -ne 0 ]; then
    echo "Error: Failed to create systemd service file. Do you have sudo privileges?"
    exit 1
fi
echo "Systemd service file created."

echo "Reloading systemd daemon..."
sudo systemctl daemon-reload || { echo "Error: Failed to reload systemd daemon."; exit 1; }

echo "Enabling and starting ${SERVICE_NAME} service..."
sudo systemctl enable "${SERVICE_NAME}" || { echo "Error: Failed to enable service."; exit 1; }
sudo systemctl start "${SERVICE_NAME}" || { echo "Error: Failed to start service."; exit 1; }

echo "Checking service status..."
sudo systemctl status "${SERVICE_NAME}" --no-pager

echo "--------------------------------------------------"
echo "Setup complete!"
echo "The MatrixVPN bot should now be running as a systemd service."
echo "You can check its status with: sudo systemctl status ${SERVICE_NAME}"
echo "You can view logs with: journalctl -u ${SERVICE_NAME} -f"
echo "--------------------------------------------------"
