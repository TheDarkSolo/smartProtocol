from typing import Literal

from .kk import kk
from .ru import ru

Lang = Literal["ru", "kk"]
DEFAULT_LANG: Lang = "ru"

DICTIONARIES: dict[Lang, dict[str, str]] = {"ru": ru, "kk": kk}


def t(lang: Lang, key: str, **kwargs: object) -> str:
    dictionary = DICTIONARIES.get(lang, DICTIONARIES[DEFAULT_LANG])
    template = dictionary.get(key, DICTIONARIES[DEFAULT_LANG].get(key, key))
    return template.format(**kwargs) if kwargs else template
