"""Клиент бэкенда Smart Protocol.

Бот не хранит бизнес-логику: он собирает файл от пользователя и передаёт его
на бэкенд тем же путём, что и веб-загрузка (POST /api/cases), — единая точка
принятия постановлений вместо двух параллельных реализаций.
"""

from dataclasses import dataclass

import httpx

from .config import settings


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


async def create_case(*, filename: str, content_type: str, payload: bytes) -> CaseCreated:
    files = {"file": (filename, payload, content_type)}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{settings.api_base_url}/api/cases", files=files)
    except httpx.HTTPError as exc:
        raise ApiError(f"Бэкенд недоступен: {exc}") from exc

    if response.status_code >= 400:
        detail = response.json().get("detail", "Не удалось создать дело.")
        raise ApiError(detail, status_code=response.status_code)

    data = response.json()
    return CaseCreated(case_id=data["case_id"], status=data["status"])


async def fetch_case_facts(case_id: str) -> dict:
    """Разбор PDF + перенос объективных полей в форму жалобы, одним запросом."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{settings.api_base_url}/api/cases/{case_id}/facts")
    except httpx.HTTPError as exc:
        raise ApiError(f"Бэкенд недоступен: {exc}") from exc

    if response.status_code >= 400:
        detail = response.json().get("detail", "Не удалось разобрать документ.")
        raise ApiError(detail, status_code=response.status_code)

    return response.json()


async def draft_appeal(*, case_id: str, ground_id: str, facts: dict) -> dict:
    body = {"ground_id": ground_id, "facts": facts}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{settings.api_base_url}/api/cases/{case_id}/draft", json=body)
    except httpx.HTTPError as exc:
        raise ApiError(f"Бэкенд недоступен: {exc}") from exc

    if response.status_code >= 400:
        detail = response.json().get("detail", "Не удалось собрать черновик.")
        raise ApiError(detail, status_code=response.status_code)

    return response.json()
