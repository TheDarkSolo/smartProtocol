"""Smart Protocol — бэкенд.

Сейчас это скелет под лендинг: публичная конфигурация и приём постановления.
Разбор документа, подбор оснований и генерация жалобы появятся на этапе 1
(см. ROADMAP.md) и будут вынесены в фоновые задачи, а не в обработчик запроса.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .schemas import AppealDraftRequest, AppealDraftResponse, CaseCreated, CaseStatus, PublicConfig
from .services.appeal_draft import UnknownGroundError, draft_appeal

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
async def create_case(file: UploadFile = File(...)) -> CaseCreated:
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

    return CaseCreated(
        case_id=case_id,
        status=CaseStatus.created,
        filename=file.filename or "document",
        size_bytes=len(payload),
        created_at=datetime.now(timezone.utc),
    )


@app.post("/api/cases/{case_id}/draft", response_model=AppealDraftResponse)
async def draft_case_appeal(case_id: str, body: AppealDraftRequest) -> AppealDraftResponse:
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

    return AppealDraftResponse(
        document_text=result.document_text,
        llm_used=result.llm_used,
        warnings=result.warnings,
    )
