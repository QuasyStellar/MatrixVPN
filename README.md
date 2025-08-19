# MatrixVPN Telegram Bot

This project implements a Telegram bot for managing VPN access, allowing users to request, renew, and manage their VPN configurations. The bot supports various VPN protocols and integrates with external shell scripts for server-side operations.

## Features

*   **User Onboarding**: Guided process for new users to request VPN access.
*   **VPN Configuration Management**: Users can receive configuration files for different VPN protocols (OpenVPN, WireGuard, AmneziaWG).
*   **Admin Tools**: Administrators can approve/deny access requests, renew user subscriptions, delete users, and send broadcast messages.
*   **Scheduled Tasks**: Automated tasks for sending payment reminders, checking expired accounts, and daily database backups.
*   **Information Menus**: Users can access information about VPN protocols and connection variants.

## Project Structure

The project has been refactored into a modular structure for better maintainability and separation of concerns:

```
MatrixVPN/
├── config/             # Application settings and static messages
│   ├── settings.py     # Loads environment variables and app settings
│   └── messages.py     # Stores all user-facing messages and texts
├── core/               # Core application components
│   ├── bot.py          # Initializes the Telegram Bot and Dispatcher
│   └── database.py     # Handles database connection and schema setup
├── modules/            # Feature-specific modules
│   ├── admin/          # Admin-related handlers and business logic
│   │   ├── handlers.py
│   │   └── services.py
│   ├── common/         # General-purpose handlers (main menu, settings, info)
│   │   ├── handlers.py
│   │   └── services.py
│   ├── user_onboarding/# Handlers and logic for user registration and instructions
│   │   ├── handlers.py
│   │   └── services.py
│   └── vpn_management/ # Handlers and logic for VPN config delivery and protocol menus
│       ├── handlers.py
│       └── services.py
├── services/           # Reusable utility functions and external integrations
│   ├── db_operations.py# Database interaction functions
│   ├── forms.py        # FSM States definitions
│   ├── messages_manage.py# Functions for sending and managing Telegram messages
│   └── scheduler.py    # APScheduler setup and scheduled tasks
├── assets/             # Static assets (images, GIFs)
├── venv/               # Python virtual environment
├── .git/               # Git repository data
├── .env                # Environment variables (created by setup.sh)
├── main.py             # Main application entry point
├── requirements.txt    # Python dependencies
└── setup.sh            # Script for initial project setup and systemd service configuration
```

## Setup and Installation

Follow these steps to set up and run the bot:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/QuasyStellar/MatrixVPN.git
    cd MatrixVPN
    ```

2.  **Run the setup script:**
    The `setup.sh` script will guide you through configuring environment variables, setting up a Python virtual environment, installing dependencies, and creating a systemd service.

    ```bash
    chmod +x setup.sh
    ./setup.sh
    ```
    *   **Important**: The `setup.sh` script will prompt you for several absolute paths for shell scripts (`delete-client.sh`, `add-client.sh`) and a VPN configuration directory. Ensure these scripts exist and are executable on your system, and the paths are correct. The bot relies on these external scripts for VPN server interactions.

3.  **Verify `.env` file:**
    After running `setup.sh`, a `.env` file will be created in the project root with your configurations. You can edit it manually if needed.

4.  **Start the bot (if not started by setup.sh):**
    The `setup.sh` script attempts to start the bot as a systemd service. If it fails or you need to restart it manually:
    ```bash
    sudo systemctl start matrixvpn
    ```

## Usage

*   **Bot Commands**: Interact with the bot via Telegram. The primary command is `/start`.
*   **Admin Commands**: If your Telegram User ID is configured as `ADMIN_ID` in `.env`, you can use admin commands like `/admin`.

## Logging

Bot logs are managed by `systemd` and can be viewed using `journalctl`:

```bash
sudo journalctl -u matrixvpn -f
```
