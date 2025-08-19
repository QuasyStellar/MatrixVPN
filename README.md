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

## Admin Commands

The following commands are available to the administrator:

*   **/admin**: Opens the admin panel with the following options:
    *   **Проверить запросы (Check Requests)**: View pending access requests.
    *   **Удалить пользователя (Delete User)**: Delete a user by their ID.
    *   **Рассылка сообщений (Broadcast Messages)**: Send a message to all users.
    *   **Получить список пользователей (Get Users List)**: Get a file with a list of all users.

*   **/renewall**: Renews the configuration for all active users. This command is useful when you need to apply changes to all users at once.

*   **/renew <user_id> +<days>**: Renews a specific user's subscription by adding days to their *current* access end date.
    *   `<user_id>`: The user's Telegram ID.
    *   `+<days>`: The number of days to add to the user's subscription. **The `+` sign is mandatory for adding days.** If the `+` sign is omitted, the access will be reset to `<days>` from the current date.
    *   **Example**: `/renew 123456789 +30` - Adds 30 days to the subscription for the user with ID `123456789`.

*   **/update <user_id> <days>**: Extends a user's subscription by a certain number of days from the current date. This command effectively *resets* the access duration to `<days>` from the current date.
    *   `<user_id>`: The user's Telegram ID.
    *   `<days>`: The total number of days the subscription will be valid from the current date.
    *   **Example**: `/update 123456789 30` - Sets the subscription for the user with ID `123456789` to expire in 30 days from today.

## Logging

Bot logs are managed by `systemd` and can be viewed using `journalctl`:

```bash
sudo journalctl -u matrixvpn -f
```
