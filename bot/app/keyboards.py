from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

language_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Русский", callback_data="lang:ru"),
            InlineKeyboardButton(text="Қазақша", callback_data="lang:kk"),
        ]
    ]
)
