"""Сборка черновика жалобы: rule engine + шаблон + LLM только для фактов.

Архитектура намеренно негибкая в одном месте: DeepSeek никогда не видит
knowledge/articles.yaml и не может вставить в текст номер статьи. Он получает
только факты, которые сообщил пользователь, и инструкцию их связно изложить.
Все ссылки на нормы подставляет Jinja2-шаблон из уже проверяемых (или помеченных
как непроверенные) записей базы. Если это когда-нибудь поменяется на «пусть
модель сама решает, что писать» — anti-hallucination гарантия исчезает.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .deepseek_client import DeepSeekError, complete

KNOWLEDGE_DIR = Path(__file__).resolve().parents[3] / "knowledge"
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "appeals"

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(disabled_extensions=(".jinja",), default=False),
    trim_blocks=True,
    lstrip_blocks=True,
)


class UnknownGroundError(ValueError):
    pass


@dataclass
class AppealDraftResult:
    document_text: str
    llm_used: bool
    warnings: list[str]


@lru_cache
def _load_yaml(name: str) -> list[dict[str, Any]]:
    with open(KNOWLEDGE_DIR / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _articles_by_id() -> dict[str, dict[str, Any]]:
    return {a["id"]: a for a in _load_yaml("articles.yaml")}


def _grounds_by_id() -> dict[str, dict[str, Any]]:
    return {g["id"]: g for g in _load_yaml("grounds.yaml")}


def _norm_sentence(article: dict[str, Any]) -> str:
    """Норма как цельное предложение: «Согласно <code>, <диспозиция>»."""
    disposition = article["disposition_ru"].strip()
    return f"Согласно {article['code']}, {disposition[0].lower()}{disposition[1:]}"


def _decree_kind_ending(decree_kind: str) -> str:
    return "о" if decree_kind.strip().lower().endswith("е") else ""


def _decree_kind_instrumental(decree_kind: str) -> str:
    """Творительный падеж для «с ...». Не полноценная морфология — эвристика
    под конкретный, короткий список слов, которые реально встречаются в
    названиях документа (постановление, предписание, протокол, решение)."""
    stripped = decree_kind.strip()
    if stripped.lower().endswith("е"):
        return stripped[:-1] + "ем"
    return stripped + "ом"


def _lowercase_first(text: str) -> str:
    text = text.strip().rstrip(".")
    return text[:1].lower() + text[1:] if text else text


NARRATIVE_SYSTEM_PROMPT = """\
Ты помогаешь составить фактическую часть жалобы на постановление по ПДД в Казахстане.
Твоя единственная задача — связно и сухим процессуальным языком изложить ТОЛЬКО те
факты, которые явно перечислены в разделе «Факты от пользователя» ниже.

Правила, которые нельзя нарушать ни при каких обстоятельствах:
1. Не добавляй ни одного факта, детали, причины или обстоятельства, которых нет
   дословно или по смыслу во входных данных — даже правдоподобных и типичных
   для такой ситуации.
2. Если по какой-то теме (например, почему манёвр был безопасен или опасен)
   факт НЕ приведён — вообще не упоминай эту тему. Замена отсутствующего факта
   общей фразой вроде «это могло привести к потере контроля», «в целях
   безопасности», «как это обычно бывает» — запрещена, это и есть выдумывание.
3. Не упоминай номера статей, пунктов, законов — они не твоя часть документа.
4. Не делай выводов о виновности или невиновности — только описание обстоятельств.
5. Пиши от первого лица в прошедшем времени, 1-4 предложения, без канцелярских
   штампов сверх необходимого и без эмоциональной окраски.

Раздел «Отсутствующие факты» перечисляет темы, по которым данных нет: если тема
там — ты не просто пропускаешь формулировку, а не даёшь никакого намёка на неё,
даже нейтрального.
"""


def _build_narrative_prompt(ground: dict[str, Any], raw_facts: dict[str, str]) -> str:
    hint = ground.get("narrative_prompt_hint", "").strip()
    lines = [
        "Темы, которые в принципе относятся к этому основанию (пиши только то, что",
        "подтверждено фактами ниже — сам перечень тем не является фактом):",
        hint,
        "",
        "Факты от пользователя:",
    ]
    present = {key: value for key, value in raw_facts.items() if value}
    missing = [key for key, value in raw_facts.items() if not value]

    for key, value in present.items():
        lines.append(f"- {key}: {value}")
    if not present:
        lines.append("(фактов не предоставлено)")

    if missing:
        lines += [
            "",
            "Отсутствующие факты (не упоминай, не предполагай и не намекай на них):",
        ]
        lines += [f"- {key}" for key in missing]

    return "\n".join(lines)


def _fallback_narrative(raw_facts: dict[str, str]) -> str:
    """Без LLM — просто перечисляем сообщённые факты, ничего не сочиняя."""
    parts = [value.strip().rstrip(".") for value in raw_facts.values() if value and value.strip()]
    if not parts:
        return "Обстоятельства правонарушения указаны заявителем при подаче жалобы."
    return "По сообщённым заявителем сведениям: " + "; ".join(parts) + "."


async def draft_appeal(*, ground_id: str, facts: dict[str, Any]) -> AppealDraftResult:
    grounds = _grounds_by_id()
    if ground_id not in grounds:
        raise UnknownGroundError(f"Неизвестное основание: {ground_id}")
    ground = grounds[ground_id]
    articles = _articles_by_id()

    warnings: list[str] = []
    for article_id in ground["applies_to_articles"] + ground["supporting_norms"] + ground["closing_norms"]:
        article = articles[article_id]
        if article["confidence"] != "verified":
            warnings.append(
                f"Норма {article['code']} не подтверждена первоисточником "
                "(kz-legal-researcher ещё не прогонялся) — не выдавать пользователю без проверки."
            )

    main_article = articles[ground["applies_to_articles"][0]]

    raw_fact_keys = ground["required_facts"]
    raw_facts = {key: str(facts.get(key, "")).strip() for key in raw_fact_keys}
    missing = [key for key, value in raw_facts.items() if not value]
    if missing:
        warnings.append(f"Не заполнены факты, важные для этого основания: {', '.join(missing)}")

    llm_used = False
    try:
        narrative = await complete(
            NARRATIVE_SYSTEM_PROMPT,
            _build_narrative_prompt(ground, raw_facts),
        )
        llm_used = True
    except DeepSeekError as exc:
        warnings.append(f"DeepSeek недоступен, использован упрощённый пересказ фактов: {exc}")
        narrative = _fallback_narrative(raw_facts)

    decree_kind = str(facts.get("decree_kind", "постановление"))
    requests = [
        template.format(
            decree_kind=decree_kind,
            decree_number=facts.get("decree_number", ""),
            decree_date=facts.get("decree_date", ""),
        )
        for template in ground["document_requests"]
    ]

    context = {
        "authority_name": f"Департаменту полиции города {facts.get('authority_city', '')}",
        "applicant_name": facts.get("applicant_name", ""),
        "applicant_address": facts.get("applicant_address", ""),
        "applicant_phone": facts.get("applicant_phone", ""),
        "applicant_iin": facts.get("applicant_iin", ""),
        "document_title": facts.get("document_title", "Заявление"),
        "decree_kind": decree_kind,
        "decree_kind_ending": _decree_kind_ending(decree_kind),
        "decree_kind_instrumental": _decree_kind_instrumental(decree_kind),
        "decree_number": facts.get("decree_number", ""),
        "decree_date": facts.get("decree_date", ""),
        "offense_date": facts.get("offense_date", ""),
        "offense_location": facts.get("offense_location", ""),
        "vehicle_make": facts.get("vehicle_make", ""),
        "vehicle_plate": facts.get("vehicle_plate", ""),
        "article_code": main_article["code"],
        "offense_description": _lowercase_first(main_article["disposition_ru"]),
        "observed_detail": facts.get("observed_detail"),
        "supporting_norms": [_norm_sentence(articles[a]) for a in ground["supporting_norms"]],
        "narrative": narrative,
        "closing_norms": [_norm_sentence(articles[a]) for a in ground["closing_norms"]],
        "requests": requests,
        "signed_date": facts.get("signed_date", ""),
    }

    template = _jinja_env.get_template("complaint_ru.txt.jinja")
    document_text = template.render(**context)
    # Схлопываем тройные+ переносы строк, которые остаются от Jinja-блоков.
    while "\n\n\n" in document_text:
        document_text = document_text.replace("\n\n\n", "\n\n")

    return AppealDraftResult(document_text=document_text.strip() + "\n", llm_used=llm_used, warnings=warnings)
