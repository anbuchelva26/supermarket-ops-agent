"""
Entrypoint. Starts the Telegram bot in polling mode and wires each incoming message to
a Claude Agent SDK session (see agent.py).

Run: python -m bot.main
"""

from db.connection import init_db
from bot.telegram_handler import run_bot


def main() -> None:
    init_db()
    run_bot()


if __name__ == "__main__":
    main()
