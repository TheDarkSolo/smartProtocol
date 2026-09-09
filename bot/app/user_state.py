"""Язык пользователя — на процесс, не персистентно.

Для MVP этого достаточно: перезапуск бота сбросит выбор языка, пользователь
просто выберет его заново командой /language. На проде — вынести в Redis
вместе с FSM (см. .claude/agents/tg-bot-dev.md), когда появится общее
хранилище состояния между инстансами бота.
"""

from .locales import DEFAULT_LANG, Lang

_lang_by_user: dict[int, Lang] = {}


def get_lang(user_id: int) -> Lang:
    return _lang_by_user.get(user_id, DEFAULT_LANG)


def set_lang(user_id: int, lang: Lang) -> None:
    _lang_by_user[user_id] = lang
