"""Конфигурация Smart Protocol.

МРП и цены вынесены сюда намеренно: МРП пересматривается ежегодно, и его
значение не должно быть константой в коде. Значение обязано иметь дату
вступления в силу и подтверждаться первоисточником.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Абсолютный путь: env_file=".env" резолвится от текущей директории процесса,
# которая не всегда backend/ (например, при запуске с --app-dir из корня
# репозитория) — из-за этого ключи из .env тихо не подхватывались.
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SP_", env_file=_ENV_FILE)

    app_name: str = "Smart Protocol"
    environment: str = "development"

    # CORS: адреса фронтенда
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Загрузка постановлений
    upload_dir: str = "storage/uploads"
    max_upload_bytes: int = 15 * 1024 * 1024
    allowed_mime: list[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/heic",
    ]

    # Цена документа, тенге
    document_price_kzt: int = 2990

    # ВНИМАНИЕ: значение требует подтверждения по первоисточнику на текущий год
    # и обновления вместе с датой вступления в силу.
    mrp_kzt: int = 3932
    mrp_effective_from: str = "2025-01-01"
    mrp_verified: bool = False

    # DeepSeek используется только для изложения фактов пользователя связным
    # текстом. Ссылки на нормы права модель не формирует — они подставляются
    # из knowledge/articles.yaml шаблоном. См. app/services/appeal_draft.py.
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"


settings = Settings()
