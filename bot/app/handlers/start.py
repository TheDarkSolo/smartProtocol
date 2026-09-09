from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from ..keyboards import language_keyboard
from ..locales import Lang, t
from ..user_state import get_lang, set_lang

router = Router(name="start")


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    lang = get_lang(message.from_user.id)
    await message.answer(t(lang, "welcome"))


@router.message(Command("help"))
async def on_help(message: Message) -> None:
    lang = get_lang(message.from_user.id)
    await message.answer(t(lang, "help"))


@router.message(Command("language"))
async def on_language_command(message: Message) -> None:
    lang = get_lang(message.from_user.id)
    await message.answer(t(lang, "choose_language"), reply_markup=language_keyboard)


@router.callback_query(F.data.startswith("lang:"))
async def on_language_chosen(callback: CallbackQuery) -> None:
    lang: Lang = "kk" if callback.data == "lang:kk" else "ru"
    set_lang(callback.from_user.id, lang)
    await callback.answer()
    if callback.message is not None:
        await callback.message.edit_text(t(lang, "language_set"))
