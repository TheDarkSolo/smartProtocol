"""Конфигурация Telegram-бота Smart Protocol.

Бот — вторичный канал (см. .claude/agents/tg-bot-dev.md): точка входа для
пользователей из чатов и возврат брошенных дел. Вся тяжёлая логика — на
бэкенде, бот обращается к нему по HTTP, а не дублирует её.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SPBOT_", env_file=_ENV_FILE)

    bot_token: str = ""
    api_base_url: str = "http://localhost:8000"


settings = Settings()
