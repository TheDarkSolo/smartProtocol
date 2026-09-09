"""Извлечение данных из PDF постановления/предписания по ПДД РК.

Многие постановления в РК — двуязычные PDF (казахская и русская версия
одного и того же документа на разных страницах, обычно чередуясь).
Текстовый слой в них уже есть, поэтому извлекаем текст напрямую — это на
порядок точнее и дешевле vision (см. .claude/agents/protocol-extractor.md).
Vision остаётся резервным путём для сканов и фото без текстового слоя.

Разбор регулярками намеренно строгий: не нашли поле — `None`, а не догадка.
Придуманный номер постановления или дата ломает всё, что строится поверх
(срок обжалования, сама жалоба).
"""

import io
import re
from dataclasses import dataclass, field

import pdfplumber

# Буквы, которых нет в русском алфавите, но есть в казахском — по ним отличаем
# казахскую страницу двуязычного документа от русской.
_KAZAKH_ONLY_LETTERS = set("әғқңөұүһі" + "әғқңөұүһі".upper())

# Слова у самых краёв страницы (боковой перевёрнутый штамп) — не часть текста.
_MARGIN_X_MIN = 20
_MARGIN_X_MAX = 550


@dataclass
class ExtractedDecree:
    """Данные из одной (русскоязычной) страницы постановления.

    Поля, которые не удалось найти в тексте, остаются `None` — это сигнал
    показать их пользователю на подтверждение, а не подставлять пусто.
    """

    decree_kind: str | None = None
    decree_number: str | None = None
    decree_date: str | None = None
    article_code: str | None = None
    offense_description: str | None = None
    offense_datetime: str | None = None
    offense_location: str | None = None
    vehicle_make: str | None = None
    vehicle_plate: str | None = None
    vehicle_color: str | None = None
    owner_name: str | None = None
    owner_iin: str | None = None
    owner_address: str | None = None
    owner_phone: str | None = None
    amount_kzt: float | None = None
    authority_name: str | None = None
    device_name: str | None = None
    device_verified_until: str | None = None
    source_page: int | None = None
    warnings: list[str] = field(default_factory=list)


def extract_pages_text(pdf_bytes: bytes) -> list[str]:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def _kazakh_ratio(text: str) -> float:
    cyrillic = [ch for ch in text if "а" <= ch.lower() <= "я" or ch.lower() in _KAZAKH_ONLY_LETTERS]
    if not cyrillic:
        return 0.0
    kazakh_only = sum(1 for ch in cyrillic if ch in _KAZAKH_ONLY_LETTERS)
    return kazakh_only / len(cyrillic)


def find_russian_decree_page(pages: list[str]) -> int | None:
    """Индекс (с 0) страницы с русской версией постановления/предписания.

    Эвристика: среди страниц, где вообще есть кириллица, берём с наименьшей
    долей казахских букв — и только если на ней встречается заголовок вида
    "ПОСТАНОВЛЕНИЕ"/"ПРЕДПИСАНИЕ" (не платёжная квитанция и не корешок).
    """
    candidates = []
    for i, text in enumerate(pages):
        if not text.strip():
            continue
        if not re.search(r"ПОСТАНОВЛЕНИЕ|ПРЕДПИСАНИЕ", text):
            continue
        candidates.append((i, _kazakh_ratio(text)))

    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[1])
    return candidates[0][0]


def _group_lines(words: list[dict]) -> list[list[dict]]:
    lines: dict[int, list[dict]] = {}
    for w in words:
        if w["x0"] < _MARGIN_X_MIN or w["x0"] > _MARGIN_X_MAX:
            continue  # боковой перевёрнутый штамп на полях страницы
        key = round(w["top"] / 3) * 3
        lines.setdefault(key, []).append(w)
    return [sorted(lines[top], key=lambda w: w["x0"]) for top in sorted(lines)]


def _split_two_column_block(page, y_top: float, y_bottom: float) -> tuple[str, str]:
    """Разводит двухколоночную таблицу ("Сведения о ТС" | "Сведения о владельце")
    на два независимых потока текста поx-координате колонки.

    Обычный `extract_text()` читает такую таблицу построчно слева направо и
    склеивает конец левой колонки с началом правой — поле "Марка, модель"
    утыкается в "Дата рождения" следующей строки соседней колонки.

    Разрыв внутри строки (как в `"№ СРТС:  ZI99643805"`) — ненадёжный
    ориентир: короткая подпись поля может дать такой же по величине зазор,
    как настоящая граница колонки, и тогда часть левой колонки утекает в
    правую. Вместо этого один раз находим саму границу колонки по заголовку
    таблицы ("Сведения о ТС" / "Сведения о владельце") и затем просто
    классифицируем каждое слово по тому, левее оно этой границы или правее.
    """
    header = next((line for line in _group_lines(page.extract_words()) if any(
        w["text"] == "Сведения" for w in line
    ) and sum(1 for w in line if w["text"] == "Сведения") >= 2), None)
    if not header:
        raise ValueError("Не найден заголовок двухколоночной таблицы")

    svedenia_positions = [w["x0"] for w in header if w["text"] == "Сведения"]
    column_boundary = min(svedenia_positions[1:]) - 15

    words = [w for w in page.extract_words() if y_top <= w["top"] < y_bottom]
    left_parts: list[str] = []
    right_parts: list[str] = []

    for line in _group_lines(words):
        left_words = [w["text"] for w in line if w["x0"] < column_boundary]
        right_words = [w["text"] for w in line if w["x0"] >= column_boundary]
        if left_words:
            left_parts.append(" ".join(left_words))
        if right_words:
            right_parts.append(" ".join(right_words))

    return "\n".join(left_parts), "\n".join(right_parts)


def _search(pattern: str, text: str, flags: int = re.IGNORECASE) -> str | None:
    match = re.search(pattern, text, flags)
    if not match:
        return None
    value = match.group(1).strip()
    return re.sub(r"\s+", " ", value)


def parse_decree_page(page) -> ExtractedDecree:
    text = page.extract_text() or ""
    result = ExtractedDecree()
    warnings: list[str] = []

    kind_match = re.search(r"(ПОСТАНОВЛЕНИЕ|ПРЕДПИСАНИЕ)", text)
    result.decree_kind = kind_match.group(1).capitalize() if kind_match else None

    result.decree_number = _search(r"№\s*(\d{6,})", text)
    result.decree_date = _search(r"от\s+(\d{2}\.\d{2}\.\d{4})\s*г\.", text)

    article_match = re.search(r"стать\w*\s+(\d+)\s+часть\w*\s+(\d+)", text, re.IGNORECASE)
    result.article_code = f"ч.{article_match.group(2)} ст. {article_match.group(1)} КоАП РК" if article_match else None

    result.offense_description = _search(
        r"Сущность правонарушения:\s*(.+?)(?=Фотоизображение|Тіркелген|$)", text, re.IGNORECASE | re.DOTALL
    )
    result.offense_datetime = _search(r"Дата,?\s*время совершения:\s*([\d.]+\s+[\d:]+)", text)
    result.offense_location = _search(
        r"Место совершения:\s*(.+?)(?=Сущность правонарушения:)", text, re.IGNORECASE | re.DOTALL
    )

    # Таблица "Сведения о ТС / Сведения о владельце" — двухколоночная, разбираем
    # координатным способом, а не по общему тексту страницы.
    table_start = re.search(r"Сведения о транспортном средстве:", text)
    table_end = re.search(r"Сведения о нарушении:", text)
    if table_start and table_end:
        words_all = page.extract_words()
        y_top = min(
            (w["top"] for w in words_all if "транспортном" == w["text"].rstrip(":")),
            default=None,
        )
        y_bottom = min(
            (w["top"] for w in words_all if w["text"].rstrip(":") == "нарушении"),
            default=None,
        )
        if y_top is not None and y_bottom is not None:
            vehicle_text, owner_text = _split_two_column_block(page, y_top - 2, y_bottom - 2)

            result.vehicle_plate = _search(r"Госномер:\s*(\S+)", vehicle_text)
            result.vehicle_make = _search(r"Марка,?\s*модель:\s*(.+?)$", vehicle_text, re.IGNORECASE | re.MULTILINE)
            result.vehicle_color = _search(r"Цвет:\s*(\S+)", vehicle_text)

            result.owner_name = _search(
                r"Фамилия,?\s*имя,?\s*отчество:\s*(.+?)(?=\n[^\n]{0,30}:|\Z)", owner_text, re.IGNORECASE | re.DOTALL
            )
            result.owner_iin = _search(r"ИИН(?:/БИН)?:\s*(\d{12})", owner_text)
            result.owner_address = _search(
                r"Адрес:\s*(.+?)(?=Телефон:|\Z)", owner_text, re.IGNORECASE | re.DOTALL
            )
            result.owner_phone = _search(r"Телефон:\s*(\d{9,15})", owner_text)
        else:
            warnings.append("Не удалось разметить таблицу ТС/владельца по координатам слов.")
    else:
        warnings.append("Не найден блок «Сведения о транспортном средстве / о владельце».")

    amount = _search(r"Сумма наложенного штрафа:\s*([\d.,]+)\s*тенге", text)
    if amount:
        try:
            result.amount_kzt = float(amount.replace(",", "."))
        except ValueError:
            warnings.append(f"Не удалось разобрать сумму штрафа: {amount!r}")

    authority = re.search(r"^(ДЕПАРТАМЕНТ ПОЛИЦИИ .+?)(?:\n|$)", text, re.MULTILINE)
    result.authority_name = authority.group(1).strip() if authority else None

    result.device_name = _search(r"Наименование:\s*(.+?)(?=Серийный номер:|$)", text, re.IGNORECASE | re.DOTALL)
    result.device_verified_until = _search(r"Поверка действительна до:\s*([\d.]+)", text)

    for field_name in ("decree_kind", "decree_number", "decree_date", "article_code", "owner_name", "owner_iin"):
        if getattr(result, field_name) is None:
            warnings.append(f"Не найдено ключевое поле: {field_name}")

    result.warnings = warnings
    return result


def extract_decree_from_pdf(pdf_bytes: bytes) -> ExtractedDecree:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages_text = [p.extract_text() or "" for p in pdf.pages]
        page_index = find_russian_decree_page(pages_text)
        if page_index is None:
            result = ExtractedDecree()
            result.warnings = ["Не найдена страница с русской версией постановления/предписания."]
            return result

        result = parse_decree_page(pdf.pages[page_index])
        result.source_page = page_index + 1
        return result
