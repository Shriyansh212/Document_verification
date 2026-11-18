from datetime import datetime, timezone
import hashlib
import time

from sqlalchemy.orm import Session

from app.models.document import Document, ExtractedFields, VerificationOutcome
from app.schemas.document import ManualReviewRequest
from app.services.audit_service import record_audit_event
from app.services.decision_engine import route_decision
from app.services.llm_extractor import extract_structured_fields
from app.services.ocr_service import OCRProcessingError, OCRResult, extract_text_from_file
from app.services.validator import validate_extracted_document


def _run_core_stages(
    db: Session,
    doc: Document,
    ocr_result: OCRResult,
    start_time: float,
) -> Document:
    doc.raw_ocr_text = ocr_result.text
    doc.ocr_engine = ocr_result.engine
    doc.ocr_confidence = ocr_result.confidence
    db.flush()

    record_audit_event(
        db,
        document_id=doc.id,
        event_type="OCR_COMPLETED",
        stage="ocr",
        message=f"OCR extracted {len(ocr_result.text)} characters using {ocr_result.engine}.",
        metadata={
            "engine": ocr_result.engine,
            "confidence": ocr_result.confidence,
            "pages": ocr_result.pages,
            "char_count": len(ocr_result.text),
            "warnings": ocr_result.warnings,
        },
    )

    # Stage 2: Structured extraction (Groq Llama + fallback)
    extraction = extract_structured_fields(
        raw_text=ocr_result.text,
        doc_type_hint=doc.requested_doc_type,
    )
    fields = extraction.fields
    doc.extraction_engine = extraction.engine
    doc.detected_doc_type = fields.get("document_type", "unknown")

    extracted_row = ExtractedFields(
        document_id=doc.id,
        document_category=fields.get("document_category", "unknown"),
        document_type=fields.get("document_type", "unknown"),
        full_name=fields.get("full_name"),
        document_number=fields.get("document_number"),
        date_of_birth=fields.get("date_of_birth"),
        issue_date=fields.get("issue_date"),
        expiry_date=fields.get("expiry_date"),
        issuing_authority=fields.get("issuing_authority"),
        country=fields.get("country"),
        address=fields.get("address"),
        institution_name=fields.get("institution_name"),
        account_number=fields.get("account_number"),
        statement_period=fields.get("statement_period"),
        currency=fields.get("currency"),
        total_amount=fields.get("total_amount"),
        tax_id=fields.get("tax_id"),
        confidence_score=fields.get("confidence_score", 0.0),
        extraction_notes=fields.get("extraction_notes"),
        raw_json=fields.get("raw_json", {}),
    )
    db.add(extracted_row)
    db.flush()

    record_audit_event(
        db,
        document_id=doc.id,
        event_type="EXTRACTION_COMPLETED",
        stage="extraction",
        message=(
            f"Structured extraction identified '{extracted_row.document_type}' "
            f"via {extraction.engine} (confidence {extracted_row.confidence_score:.0%})."
        ),
        metadata={
            "engine": extraction.engine,
            "document_category": extracted_row.document_category,
            "document_type": extracted_row.document_type,
            "confidence_score": extracted_row.confidence_score,
        },
    )

    # Stage 3: Python validation rules
    flags = validate_extracted_document(
        fields=fields,
        raw_ocr_text=ocr_result.text,
        ocr_confidence=ocr_result.confidence,
        applicant_name=doc.applicant_name,
        applicant_dob=doc.applicant_dob,
        applicant_id_number=doc.applicant_id_number,
    )
    flags_serialized = [flag.model_dump() for flag in flags]

    record_audit_event(
        db,
        document_id=doc.id,
        event_type="VALIDATION_COMPLETED",
        stage="validation",
        message=f"Validation completed with {len(flags)} flag(s).",
        metadata={
            "total_flags": len(flags),
            "critical_count": sum(1 for f in flags if f.severity == "CRITICAL"),
            "warning_count": sum(1 for f in flags if f.severity == "WARNING"),
            "rule_codes": [f.rule_code for f in flags],
        },
    )

    # Stage 4: Decision workflow routing (PASS / FAIL / MANUAL_REVIEW)
    decision_result = route_decision(
        flags=flags,
        extraction_confidence=extracted_row.confidence_score,
        ocr_confidence=ocr_result.confidence,
    )

    outcome = VerificationOutcome(
        document_id=doc.id,
        initial_decision=decision_result.decision,
        final_decision=decision_result.decision,
        risk_score=decision_result.risk_score,
        confidence_score=decision_result.confidence_score,
        validation_flags=flags_serialized,
        summary_reason=decision_result.summary_reason,
    )
    db.add(outcome)

    doc.status = decision_result.decision
    doc.processing_time_ms = int((time.perf_counter() - start_time) * 1000)
    db.flush()

    record_audit_event(
        db,
        document_id=doc.id,
        event_type="DECISION_ROUTED",
        stage="decision",
        message=decision_result.summary_reason,
        metadata={
            "decision": decision_result.decision,
            "risk_score": decision_result.risk_score,
            "confidence_score": decision_result.confidence_score,
            "processing_time_ms": doc.processing_time_ms,
        },
    )

    db.commit()
    db.refresh(doc)
    return doc


def process_uploaded_document(
    db: Session,
    *,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    requested_doc_type: str = "auto",
    applicant_name: str | None = None,
    applicant_dob: str | None = None,
    applicant_id_number: str | None = None,
) -> Document:
    start_time = time.perf_counter()
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    doc = Document(
        filename=filename,
        content_type=content_type or "application/octet-stream",
        file_size=len(file_bytes),
        file_hash=file_hash,
        requested_doc_type=requested_doc_type or "auto",
        applicant_name=applicant_name.strip() if applicant_name else None,
        applicant_dob=applicant_dob.strip() if applicant_dob else None,
        applicant_id_number=applicant_id_number.strip() if applicant_id_number else None,
        status="PROCESSING",
    )
    db.add(doc)
    db.flush()

    record_audit_event(
        db,
        document_id=doc.id,
        event_type="DOCUMENT_UPLOADED",
        stage="ingestion",
        message=f"Received '{filename}' ({len(file_bytes)} bytes) for verification.",
        metadata={
            "filename": filename,
            "content_type": doc.content_type,
            "file_hash": file_hash[:16],
            "requested_doc_type": doc.requested_doc_type,
        },
    )

    try:
        ocr_result = extract_text_from_file(file_bytes, filename, doc.content_type)
    except OCRProcessingError as exc:
        doc.status = "ERROR"
        doc.processing_time_ms = int((time.perf_counter() - start_time) * 1000)
        record_audit_event(
            db,
            document_id=doc.id,
            event_type="PIPELINE_ERROR",
            stage="ocr",
            message=str(exc),
            metadata={"error_type": "OCRProcessingError"},
        )
        db.commit()
        raise

    return _run_core_stages(db, doc, ocr_result, start_time)


def process_raw_text_document(
    db: Session,
    *,
    raw_text: str,
    filename: str = "raw_document.txt",
    requested_doc_type: str = "auto",
    applicant_name: str | None = None,
    applicant_dob: str | None = None,
    applicant_id_number: str | None = None,
    ocr_engine: str = "direct_text_input",
    ocr_confidence: float = 0.98,
) -> Document:
    start_time = time.perf_counter()
    encoded = raw_text.encode("utf-8")
    file_hash = hashlib.sha256(encoded).hexdigest()

    doc = Document(
        filename=filename,
        content_type="text/plain",
        file_size=len(encoded),
        file_hash=file_hash,
        requested_doc_type=requested_doc_type or "auto",
        applicant_name=applicant_name.strip() if applicant_name else None,
        applicant_dob=applicant_dob.strip() if applicant_dob else None,
        applicant_id_number=applicant_id_number.strip() if applicant_id_number else None,
        status="PROCESSING",
    )
    db.add(doc)
    db.flush()

    record_audit_event(
        db,
        document_id=doc.id,
        event_type="DOCUMENT_UPLOADED",
        stage="ingestion",
        message=f"Ingested text payload '{filename}' ({len(encoded)} bytes) for verification.",
        metadata={
            "filename": filename,
            "requested_doc_type": doc.requested_doc_type,
        },
    )

    ocr_result = OCRResult(
        text=raw_text.strip(),
        engine=ocr_engine,
        confidence=ocr_confidence,
        pages=1,
    )
    return _run_core_stages(db, doc, ocr_result, start_time)


def submit_manual_review(
    db: Session,
    *,
    doc: Document,
    payload: ManualReviewRequest,
) -> Document:
    if not doc.outcome:
        raise ValueError("Document has no verification outcome to review.")

    previous_decision = doc.outcome.final_decision
    doc.outcome.final_decision = payload.decision
    doc.outcome.reviewed_by = payload.reviewer_name.strip()
    doc.outcome.review_notes = payload.notes.strip()
    doc.outcome.reviewed_at = datetime.now(timezone.utc)
    doc.status = payload.decision

    record_audit_event(
        db,
        document_id=doc.id,
        event_type="MANUAL_REVIEW_SUBMITTED",
        stage="review",
        actor=payload.reviewer_name.strip(),
        message=(
            f"Analyst {payload.reviewer_name.strip()} changed decision from "
            f"{previous_decision} to {payload.decision}."
        ),
        metadata={
            "previous_decision": previous_decision,
            "new_decision": payload.decision,
            "notes": payload.notes.strip(),
        },
    )

    db.commit()
    db.refresh(doc)
    return doc
