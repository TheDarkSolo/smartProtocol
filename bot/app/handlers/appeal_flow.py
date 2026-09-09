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
from aiogram.types import CallbackQuery, Message

from .. import api_client
from ..keyboards import review_rating_keyboard, review_skip_keyboard
from ..locales import field_label, t
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
    ask_missing_field = State()
    ask_distance = State()
    ask_braking = State()
    ask_continued = State()
    ask_review_rating = State()
    ask_review_comment = State()


async def start_clarification(message: Message, state: FSMContext, lang: str, *, case_id: str, base_facts: dict) -> None:
    """Точка входа после успешного разбора документа.

    Экстракция никогда не считается «либо всё, либо ничего»: то, что не
    нашлось в PDF (сегодня — город органа, завтра — что-то ещё), не должно
    останавливать сценарий. Недостающие поля из REQUIRED_FACT_FIELDS
    просто спрашиваются текстом, одно за другим, прежде чем перейти к
    вопросам по существу основания.
    """
    missing = [field for field in REQUIRED_FACT_FIELDS if not base_facts.get(field)]
    if not missing:
        await _ask_ground_questions(message, state, lang, case_id=case_id, base_facts=base_facts)
        return

    await state.update_data(case_id=case_id, base_facts=dict(base_facts), missing_queue=missing)
    await state.set_state(AppealStates.ask_missing_field)
    await message.answer(t(lang, "ask_missing_field", label=field_label(lang, missing[0])))


@router.message(AppealStates.ask_missing_field, F.text)
async def on_missing_field_answer(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    data = await state.get_data()
    queue = data.get("missing_queue") or []
    if not queue:
        # Не должно происходить в норме — защитная ветка от рассинхронизации.
        await state.clear()
        return

    field = queue[0]
    base_facts = data["base_facts"]
    base_facts[field] = message.text.strip()
    remaining = queue[1:]
    await state.update_data(base_facts=base_facts, missing_queue=remaining)

    if remaining:
        await message.answer(t(lang, "ask_missing_field", label=field_label(lang, remaining[0])))
        return

    await _ask_ground_questions(message, state, lang, case_id=data["case_id"], base_facts=base_facts)


async def _ask_ground_questions(message: Message, state: FSMContext, lang: str, *, case_id: str, base_facts: dict) -> None:
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
        result = await api_client.draft_appeal(
            case_id=case_id, ground_id=GROUND_ID, facts=facts, user_id=str(message.from_user.id)
        )
    except api_client.ApiError as exc:
        await status_message.edit_text(t(lang, "draft_failed", error=str(exc)))
        await state.clear()
        return

    await status_message.edit_text(t(lang, "draft_ready"))
    for chunk in _split_message(result["document_text"]):
        await message.answer(chunk)

    # Дело сделано — дальше короткий опрос об оценке, не сбрасываем состояние
    # сразу, а переводим в ожидание оценки. case_id ещё нужен для отзыва.
    await state.set_data({"case_id": case_id})
    await state.set_state(AppealStates.ask_review_rating)
    await message.answer(t(lang, "review_prompt"), reply_markup=review_rating_keyboard)


@router.callback_query(AppealStates.ask_review_rating, F.data.startswith("review:"))
async def on_review_rating(callback: CallbackQuery, state: FSMContext) -> None:
    lang = get_lang(callback.from_user.id)
    rating = int(callback.data.split(":", 1)[1])
    await state.update_data(review_rating=rating)
    await state.set_state(AppealStates.ask_review_comment)
    await callback.answer()
    if callback.message is not None:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            t(lang, "review_ask_comment"),
            reply_markup=review_skip_keyboard(t(lang, "review_skip_button")),
        )


@router.message(AppealStates.ask_review_comment, F.text)
async def on_review_comment(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    await _submit_review(state, user_id=str(message.from_user.id), comment=message.text.strip())
    await message.answer(t(lang, "review_thanks"))
    await state.clear()


@router.callback_query(AppealStates.ask_review_comment, F.data == "review_skip")
async def on_review_skip(callback: CallbackQuery, state: FSMContext) -> None:
    lang = get_lang(callback.from_user.id)
    await callback.answer()
    if callback.message is not None:
        await callback.message.edit_reply_markup(reply_markup=None)
    await _submit_review(state, user_id=str(callback.from_user.id), comment=None)
    if callback.message is not None:
        await callback.message.answer(t(lang, "review_thanks"))
    await state.clear()


async def _submit_review(state: FSMContext, *, user_id: str, comment: str | None) -> None:
    data = await state.get_data()
    case_id = data.get("case_id")
    rating = data.get("review_rating")
    if rating is None or case_id is None:
        return
    await api_client.submit_review(case_id=case_id, rating=rating, comment=comment, user_id=user_id)


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
