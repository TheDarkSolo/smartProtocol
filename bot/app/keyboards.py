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


def universal_gate_keyboard(yes_label: str, no_label: str) -> InlineKeyboardMarkup:
    """Общая клавиатура «да/нет» для любого универсального основания в
    очереди (см. UNIVERSAL_GROUNDS в appeal_flow.py) — один виджет на все,
    а не отдельная клавиатура под каждое."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=yes_label, callback_data="universal:yes")],
            [InlineKeyboardButton(text=no_label, callback_data="universal:no")],
        ]
    )
