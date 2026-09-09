from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class CaseStatus(str, Enum):
    """Дело = одно постановление. Конечный автомат из ROADMAP."""

    created = "created"
    extracted = "extracted"
    clarified = "clarified"
    drafted = "drafted"
    paid = "paid"
    delivered = "delivered"


class PublicConfig(BaseModel):
    """Всё, что лендингу нужно знать о ценах и ограничениях загрузки.

    Фронтенд не хардкодит ни цену, ни лимиты — иначе они разъедутся с бэкендом.
    """

    document_price_kzt: int
    mrp_kzt: int
    mrp_effective_from: str
    max_upload_bytes: int
    allowed_mime: list[str]


class CaseCreated(BaseModel):
    case_id: str
    status: CaseStatus
    filename: str
    size_bytes: int
    created_at: datetime


class ErrorResponse(BaseModel):
    detail: str = Field(description="Причина отказа, пригодная для показа пользователю")


class AppealFacts(BaseModel):
    """Данные для сборки жалобы. На проде часть полей придёт из извлечения
    документа (protocol-extractor), часть — из ответов пользователя на
    уточняющие вопросы. Здесь — плоская структура для прямой проверки
    генерации без готового пайплайна извлечения."""

    applicant_name: str
    applicant_address: str
    applicant_phone: str
    applicant_iin: str
    authority_city: str

    decree_kind: str = "постановление"
    decree_number: str
    decree_date: str

    offense_date: str
    offense_location: str
    vehicle_make: str
    vehicle_plate: str
    observed_detail: str | None = None

    signed_date: str

    # Факты под основание "yellow_signal_no_safe_stop" — см. knowledge/grounds.yaml.
    # Для другого ground_id набор обязательных фактов будет другим.
    distance_to_stop_line_at_signal_change: str | None = None
    braking_would_be_unsafe: str | None = None
    continued_through_intersection: str | None = None


class ExtractedDecreeResponse(BaseModel):
    """Результат разбора PDF. Поле `None` значит «не нашли», не «пусто» —
    это осознанно: фронтенд обязан показать такие поля на подтверждение
    пользователю, а не тихо оставить дыру в жалобе (protocol-extractor)."""

    decree_kind: str | None
    decree_number: str | None
    decree_date: str | None
    article_code: str | None
    offense_description: str | None
    offense_datetime: str | None
    offense_location: str | None
    vehicle_make: str | None
    vehicle_plate: str | None
    vehicle_color: str | None
    owner_name: str | None
    owner_iin: str | None
    owner_address: str | None
    owner_phone: str | None
    amount_kzt: float | None
    authority_name: str | None
    device_name: str | None
    device_verified_until: str | None
    source_page: int | None
    warnings: list[str] = Field(default_factory=list)


class AppealDraftRequest(BaseModel):
    ground_id: str = "yellow_signal_no_safe_stop"
    facts: AppealFacts


class AppealDraftResponse(BaseModel):
    document_text: str
    llm_used: bool = Field(description="True, если изложение фактов сформировал DeepSeek, а не резервный пересказ")
    warnings: list[str] = Field(default_factory=list)
