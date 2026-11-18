from datetime import date

from PIL import Image

from app.services.decision_engine import route_decision
from app.services.ocr_service import _preprocess_image
from app.services.validator import validate_extracted_document


def test_valid_passport_passes():
    fields = {
        "document_category": "identity",
        "document_type": "passport",
        "full_name": "Aarav Mehta",
        "document_number": "Z8492014",
        "date_of_birth": "1994-06-18",
        "issue_date": "2022-04-12",
        "expiry_date": "2032-04-11",
        "country": "India",
        "confidence_score": 0.94,
    }
    flags = validate_extracted_document(
        fields=fields,
        raw_ocr_text="REPUBLIC OF INDIA PASSPORT Z8492014 Aarav Mehta DOB 1994-06-18",
        ocr_confidence=0.95,
        applicant_name="Aarav Mehta",
        applicant_dob="1994-06-18",
        applicant_id_number="Z8492014",
        reference_date=date(2026, 11, 18),
    )
    assert flags == []
    decision = route_decision(flags, extraction_confidence=0.94, ocr_confidence=0.95)
    assert decision.decision == "PASS"
    assert decision.risk_score == 0


def test_expired_document_fails():
    fields = {
        "document_category": "identity",
        "document_type": "drivers_license",
        "full_name": "Rohan Verma",
        "document_number": "DL042016009821",
        "date_of_birth": "1991-11-05",
        "issue_date": "2018-05-10",
        "expiry_date": "2023-05-10",
        "issuing_authority": "State Transport Authority",
        "address": "Noida",
        "confidence_score": 0.91,
    }
    flags = validate_extracted_document(
        fields=fields,
        raw_ocr_text="DRIVER LICENSE DL042016009821 Rohan Verma Expiry 2023-05-10",
        ocr_confidence=0.92,
        reference_date=date(2026, 11, 18),
    )
    codes = {f.rule_code for f in flags}
    assert "DOCUMENT_EXPIRED" in codes
    decision = route_decision(flags, extraction_confidence=0.91, ocr_confidence=0.92)
    assert decision.decision == "FAIL"


def test_minor_name_discrepancy_routes_to_manual_review():
    fields = {
        "document_category": "financial",
        "document_type": "bank_statement",
        "full_name": "Priya Sharma",
        "institution_name": "Horizon National Bank",
        "account_number": "****7821",
        "statement_period": "2026-09-01 to 2026-09-30",
        "currency": "USD",
        "total_amount": 18450.75,
        "confidence_score": 0.90,
    }
    flags = validate_extracted_document(
        fields=fields,
        raw_ocr_text="MONTHLY BANK STATEMENT Horizon National Bank Priya Sharma 18450.75",
        ocr_confidence=0.91,
        applicant_name="Priya Kumari Sharma",
        reference_date=date(2026, 11, 18),
    )
    codes = {f.rule_code for f in flags}
    assert "APPLICANT_NAME_DISCREPANCY" in codes
    decision = route_decision(flags, extraction_confidence=0.90, ocr_confidence=0.91)
    assert decision.decision == "MANUAL_REVIEW"


def test_missing_required_fields_trigger_fail():
    fields = {
        "document_category": "identity",
        "document_type": "passport",
        "full_name": "Test User",
        "confidence_score": 0.85,
    }
    flags = validate_extracted_document(
        fields=fields,
        raw_ocr_text="PASSPORT document text with missing number and dates for Test User",
        ocr_confidence=0.90,
        reference_date=date(2026, 11, 18),
    )
    missing_fields = {f.field for f in flags if f.rule_code == "MISSING_REQUIRED_FIELD"}
    assert {"document_number", "date_of_birth", "expiry_date"}.issubset(missing_fields)
    decision = route_decision(flags, extraction_confidence=0.85, ocr_confidence=0.90)
    assert decision.decision == "FAIL"


def test_preprocess_image_caps_dimensions_for_low_memory():
    large = Image.new("RGB", (3200, 1800), color="white")
    resized_large = _preprocess_image(large)
    assert max(resized_large.size) <= 1600

    wide_crop = Image.new("RGB", (1400, 350), color="white")
    resized_crop = _preprocess_image(wide_crop)
    assert max(resized_crop.size) <= 1600

