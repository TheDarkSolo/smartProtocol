"""Приём постановления: файл или фото пересылается на бэкенд как есть.

После загрузки PDF бот сразу пробует разобрать документ (см. app/api_client.py
fetch_case_facts → backend /api/cases/{case_id}/facts) и, если получилось,
переходит к уточняющим вопросам (appeal_flow.py). Для фото автоматический
разбор пока не поддержан на бэкенде (только PDF с текстовым слоем) — бот
честно говорит об этом, а не делает вид, что процесс завершён.
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from .. import api_client
from ..locales import t
from ..user_state import get_lang
from .appeal_flow import start_clarification

router = Router(name="upload")


@router.message(F.document)
async def on_document(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    document = message.document
    await _handle_upload(
        message,
        state,
        filename=document.file_name or "document",
        content_type=document.mime_type or "application/octet-stream",
        file_id=document.file_id,
        lang=lang,
    )


@router.message(F.photo)
async def on_photo(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    # Telegram присылает несколько размеров одного фото — берём самое крупное.
    largest = message.photo[-1]
    await _handle_upload(
        message,
        state,
        filename=f"{largest.file_id}.jpg",
        content_type="image/jpeg",
        file_id=largest.file_id,
        lang=lang,
    )


async def _handle_upload(
    message: Message, state: FSMContext, *, filename: str, content_type: str, file_id: str, lang: str
) -> None:
    try:
        config = await api_client.fetch_config()
    except Exception:
        await message.answer(t(lang, "backend_offline"))
        return

    if content_type not in config.allowed_mime:
        await message.answer(t(lang, "unsupported_type"))
        return

    status_message = await message.answer(t(lang, "receiving"))

    bot = message.bot
    file = await bot.get_file(file_id)
    if file.file_size and file.file_size > config.max_upload_bytes:
        limit_mb = config.max_upload_bytes // (1024 * 1024)
        await status_message.edit_text(t(lang, "too_large", limit_mb=limit_mb))
        return

    buffer = await bot.download_file(file.file_path)
    payload = buffer.read()

    user_id = str(message.from_user.id)
    try:
        case = await api_client.create_case(
            filename=filename, content_type=content_type, payload=payload, user_id=user_id
        )
    except api_client.ApiError as exc:
        if exc.status_code:
            await status_message.edit_text(str(exc))
        else:
            await status_message.edit_text(t(lang, "backend_offline"))
        return

    # Пока нет однозначного успеха, промежуточный статус остаётся одним и тем
    # же редактируемым сообщением — не заводим отдельное "дело создано",
    # которое тут же обесценивается следующим сообщением об отказе.
    if content_type != "application/pdf":
        # Разбор без текстового слоя (vision-путь) на бэкенде ещё не готов —
        # честно говорим об этом, а не притворяемся, что фото тоже разбирается.
        await status_message.edit_text(t(lang, "extraction_pdf_only"))
        return

    try:
        facts = await api_client.fetch_case_facts(case.case_id, user_id=user_id)
    except api_client.ApiError as exc:
        await status_message.edit_text(t(lang, "backend_offline") if not exc.status_code else str(exc))
        return

    if not facts.get("is_protocol"):
        # Быстрый отказ здесь и есть экономия токенов: дальше по цепочке —
        # уточняющие вопросы и вызов DeepSeek — для случайного PDF просто не
        # запускаются. Разбор до этой точки — pdfplumber, локально, без LLM.
        await status_message.edit_text(t(lang, "not_a_protocol"))
        return

    await status_message.edit_text(
        t(
            lang,
            "extracted_summary",
            page=facts.get("source_page") or "—",
            decree_kind=facts.get("decree_kind") or "—",
            decree_number=facts.get("decree_number") or "—",
            decree_date=facts.get("decree_date") or "—",
            article_code=facts.get("article_code") or "—",
            offense_description=facts.get("offense_description") or "—",
            offense_date=facts.get("offense_date") or "—",
            offense_location=facts.get("offense_location") or "—",
            vehicle_make=facts.get("vehicle_make") or "—",
            vehicle_plate=facts.get("vehicle_plate") or "—",
            applicant_name=facts.get("applicant_name") or "—",
            applicant_iin=facts.get("applicant_iin") or "—",
        )
    )

    # Раньше здесь была прямая проверка "supported_ground == GROUND_ID иначе
    # отказ" — это оставалось от версии до того, как в appeal_flow.py
    # появились меню универсальных оснований и открытый вопрос. Из-за этого
    # start_clarification (а с ним вся новая логика) для любой статьи, кроме
    # жёлтого сигнала, вообще не вызывался — бот всегда прыгал сразу к
    # отказу. Теперь маршрутизация (жёлтый свет vs меню оснований vs отказ)
    # целиком внутри start_clarification, здесь она не дублируется.
    await start_clarification(message, state, lang, case_id=case.case_id, base_facts=facts)
