from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


DecisionType = Literal["PASS", "FAIL", "MANUAL_REVIEW"]
SeverityType = Literal["CRITICAL", "WARNING", "INFO"]


class ValidationFlag(BaseModel):
    rule_code: str
    severity: SeverityType
    field: str | None = None
    message: str


class ExtractedFieldsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_category: str = "unknown"
    document_type: str = "unknown"
    full_name: str | None = None
    document_number: str | None = None
    date_of_birth: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None
    issuing_authority: str | None = None
    country: str | None = None
    address: str | None = None

    institution_name: str | None = None
    account_number: str | None = None
    statement_period: str | None = None
    currency: str | None = None
    total_amount: float | None = None
    tax_id: str | None = None

    confidence_score: float = 0.0
    extraction_notes: str | None = None
    raw_json: dict[str, Any] = Field(default_factory=dict)


class VerificationOutcomeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    initial_decision: DecisionType
    final_decision: DecisionType
    risk_score: int
    confidence_score: float
    validation_flags: list[ValidationFlag] = Field(default_factory=list)
    summary_reason: str
    reviewed_by: str | None = None
    review_notes: str | None = None
    reviewed_at: datetime | None = None


class AuditLogSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: str
    event_type: str
    stage: str
    actor: str
    message: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class DocumentSummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    content_type: str
    file_size: int
    requested_doc_type: str
    detected_doc_type: str | None = None
    applicant_name: str | None = None
    status: str
    ocr_engine: str | None = None
    extraction_engine: str | None = None
    processing_time_ms: int | None = None
    created_at: datetime
    updated_at: datetime
    outcome: VerificationOutcomeSchema | None = None


class DocumentDetailSchema(DocumentSummarySchema):
    file_hash: str
    applicant_dob: str | None = None
    applicant_id_number: str | None = None
    raw_ocr_text: str | None = None
    ocr_confidence: float | None = None
    extracted_fields: ExtractedFieldsSchema | None = None
    audit_logs: list[AuditLogSchema] = Field(default_factory=list)


class ManualReviewRequest(BaseModel):
    decision: Literal["PASS", "FAIL"]
    reviewer_name: str = Field(..., min_length=2, max_length=128)
    notes: str = Field(..., min_length=3, max_length=2000)


class TextVerifyRequest(BaseModel):
    filename: str = Field(default="raw_document.txt", max_length=255)
    raw_text: str = Field(..., min_length=5)
    doc_type: str = Field(default="auto")
    applicant_name: str | None = None
    applicant_dob: str | None = None
    applicant_id_number: str | None = None


class PipelineStatsSchema(BaseModel):
    total_documents: int
    passed: int
    failed: int
    manual_review: int
    pass_rate: float
    avg_processing_time_ms: float
    groq_configured: bool
    tesseract_available: bool
    groq_model: str


class SampleScenarioSchema(BaseModel):
    id: str
    title: str
    doc_type: str
    category: str
    expected_outcome: DecisionType
    description: str
    applicant_name: str | None = None
    applicant_dob: str | None = None
    applicant_id_number: str | None = None
