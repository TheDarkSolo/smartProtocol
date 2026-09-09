from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

language_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Русский", callback_data="lang:ru"),
            InlineKeyboardButton(text="Қазақша", callback_data="lang:kk"),
        ]
    ]
)

review_rating_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=str(n), callback_data=f"review:{n}") for n in range(1, 6)],
    ]
)


def review_skip_keyboard(skip_label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=skip_label, callback_data="review_skip")]]
    )


def driver_choice_keyboard(me_label: str, other_label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=me_label, callback_data="driver:me")],
            [InlineKeyboardButton(text=other_label, callback_data="driver:other")],
        ]
    )
