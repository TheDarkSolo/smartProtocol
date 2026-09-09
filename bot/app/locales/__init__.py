from typing import Any, Literal

from .kk import kk
from .ru import ru

Lang = Literal["ru", "kk"]
DEFAULT_LANG: Lang = "ru"

# Значения — обычно str (шаблоны сообщений), но field_labels — вложенный
# dict[str, str], поэтому Any вместо str.
DICTIONARIES: dict[Lang, dict[str, Any]] = {"ru": ru, "kk": kk}


def t(lang: Lang, key: str, **kwargs: object) -> str:
    dictionary = DICTIONARIES.get(lang, DICTIONARIES[DEFAULT_LANG])
    template = dictionary.get(key, DICTIONARIES[DEFAULT_LANG].get(key, key))
    return template.format(**kwargs) if kwargs else template


def field_label(lang: Lang, field: str) -> str:
    """Человекочитаемая подпись поля для вопроса «напишите вручную» —
    см. field_labels в locales/ru.py и kk.py."""
    dictionary = DICTIONARIES.get(lang, DICTIONARIES[DEFAULT_LANG])
    labels = dictionary.get("field_labels", {})
    fallback = DICTIONARIES[DEFAULT_LANG].get("field_labels", {})
    return labels.get(field) or fallback.get(field, field)
