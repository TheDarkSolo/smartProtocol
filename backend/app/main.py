"""Smart Protocol — бэкенд.

Сейчас это скелет под лендинг: публичная конфигурация и приём постановления.
Разбор документа, подбор оснований и генерация жалобы появятся на этапе 1
(см. ROADMAP.md) и будут вынесены в фоновые задачи, а не в обработчик запроса.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .config import settings
from .schemas import (
    AppealDraftRequest,
    AppealDraftResponse,
    CaseCreated,
    CaseStatus,
    ExtractedDecreeResponse,
    MappedAppealFacts,
    PublicConfig,
    ReviewRequest,
    ReviewResponse,
)
from .services.appeal_draft import UnknownGroundError, draft_appeal, find_ground_for_article
from .services.protocol_extractor import decree_to_appeal_facts, extract_decree_from_pdf

app = FastAPI(
    title="Smart Protocol API",
    description="Конструктор жалоб на постановления по ПДД РК",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@app.get("/api/config", response_model=PublicConfig)
def public_config() -> PublicConfig:
    return PublicConfig(
        document_price_kzt=settings.document_price_kzt,
        mrp_kzt=settings.mrp_kzt,
        mrp_effective_from=settings.mrp_effective_from,
        max_upload_bytes=settings.max_upload_bytes,
        allowed_mime=settings.allowed_mime,
    )


@app.post("/api/cases", response_model=CaseCreated, status_code=201)
async def create_case(
    file: UploadFile = File(...),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> CaseCreated:
    """Принять постановление и завести дело.

    Файл читается целиком в память только потому, что лимит — 15 МБ. При
    переходе на объектное хранилище загрузка пойдёт по подписанному URL мимо
    этого сервиса, и этот код заменится на регистрацию уже загруженного ключа.
    """
    if file.content_type not in settings.allowed_mime:
        raise HTTPException(
            status_code=415,
            detail="Поддерживаются PDF, JPG, PNG и HEIC.",
        )

    payload = await file.read()
    if len(payload) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"Файл больше {limit_mb} МБ.",
        )
    if not payload:
        raise HTTPException(status_code=400, detail="Файл пустой.")

    case_id = uuid.uuid4().hex
    # Имя на диске — только case_id: имя файла от пользователя не доверенное
    # и может содержать персональные данные.
    suffix = Path(file.filename or "").suffix.lower()[:8]
    target_dir = Path(settings.upload_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / f"{case_id}{suffix}").write_bytes(payload)

    db.log_event("case_created", case_id=case_id, user_id=x_user_id)

    return CaseCreated(
        case_id=case_id,
        status=CaseStatus.created,
        filename=file.filename or "document",
        size_bytes=len(payload),
        created_at=datetime.now(timezone.utc),
    )


def _find_uploaded_file(case_id: str) -> Path:
    matches = list(Path(settings.upload_dir).glob(f"{case_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Дело не найдено.")
    return matches[0]


@app.post("/api/cases/{case_id}/extract", response_model=ExtractedDecreeResponse)
async def extract_case_decree(case_id: str) -> ExtractedDecreeResponse:
    """Разобрать уже загруженное постановление на структурированные поля.

    Пока это только PDF-путь (см. protocol_extractor.py): текстовый слой,
    который реально есть в постановлениях из госприложения. Фото и сканы без
    текстового слоя — резервный vision-путь, отдельный от этого эндпоинта, на
    этапе 1 ещё не реализован.

    Каждое поле в ответе, включая `None`, обязано быть показано пользователю
    на подтверждение — сервис не подставляет уверенные догадки вместо данных,
    которых не нашёл.
    """
    path = _find_uploaded_file(case_id)
    if path.suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=422,
            detail="Автоматический разбор пока работает только для PDF.",
        )

    payload = path.read_bytes()
    result = extract_decree_from_pdf(payload)

    return ExtractedDecreeResponse(
        decree_kind=result.decree_kind,
        decree_number=result.decree_number,
        decree_date=result.decree_date,
        article_code=result.article_code,
        offense_description=result.offense_description,
        offense_datetime=result.offense_datetime,
        offense_location=result.offense_location,
        vehicle_make=result.vehicle_make,
        vehicle_plate=result.vehicle_plate,
        vehicle_color=result.vehicle_color,
        owner_name=result.owner_name,
        owner_iin=result.owner_iin,
        owner_address=result.owner_address,
        owner_phone=result.owner_phone,
        amount_kzt=result.amount_kzt,
        authority_name=result.authority_name,
        device_name=result.device_name,
        device_verified_until=result.device_verified_until,
        source_page=result.source_page,
        is_protocol=result.is_protocol,
        warnings=result.warnings,
    )


@app.post("/api/cases/{case_id}/facts", response_model=MappedAppealFacts)
async def case_facts(
    case_id: str,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> MappedAppealFacts:
    """Разбор + перенос объективных полей документа в форму жалобы, одним
    вызовом. То, что нельзя достать из документа (обстоятельства защиты),
    остаётся вне этого ответа — их обязан спросить сам диалог с пользователем.
    """
    path = _find_uploaded_file(case_id)
    if path.suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=422,
            detail="Автоматический разбор пока работает только для PDF.",
        )

    decree = extract_decree_from_pdf(path.read_bytes())
    mapped = decree_to_appeal_facts(decree)

    missing = [key for key, value in mapped.items() if value is None]

    db.log_event(
        "extracted" if decree.is_protocol else "protocol_rejected",
        case_id=case_id,
        user_id=x_user_id,
    )

    return MappedAppealFacts(
        **mapped,
        article_code=decree.article_code,
        offense_description=decree.offense_description,
        source_page=decree.source_page,
        is_protocol=decree.is_protocol,
        supported_ground=find_ground_for_article(decree.article_code),
        missing_fields=missing,
        warnings=decree.warnings,
    )


@app.post("/api/cases/{case_id}/draft", response_model=AppealDraftResponse)
async def draft_case_appeal(
    case_id: str,
    body: AppealDraftRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> AppealDraftResponse:
    """Собрать черновик жалобы по одному отработанному основанию.

    Прямого прохода: пока нет ни БД дел, ни разбора документа (Этап 1 в
    ROADMAP.md), поэтому case_id здесь не проверяется на существование — это
    рабочий срез для проверки связки rule engine → шаблон → DeepSeek. Реальная
    проверка дела появится вместе с постоянным хранением дел.
    """
    try:
        result = await draft_appeal(ground_id=body.ground_id, facts=body.facts.model_dump())
    except UnknownGroundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.log_event("draft_created", case_id=case_id, user_id=x_user_id)

    return AppealDraftResponse(
        document_text=result.document_text,
        llm_used=result.llm_used,
        warnings=result.warnings,
    )


@app.post("/api/cases/{case_id}/review", response_model=ReviewResponse)
async def submit_review(
    case_id: str,
    body: ReviewRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> ReviewResponse:
    """Оценка результата пользователем. Не завязана на существование дела в
    БД (её пока и нет) — случайный несуществующий case_id просто запишется
    как есть, это не проблема на объёме одного бота на тестовой стадии."""
    db.save_review(rating=body.rating, case_id=case_id, user_id=x_user_id, comment=body.comment)
    return ReviewResponse()
