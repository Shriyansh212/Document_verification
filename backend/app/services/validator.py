from datetime import date, datetime
from difflib import SequenceMatcher
import re
from typing import Any

from app.schemas.document import ValidationFlag


REQUIRED_FIELDS_BY_TYPE: dict[str, dict[str, list[str]]] = {
    "passport": {
        "critical": ["full_name", "document_number", "date_of_birth", "expiry_date"],
        "warning": ["country", "issue_date"],
    },
    "drivers_license": {
        "critical": ["full_name", "document_number", "date_of_birth", "expiry_date"],
        "warning": ["issuing_authority", "address"],
    },
    "national_id": {
        "critical": ["full_name", "document_number", "date_of_birth"],
        "warning": ["country", "issuing_authority"],
    },
    "bank_statement": {
        "critical": ["full_name", "institution_name", "account_number"],
        "warning": ["statement_period", "total_amount", "currency"],
    },
    "tax_document": {
        "critical": ["full_name", "tax_id"],
        "warning": ["statement_period", "total_amount", "institution_name"],
    },
    "utility_bill": {
        "critical": ["full_name", "address"],
        "warning": ["institution_name", "total_amount", "issue_date"],
    },
    "pay_stub": {
        "critical": ["full_name", "institution_name", "total_amount"],
        "warning": ["statement_period", "currency"],
    },
    "invoice": {
        "critical": ["institution_name", "total_amount"],
        "warning": ["document_number", "issue_date", "currency"],
    },
}


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _normalize_id(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-zA-Z\s]", "", value)).strip().lower()


def validate_extracted_document(
    fields: dict[str, Any],
    raw_ocr_text: str,
    ocr_confidence: float | None = None,
    applicant_name: str | None = None,
    applicant_dob: str | None = None,
    applicant_id_number: str | None = None,
    reference_date: date | None = None,
) -> list[ValidationFlag]:
    """Run modular Python validation rules to detect missing fields, inconsistencies, and discrepancies."""
    flags: list[ValidationFlag] = []
    today = reference_date or date.today()

    # 1. OCR quality & readability checks
    clean_text = (raw_ocr_text or "").strip()
    if len(clean_text) < 25:
        flags.append(
            ValidationFlag(
                rule_code="OCR_TEXT_TOO_SHORT",
                severity="CRITICAL",
                field="raw_ocr_text",
                message="Extracted OCR text is too short or unreadable to verify document contents.",
            )
        )
    elif ocr_confidence is not None and ocr_confidence < 0.55:
        flags.append(
            ValidationFlag(
                rule_code="LOW_OCR_CONFIDENCE",
                severity="WARNING",
                field="ocr_confidence",
                message=f"OCR confidence ({ocr_confidence:.0%}) is below recommended threshold (55%).",
            )
        )

    # 2. Document type classification & required field completeness
    doc_type = (fields.get("document_type") or "unknown").lower()
    if doc_type == "unknown":
        flags.append(
            ValidationFlag(
                rule_code="UNKNOWN_DOCUMENT_TYPE",
                severity="WARNING",
                field="document_type",
                message="Document type could not be confidently classified; manual verification recommended.",
            )
        )
    else:
        spec = REQUIRED_FIELDS_BY_TYPE.get(doc_type, {"critical": ["full_name"], "warning": []})
        for req_field in spec["critical"]:
            if fields.get(req_field) in (None, ""):
                flags.append(
                    ValidationFlag(
                        rule_code="MISSING_REQUIRED_FIELD",
                        severity="CRITICAL",
                        field=req_field,
                        message=f"Mandatory field '{req_field}' is missing for {doc_type.replace('_', ' ')}.",
                    )
                )
        for warn_field in spec["warning"]:
            if fields.get(warn_field) in (None, ""):
                flags.append(
                    ValidationFlag(
                        rule_code="MISSING_SECONDARY_FIELD",
                        severity="WARNING",
                        field=warn_field,
                        message=f"Expected supporting field '{warn_field}' was not found in the document.",
                    )
                )

    # 3. Date format & chronological consistency checks
    dob_str = fields.get("date_of_birth")
    issue_str = fields.get("issue_date")
    expiry_str = fields.get("expiry_date")

    dob = _parse_iso_date(dob_str)
    issue_dt = _parse_iso_date(issue_str)
    expiry_dt = _parse_iso_date(expiry_str)

    if dob_str and dob is None:
        flags.append(
            ValidationFlag(
                rule_code="INVALID_DATE_FORMAT",
                severity="WARNING",
                field="date_of_birth",
                message=f"Date of birth '{dob_str}' could not be normalized to ISO YYYY-MM-DD.",
            )
        )
    if issue_str and issue_dt is None:
        flags.append(
            ValidationFlag(
                rule_code="INVALID_DATE_FORMAT",
                severity="WARNING",
                field="issue_date",
                message=f"Issue date '{issue_str}' could not be normalized to ISO YYYY-MM-DD.",
            )
        )
    if expiry_str and expiry_dt is None:
        flags.append(
            ValidationFlag(
                rule_code="INVALID_DATE_FORMAT",
                severity="WARNING",
                field="expiry_date",
                message=f"Expiry date '{expiry_str}' could not be normalized to ISO YYYY-MM-DD.",
            )
        )

    if dob is not None:
        if dob > today:
            flags.append(
                ValidationFlag(
                    rule_code="FUTURE_DATE_OF_BIRTH",
                    severity="CRITICAL",
                    field="date_of_birth",
                    message=f"Date of birth ({dob.isoformat()}) is in the future.",
                )
            )
        else:
            age_years = (today - dob).days / 365.25
            if age_years < 14 or age_years > 120:
                flags.append(
                    ValidationFlag(
                        rule_code="IMPLAUSIBLE_AGE",
                        severity="WARNING",
                        field="date_of_birth",
                        message=f"Derived holder age ({age_years:.1f} yrs) is outside expected KYC range (14-120).",
                    )
                )

    if issue_dt is not None:
        if issue_dt > today:
            flags.append(
                ValidationFlag(
                    rule_code="FUTURE_ISSUE_DATE",
                    severity="CRITICAL",
                    field="issue_date",
                    message=f"Document issue date ({issue_dt.isoformat()}) is in the future.",
                )
            )
        if dob is not None and issue_dt < dob:
            flags.append(
                ValidationFlag(
                    rule_code="ISSUE_BEFORE_DOB",
                    severity="CRITICAL",
                    field="issue_date",
                    message="Document issue date precedes the holder's date of birth.",
                )
            )

    if expiry_dt is not None:
        if issue_dt is not None and expiry_dt <= issue_dt:
            flags.append(
                ValidationFlag(
                    rule_code="EXPIRY_BEFORE_ISSUE",
                    severity="CRITICAL",
                    field="expiry_date",
                    message="Document expiry date is earlier than or equal to the issue date.",
                )
            )
        if expiry_dt < today:
            flags.append(
                ValidationFlag(
                    rule_code="DOCUMENT_EXPIRED",
                    severity="CRITICAL",
                    field="expiry_date",
                    message=f"Document expired on {expiry_dt.isoformat()}.",
                )
            )
        elif (expiry_dt - today).days <= 30:
            flags.append(
                ValidationFlag(
                    rule_code="DOCUMENT_EXPIRING_SOON",
                    severity="WARNING",
                    field="expiry_date",
                    message=f"Document expires within 30 days ({expiry_dt.isoformat()}).",
                )
            )

    # 4. Identifier & financial amount format checks
    doc_num = fields.get("document_number")
    if doc_num is not None:
        normalized_num = _normalize_id(str(doc_num))
        if len(normalized_num) < 5:
            flags.append(
                ValidationFlag(
                    rule_code="INVALID_DOCUMENT_NUMBER",
                    severity="CRITICAL",
                    field="document_number",
                    message=f"Document number '{doc_num}' is shorter than minimum valid identifier length.",
                )
            )

    total_amount = fields.get("total_amount")
    if total_amount is not None and total_amount < 0:
        flags.append(
            ValidationFlag(
                rule_code="NEGATIVE_FINANCIAL_AMOUNT",
                severity="WARNING",
                field="total_amount",
                message=f"Extracted financial amount ({total_amount}) is negative; review recommended.",
            )
        )

    # 5. Applicant cross-check discrepancy rules
    if applicant_name and fields.get("full_name"):
        expected = _normalize_name(applicant_name)
        extracted = _normalize_name(str(fields["full_name"]))
        ratio = SequenceMatcher(None, expected, extracted).ratio()
        if ratio < 0.72:
            flags.append(
                ValidationFlag(
                    rule_code="APPLICANT_NAME_MISMATCH",
                    severity="CRITICAL",
                    field="full_name",
                    message=(
                        f"Extracted name '{fields['full_name']}' does not match submitted applicant "
                        f"name '{applicant_name}' (similarity {ratio:.0%})."
                    ),
                )
            )
        elif ratio < 0.92:
            flags.append(
                ValidationFlag(
                    rule_code="APPLICANT_NAME_DISCREPANCY",
                    severity="WARNING",
                    field="full_name",
                    message=(
                        f"Minor discrepancy between extracted name '{fields['full_name']}' and "
                        f"applicant name '{applicant_name}' (similarity {ratio:.0%})."
                    ),
                )
            )

    if applicant_dob and fields.get("date_of_birth"):
        if applicant_dob.strip() != str(fields["date_of_birth"]).strip():
            flags.append(
                ValidationFlag(
                    rule_code="APPLICANT_DOB_MISMATCH",
                    severity="CRITICAL",
                    field="date_of_birth",
                    message=(
                        f"Extracted DOB '{fields['date_of_birth']}' conflicts with submitted "
                        f"applicant DOB '{applicant_dob}'."
                    ),
                )
            )

    if applicant_id_number:
        extracted_id = fields.get("document_number") or fields.get("tax_id") or fields.get("account_number")
        if extracted_id:
            if _normalize_id(applicant_id_number) != _normalize_id(str(extracted_id)):
                flags.append(
                    ValidationFlag(
                        rule_code="APPLICANT_ID_MISMATCH",
                        severity="CRITICAL",
                        field="document_number",
                        message=(
                            f"Extracted identifier '{extracted_id}' does not match submitted ID "
                            f"'{applicant_id_number}'."
                        ),
                    )
                )

    # 6. LLM extraction confidence check
    llm_conf = float(fields.get("confidence_score") or 0.0)
    if llm_conf < 0.50:
        flags.append(
            ValidationFlag(
                rule_code="VERY_LOW_EXTRACTION_CONFIDENCE",
                severity="CRITICAL",
                field="confidence_score",
                message=f"Structured extraction confidence ({llm_conf:.0%}) is critically low.",
            )
        )
    elif llm_conf < 0.75:
        flags.append(
            ValidationFlag(
                rule_code="MODERATE_EXTRACTION_CONFIDENCE",
                severity="WARNING",
                field="confidence_score",
                message=f"Structured extraction confidence ({llm_conf:.0%}) requires analyst review.",
            )
        )

    return flags
