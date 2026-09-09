"""Приём постановления: файл или фото пересылается на бэкенд как есть.

Разбор документа и подбор оснований здесь намеренно не происходят — этого
пока нет и на бэкенде (Этап 1 в ROADMAP.md). Бот честно говорит пользователю,
что дальше эта часть в разработке, а не делает вид, что процесс завершён.
"""

from aiogram import F, Router
from aiogram.types import Message

from .. import api_client
from ..locales import t
from ..user_state import get_lang

router = Router(name="upload")


@router.message(F.document)
async def on_document(message: Message) -> None:
    lang = get_lang(message.from_user.id)
    document = message.document
    await _handle_upload(
        message,
        filename=document.file_name or "document",
        content_type=document.mime_type or "application/octet-stream",
        file_id=document.file_id,
        lang=lang,
    )


@router.message(F.photo)
async def on_photo(message: Message) -> None:
    lang = get_lang(message.from_user.id)
    # Telegram присылает несколько размеров одного фото — берём самое крупное.
    largest = message.photo[-1]
    await _handle_upload(
        message,
        filename=f"{largest.file_id}.jpg",
        content_type="image/jpeg",
        file_id=largest.file_id,
        lang=lang,
    )


async def _handle_upload(message: Message, *, filename: str, content_type: str, file_id: str, lang: str) -> None:
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

    try:
        case = await api_client.create_case(filename=filename, content_type=content_type, payload=payload)
    except api_client.ApiError as exc:
        if exc.status_code:
            await status_message.edit_text(str(exc))
        else:
            await status_message.edit_text(t(lang, "backend_offline"))
        return

    await status_message.edit_text(t(lang, "case_created", case_id=case.case_id))
