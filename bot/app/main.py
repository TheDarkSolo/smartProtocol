"""Точка входа Telegram-бота Smart Protocol.

Поллинг — только для разработки. На проде (см. .claude/agents/tg-bot-dev.md)
нужны вебхуки и общее хранилище состояния (Redis) вместо словаря в памяти.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .config import settings
from .handlers import fallback, start, upload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smart_protocol_bot")


async def main() -> None:
    if not settings.bot_token:
        raise SystemExit(
            "SPBOT_BOT_TOKEN не задан. Получите токен у @BotFather и запишите "
            "его в bot/.env (SPBOT_BOT_TOKEN=...)."
        )

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher()

    # Порядок важен: fallback должен быть подключён последним, иначе он
    # перехватит сообщения, предназначенные другим роутерам.
    dispatcher.include_router(start.router)
    dispatcher.include_router(upload.router)
    dispatcher.include_router(fallback.router)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Smart Protocol bot: старт (polling, API=%s)", settings.api_base_url)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
