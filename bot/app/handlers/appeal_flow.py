"""Уточняющие вопросы и сборка черновика жалобы после разбора документа.

Единственное основание, для которого это здесь реализовано, —
"yellow_signal_no_safe_stop" (см. knowledge/grounds.yaml): жёлтый сигнал
светофора при невозможности безопасно остановиться. Три вопроса ниже —
ровно required_facts этого основания. Другое основание потребует другого
набора вопросов; это по-прежнему не общий движок подбора оснований (он
появится вместе с rule engine на этапе 1 в ROADMAP.md).

Ключевое: эти факты нельзя ничем заменить или угадать — только сам человек
знает, был ли он близко к стоп-линии и почему торможение было небезопасно.
Пропуск вопроса — это дыра в жалобе, а не мелочь.
"""

from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from .. import api_client
from ..locales import t
from ..user_state import get_lang

router = Router(name="appeal_flow")

GROUND_ID = "yellow_signal_no_safe_stop"

REQUIRED_FACT_FIELDS = [
    "applicant_name",
    "applicant_address",
    "applicant_phone",
    "applicant_iin",
    "authority_city",
    "decree_number",
    "decree_date",
    "offense_date",
    "offense_location",
    "vehicle_make",
    "vehicle_plate",
]

# Порядок здесь и порядок вопросов в состояниях должны совпадать построчно.
_QUESTIONS = [
    ("distance_to_stop_line_at_signal_change", "ask_distance"),
    ("braking_would_be_unsafe", "ask_braking"),
    ("continued_through_intersection", "ask_continued"),
]

# Телеграм режет сообщение на границе 4096 символов — режем сами по абзацам,
# чтобы не разрывать документ посреди слова.
_TELEGRAM_MESSAGE_LIMIT = 4000


class AppealStates(StatesGroup):
    ask_distance = State()
    ask_braking = State()
    ask_continued = State()


async def ask_first_question(message: Message, state: FSMContext, lang: str, *, case_id: str, base_facts: dict) -> None:
    await state.update_data(case_id=case_id, base_facts=base_facts, answers={})
    await state.set_state(AppealStates.ask_distance)
    await message.answer(t(lang, "ground_intro"))
    await message.answer(t(lang, "ask_distance"))


@router.message(AppealStates.ask_distance, F.text)
async def on_distance_answer(message: Message, state: FSMContext) -> None:
    await _store_answer_and_ask_next(message, state, field="distance_to_stop_line_at_signal_change")


@router.message(AppealStates.ask_braking, F.text)
async def on_braking_answer(message: Message, state: FSMContext) -> None:
    await _store_answer_and_ask_next(message, state, field="braking_would_be_unsafe")


@router.message(AppealStates.ask_continued, F.text)
async def on_continued_answer(message: Message, state: FSMContext) -> None:
    await _store_answer_and_ask_next(message, state, field="continued_through_intersection")


async def _store_answer_and_ask_next(message: Message, state: FSMContext, *, field: str) -> None:
    lang = get_lang(message.from_user.id)
    data = await state.get_data()
    answers = data.get("answers", {})
    answers[field] = message.text.strip()
    await state.update_data(answers=answers)

    current_index = next(i for i, (f, _) in enumerate(_QUESTIONS) if f == field)
    if current_index + 1 < len(_QUESTIONS):
        _, next_state_name = _QUESTIONS[current_index + 1]
        await state.set_state(getattr(AppealStates, next_state_name))
        await message.answer(t(lang, next_state_name))
        return

    await _finish(message, state, lang)


async def _finish(message: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    case_id = data["case_id"]
    base_facts = data["base_facts"]
    answers = data["answers"]

    status_message = await message.answer(t(lang, "drafting"))

    facts = {
        **{key: base_facts.get(key) for key in REQUIRED_FACT_FIELDS},
        "decree_kind": base_facts.get("decree_kind") or "постановление",
        "signed_date": date.today().strftime("%d.%m.%Y"),
        **answers,
    }

    try:
        result = await api_client.draft_appeal(case_id=case_id, ground_id=GROUND_ID, facts=facts)
    except api_client.ApiError as exc:
        await status_message.edit_text(t(lang, "draft_failed", error=str(exc)))
        await state.clear()
        return

    await status_message.edit_text(t(lang, "draft_ready"))
    for chunk in _split_message(result["document_text"]):
        await message.answer(chunk)

    await state.clear()


def _split_message(text: str, limit: int = _TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        split_at = remaining.rfind("\n\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks
