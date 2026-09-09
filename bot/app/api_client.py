"""Клиент бэкенда Smart Protocol.

Бот не хранит бизнес-логику: он собирает файл от пользователя и передаёт его
на бэкенд тем же путём, что и веб-загрузка (POST /api/cases), — единая точка
принятия постановлений вместо двух параллельных реализаций.

Каждый вызов несёт X-User-Id (Telegram user id) — по нему бэкенд считает
уникальных пользователей бота в журнале событий (app/db.py). У веба такой
identity пока нет (анонимная сессия), поэтому статистика различает источники.
"""

from dataclasses import dataclass

import httpx

from .config import settings


def _headers(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


class ApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class PublicConfig:
    max_upload_bytes: int
    allowed_mime: list[str]


@dataclass
class CaseCreated:
    case_id: str
    status: str


async def fetch_config() -> PublicConfig:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{settings.api_base_url}/api/config")
    response.raise_for_status()
    data = response.json()
    return PublicConfig(max_upload_bytes=data["max_upload_bytes"], allowed_mime=data["allowed_mime"])


async def create_case(*, filename: str, content_type: str, payload: bytes, user_id: str) -> CaseCreated:
    files = {"file": (filename, payload, content_type)}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.api_base_url}/api/cases", files=files, headers=_headers(user_id)
            )
    except httpx.HTTPError as exc:
        raise ApiError(f"Бэкенд недоступен: {exc}") from exc

    if response.status_code >= 400:
        detail = response.json().get("detail", "Не удалось создать дело.")
        raise ApiError(detail, status_code=response.status_code)

    data = response.json()
    return CaseCreated(case_id=data["case_id"], status=data["status"])


async def fetch_case_facts(case_id: str, *, user_id: str) -> dict:
    """Разбор PDF + перенос объективных полей в форму жалобы, одним запросом."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.api_base_url}/api/cases/{case_id}/facts", headers=_headers(user_id)
            )
    except httpx.HTTPError as exc:
        raise ApiError(f"Бэкенд недоступен: {exc}") from exc

    if response.status_code >= 400:
        detail = response.json().get("detail", "Не удалось разобрать документ.")
        raise ApiError(detail, status_code=response.status_code)

    return response.json()


async def submit_review(*, case_id: str, rating: int, comment: str | None, user_id: str) -> None:
    body = {"rating": rating, "comment": comment}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{settings.api_base_url}/api/cases/{case_id}/review", json=body, headers=_headers(user_id)
            )
        response.raise_for_status()
    except httpx.HTTPError:
        # Отзыв — не критичный шаг сценария: если бэкенд недоступен именно
        # в этот момент, не заставляем пользователя разбираться с ошибкой
        # ради необязательной оценки. Просто не сохраняем.
        pass


async def submit_missed_ground(
    *, case_id: str, note: str, article_code: str | None, offense_description: str | None, user_id: str
) -> None:
    body = {"note": note, "article_code": article_code, "offense_description": offense_description}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{settings.api_base_url}/api/cases/{case_id}/missed-ground", json=body, headers=_headers(user_id)
            )
        response.raise_for_status()
    except httpx.HTTPError:
        # Как и с отзывом — необязательный шаг, не блокируем пользователя
        # из-за временной недоступности бэкенда.
        pass


async def draft_appeal(*, case_id: str, ground_id: str, facts: dict, user_id: str) -> dict:
    body = {"ground_id": ground_id, "facts": facts}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{settings.api_base_url}/api/cases/{case_id}/draft", json=body, headers=_headers(user_id)
            )
    except httpx.HTTPError as exc:
        raise ApiError(f"Бэкенд недоступен: {exc}") from exc

    if response.status_code >= 400:
        detail = response.json().get("detail", "Не удалось собрать черновик.")
        raise ApiError(detail, status_code=response.status_code)

    return response.json()
