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


def ground_menu_keyboard(buttons: list[tuple[str, str]], none_label: str) -> InlineKeyboardMarkup:
    """Меню оснований одним сообщением — человек сам выбирает, что похоже на
    его ситуацию (см. UNIVERSAL_GROUNDS в appeal_flow.py), вместо вопросов
    «да/нет» по одному на каждое. buttons — пары (подпись, id основания)."""
    rows = [[InlineKeyboardButton(text=label, callback_data=f"ground_choice:{ground_id}")] for label, ground_id in buttons]
    rows.append([InlineKeyboardButton(text=none_label, callback_data="ground_choice:none")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
