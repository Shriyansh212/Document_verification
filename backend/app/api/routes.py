from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.session import get_db
from app.models.document import AuditLog, Document
from app.schemas.document import (
    AuditLogSchema,
    DocumentDetailSchema,
    DocumentSummarySchema,
    ManualReviewRequest,
    PipelineStatsSchema,
    SampleScenarioSchema,
    TextVerifyRequest,
)
from app.services.llm_extractor import is_groq_configured
from app.services.ocr_service import OCRProcessingError, is_tesseract_available
from app.services.pipeline import (
    process_raw_text_document,
    process_uploaded_document,
    submit_manual_review,
)
from app.services.samples import SAMPLE_SCENARIOS

router = APIRouter(prefix="/api/v1", tags=["Verification Pipeline"])

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tiff", ".tif", ".bmp", ".pdf", ".txt"}


@router.get("/health")
def health_check():
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "groq_configured": is_groq_configured(),
        "groq_model": settings.groq_model,
        "tesseract_available": is_tesseract_available(),
    }


@router.get("/stats", response_model=PipelineStatsSchema)
def get_pipeline_stats(db: Session = Depends(get_db)):
    settings = get_settings()
    total = db.scalar(select(func.count(Document.id))) or 0
    passed = db.scalar(select(func.count(Document.id)).where(Document.status == "PASS")) or 0
    failed = db.scalar(select(func.count(Document.id)).where(Document.status == "FAIL")) or 0
    manual_review = (
        db.scalar(select(func.count(Document.id)).where(Document.status == "MANUAL_REVIEW")) or 0
    )
    avg_time = db.scalar(select(func.avg(Document.processing_time_ms))) or 0.0
    pass_rate = round((passed / total) * 100, 1) if total > 0 else 0.0

    return PipelineStatsSchema(
        total_documents=total,
        passed=passed,
        failed=failed,
        manual_review=manual_review,
        pass_rate=pass_rate,
        avg_processing_time_ms=round(float(avg_time), 1),
        groq_configured=is_groq_configured(),
        tesseract_available=is_tesseract_available(),
        groq_model=settings.groq_model,
    )


@router.post(
    "/documents/verify",
    response_model=DocumentDetailSchema,
    status_code=status.HTTP_201_CREATED,
)
async def verify_uploaded_document(
    file: UploadFile = File(...),
    doc_type: str = Form(default="auto"),
    applicant_name: str | None = Form(default=None),
    applicant_dob: str | None = Form(default=None),
    applicant_id_number: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    filename = file.filename or "uploaded_document"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")
    if len(file_bytes) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_file_size_mb} MB.",
        )

    try:
        doc = process_uploaded_document(
            db,
            file_bytes=file_bytes,
            filename=filename,
            content_type=file.content_type or "application/octet-stream",
            requested_doc_type=doc_type,
            applicant_name=applicant_name,
            applicant_dob=applicant_dob,
            applicant_id_number=applicant_id_number,
        )
    except OCRProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return _load_document_detail(db, doc.id)


@router.post(
    "/documents/verify-text",
    response_model=DocumentDetailSchema,
    status_code=status.HTTP_201_CREATED,
)
def verify_text_document(
    payload: TextVerifyRequest,
    db: Session = Depends(get_db),
):
    doc = process_raw_text_document(
        db,
        raw_text=payload.raw_text,
        filename=payload.filename,
        requested_doc_type=payload.doc_type,
        applicant_name=payload.applicant_name,
        applicant_dob=payload.applicant_dob,
        applicant_id_number=payload.applicant_id_number,
    )
    return _load_document_detail(db, doc.id)


@router.get("/documents", response_model=list[DocumentSummarySchema])
def list_documents(
    status_filter: str | None = Query(default=None, alias="status"),
    doc_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Document)
        .options(selectinload(Document.outcome))
        .order_by(desc(Document.created_at))
    )
    if status_filter and status_filter.upper() != "ALL":
        stmt = stmt.where(Document.status == status_filter.upper())
    if doc_type and doc_type.lower() != "all":
        stmt = stmt.where(Document.detected_doc_type == doc_type.lower())
    if search:
        like_term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Document.filename.ilike(like_term),
                Document.applicant_name.ilike(like_term),
                Document.detected_doc_type.ilike(like_term),
                Document.id.ilike(like_term),
            )
        )

    rows = db.scalars(stmt.offset(offset).limit(limit)).all()
    return rows


@router.get("/documents/{document_id}", response_model=DocumentDetailSchema)
def get_document(document_id: str, db: Session = Depends(get_db)):
    return _load_document_detail(db, document_id)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    db.delete(doc)
    db.commit()


@router.post("/documents/{document_id}/review", response_model=DocumentDetailSchema)
def review_document(
    document_id: str,
    payload: ManualReviewRequest,
    db: Session = Depends(get_db),
):
    doc = db.scalar(
        select(Document)
        .options(selectinload(Document.outcome))
        .where(Document.id == document_id)
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if not doc.outcome:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document does not have a verification outcome yet.",
        )

    submit_manual_review(db, doc=doc, payload=payload)
    return _load_document_detail(db, doc.id)


@router.get("/audit-logs", response_model=list[AuditLogSchema])
def list_audit_logs(
    document_id: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(AuditLog).order_by(desc(AuditLog.created_at), desc(AuditLog.id))
    if document_id:
        stmt = stmt.where(AuditLog.document_id == document_id)
    if stage and stage.lower() != "all":
        stmt = stmt.where(AuditLog.stage == stage.lower())
    if event_type and event_type.upper() != "ALL":
        stmt = stmt.where(AuditLog.event_type == event_type.upper())
    return db.scalars(stmt.limit(limit)).all()


@router.get("/samples", response_model=list[SampleScenarioSchema])
def list_sample_scenarios():
    return [
        SampleScenarioSchema(
            id=s.id,
            title=s.title,
            doc_type=s.doc_type,
            category=s.category,
            expected_outcome=s.expected_outcome,
            description=s.description,
            applicant_name=s.applicant_name,
            applicant_dob=s.applicant_dob,
            applicant_id_number=s.applicant_id_number,
        )
        for s in SAMPLE_SCENARIOS.values()
    ]


@router.post(
    "/samples/{sample_id}/run",
    response_model=DocumentDetailSchema,
    status_code=status.HTTP_201_CREATED,
)
def run_sample_scenario(sample_id: str, db: Session = Depends(get_db)):
    scenario = SAMPLE_SCENARIOS.get(sample_id)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sample scenario not found.")

    doc = process_raw_text_document(
        db,
        raw_text=scenario.raw_text,
        filename=scenario.filename,
        requested_doc_type=scenario.doc_type,
        applicant_name=scenario.applicant_name,
        applicant_dob=scenario.applicant_dob,
        applicant_id_number=scenario.applicant_id_number,
        ocr_engine="tesseract_ocr_sample",
        ocr_confidence=scenario.ocr_confidence,
    )
    return _load_document_detail(db, doc.id)


def _load_document_detail(db: Session, document_id: str) -> Document:
    doc = db.scalar(
        select(Document)
        .options(
            selectinload(Document.extracted_fields),
            selectinload(Document.outcome),
            selectinload(Document.audit_logs),
        )
        .where(Document.id == document_id)
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return doc
