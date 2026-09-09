"""Ловит всё, что не подошло другим роутерам — должен быть подключён последним."""

from aiogram import Router
from aiogram.types import Message

from ..locales import t
from ..user_state import get_lang

router = Router(name="fallback")


@router.message()
async def on_unexpected(message: Message) -> None:
    lang = get_lang(message.from_user.id)
    await message.answer(t(lang, "unexpected_message"))
