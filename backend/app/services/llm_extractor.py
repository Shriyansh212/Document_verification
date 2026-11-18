from dataclasses import dataclass
from datetime import datetime
import json
import logging
import re
from typing import Any

from groq import Groq

from app.core.config import get_settings

logger = logging.getLogger(__name__)

IDENTITY_DOC_TYPES = {"passport", "national_id", "drivers_license"}
FINANCIAL_DOC_TYPES = {"bank_statement", "tax_document", "utility_bill", "pay_stub", "invoice"}

SYSTEM_PROMPT = """You are a strict KYC and financial document extraction engine.
Given raw OCR text from a financial or identity document, extract structured fields into a single JSON object.
Return ONLY valid JSON with these exact keys (use null when a field is not present):
{
  "document_category": "identity" | "financial" | "unknown",
  "document_type": "passport" | "national_id" | "drivers_license" | "bank_statement" | "tax_document" | "utility_bill" | "pay_stub" | "invoice" | "unknown",
  "full_name": string | null,
  "document_number": string | null,
  "date_of_birth": "YYYY-MM-DD" | null,
  "issue_date": "YYYY-MM-DD" | null,
  "expiry_date": "YYYY-MM-DD" | null,
  "issuing_authority": string | null,
  "country": string | null,
  "address": string | null,
  "institution_name": string | null,
  "account_number": string | null,
  "statement_period": string | null,
  "currency": string | null,
  "total_amount": number | null,
  "tax_id": string | null,
  "confidence_score": number (between 0.0 and 1.0),
  "extraction_notes": string
}
Normalize all dates to YYYY-MM-DD when possible. Never invent values not supported by the OCR text."""


@dataclass
class ExtractionResult:
    fields: dict[str, Any]
    engine: str


def is_groq_configured() -> bool:
    key = (get_settings().groq_api_key or "").strip()
    return bool(key) and key != "your_groq_api_key_here"


def _normalize_date_str(value: str | None) -> str | None:
    if not value:
        return None
    raw = str(value).strip()
    for fmt in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%B %d, %Y",
    ):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _normalize_payload(payload: dict[str, Any], doc_type_hint: str) -> dict[str, Any]:
    doc_type = (payload.get("document_type") or "").strip().lower()
    if (not doc_type or doc_type == "unknown") and doc_type_hint and doc_type_hint != "auto":
        doc_type = doc_type_hint.lower()
    if not doc_type:
        doc_type = "unknown"

    category = (payload.get("document_category") or "").strip().lower()
    if category not in ("identity", "financial"):
        if doc_type in IDENTITY_DOC_TYPES:
            category = "identity"
        elif doc_type in FINANCIAL_DOC_TYPES:
            category = "financial"
        else:
            category = "unknown"

    conf = _parse_float(payload.get("confidence_score"))
    confidence_score = max(0.0, min(1.0, conf if conf is not None else 0.5))

    return {
        "document_category": category,
        "document_type": doc_type,
        "full_name": _clean_str(payload.get("full_name")),
        "document_number": _clean_str(payload.get("document_number")),
        "date_of_birth": _normalize_date_str(payload.get("date_of_birth")),
        "issue_date": _normalize_date_str(payload.get("issue_date")),
        "expiry_date": _normalize_date_str(payload.get("expiry_date")),
        "issuing_authority": _clean_str(payload.get("issuing_authority")),
        "country": _clean_str(payload.get("country")),
        "address": _clean_str(payload.get("address")),
        "institution_name": _clean_str(payload.get("institution_name")),
        "account_number": _clean_str(payload.get("account_number")),
        "statement_period": _clean_str(payload.get("statement_period")),
        "currency": _clean_str(payload.get("currency")),
        "total_amount": _parse_float(payload.get("total_amount")),
        "tax_id": _clean_str(payload.get("tax_id")),
        "confidence_score": round(confidence_score, 4),
        "extraction_notes": _clean_str(payload.get("extraction_notes")) or "",
        "raw_json": payload,
    }


def _clean_str(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s.lower() not in ("null", "none", "n/a") else None


def _detect_doc_type_heuristic(text: str, hint: str) -> str:
    if hint and hint != "auto":
        return hint.lower()
    lower = text.lower()
    if "passport" in lower:
        return "passport"
    if "driver" in lower and ("license" in lower or "licence" in lower):
        return "drivers_license"
    if any(k in lower for k in ("national id", "aadhaar", "pan card", "identity card", "permanent account")):
        return "national_id"
    if any(k in lower for k in ("bank statement", "account summary", "closing balance", "statement period")):
        return "bank_statement"
    if any(k in lower for k in ("form w-2", "w-2", "income tax", "tax return", "form 16", "tax id", "tin")):
        return "tax_document"
    if any(k in lower for k in ("utility bill", "electricity bill", "water bill", "amount due")):
        return "utility_bill"
    if any(k in lower for k in ("pay stub", "payslip", "net pay", "gross pay")):
        return "pay_stub"
    if "invoice" in lower:
        return "invoice"
    return "unknown"


def _match_first(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return None


def heuristic_fallback_extract(raw_text: str, doc_type_hint: str = "auto") -> dict[str, Any]:
    """Deterministic pattern extractor used when GROQ_API_KEY is not configured or unavailable."""
    doc_type = _detect_doc_type_heuristic(raw_text, doc_type_hint)

    full_name = _match_first(
        raw_text,
        [
            r"(?:full\s*name|account\s*holder|employee\s*name|taxpayer\s*name|holder\s*name|name)\s*[:\-]\s*([^\n\r]+)",
        ],
    )
    document_number = _match_first(
        raw_text,
        [
            r"(?:passport\s*(?:no|number)|license\s*(?:no|number)|id\s*(?:no|number)|document\s*(?:no|number)|pan)\s*[:\-#]\s*([A-Z0-9\-/]{4,32})",
        ],
    )
    date_of_birth = _match_first(
        raw_text,
        [
            r"(?:date\s*of\s*birth|dob|birth\s*date)\s*[:\-]\s*([^\n\r]+)",
        ],
    )
    issue_date = _match_first(
        raw_text,
        [
            r"(?:date\s*of\s*issue|issue\s*date|issued\s*on|statement\s*date)\s*[:\-]\s*([^\n\r]+)",
        ],
    )
    expiry_date = _match_first(
        raw_text,
        [
            r"(?:date\s*of\s*expiry|expiry\s*date|expiration\s*date|valid\s*until|expires)\s*[:\-]\s*([^\n\r]+)",
        ],
    )
    issuing_authority = _match_first(
        raw_text,
        [
            r"(?:issuing\s*authority|issued\s*by|authority)\s*[:\-]\s*([^\n\r]+)",
        ],
    )
    country = _match_first(
        raw_text,
        [
            r"(?:country|nationality|country\s*code)\s*[:\-]\s*([^\n\r]+)",
        ],
    )
    address = _match_first(
        raw_text,
        [
            r"(?:address|residential\s*address)\s*[:\-]\s*([^\n\r]+)",
        ],
    )
    institution_name = _match_first(
        raw_text,
        [
            r"(?:bank\s*name|institution|financial\s*institution|employer\s*name|provider)\s*[:\-]\s*([^\n\r]+)",
        ],
    )
    account_number = _match_first(
        raw_text,
        [
            r"(?:account\s*(?:no|number)|acct\s*(?:no|#))\s*[:\-]\s*([A-Z0-9\-\*]{4,32})",
        ],
    )
    statement_period = _match_first(
        raw_text,
        [
            r"(?:statement\s*period|billing\s*period|tax\s*year|period)\s*[:\-]\s*([^\n\r]+)",
        ],
    )
    tax_id = _match_first(
        raw_text,
        [
            r"(?:tax\s*id|tin|ssn|ein|pan\s*number)\s*[:\-]\s*([A-Z0-9\-]{5,24})",
        ],
    )
    amount_match = re.search(
        r"(?:closing\s*balance|ending\s*balance|total\s*wages|total\s*income|gross\s*income|amount\s*due|total\s*amount)\s*[:\-]\s*([A-Z$€£₹]{0,4})\s*([0-9,]+(?:\.[0-9]{1,2})?)",
        raw_text,
        re.IGNORECASE,
    )
    currency = None
    total_amount = None
    if amount_match:
        sym = amount_match.group(1).strip()
        currency_map = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}
        currency = currency_map.get(sym, sym or None)
        total_amount = _parse_float(amount_match.group(2))

    if not currency:
        currency = _match_first(raw_text, [r"(?:currency)\s*[:\-]\s*([A-Z]{3})"])

    populated = sum(
        1
        for v in (
            full_name,
            document_number,
            date_of_birth,
            issue_date,
            expiry_date,
            institution_name,
            account_number,
            total_amount,
            tax_id,
        )
        if v is not None
    )
    confidence = min(0.92, 0.35 + populated * 0.11) if raw_text.strip() else 0.0

    raw_payload = {
        "document_type": doc_type,
        "full_name": full_name,
        "document_number": document_number,
        "date_of_birth": date_of_birth,
        "issue_date": issue_date,
        "expiry_date": expiry_date,
        "issuing_authority": issuing_authority,
        "country": country,
        "address": address,
        "institution_name": institution_name,
        "account_number": account_number,
        "statement_period": statement_period,
        "currency": currency,
        "total_amount": total_amount,
        "tax_id": tax_id,
        "confidence_score": round(confidence, 4),
        "extraction_notes": "Extracted with local deterministic fallback (configure GROQ_API_KEY for Groq Llama).",
    }
    return _normalize_payload(raw_payload, doc_type_hint)


def extract_structured_fields(raw_text: str, doc_type_hint: str = "auto") -> ExtractionResult:
    """Extract structured identity/financial fields using Groq Llama with graceful fallback."""
    if not raw_text or not raw_text.strip():
        empty = _normalize_payload(
            {
                "document_type": doc_type_hint if doc_type_hint != "auto" else "unknown",
                "confidence_score": 0.0,
                "extraction_notes": "No OCR text available for extraction.",
            },
            doc_type_hint,
        )
        return ExtractionResult(fields=empty, engine="none")

    settings = get_settings()
    if is_groq_configured():
        try:
            client = Groq(api_key=settings.groq_api_key)
            user_prompt = (
                f"Document type hint: {doc_type_hint}\n\n"
                f"OCR TEXT:\n\"\"\"\n{raw_text[:12000]}\n\"\"\""
            )
            completion = client.chat.completions.create(
                model=settings.groq_model,
                temperature=0.0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = completion.choices[0].message.content or "{}"
            parsed = json.loads(content)
            normalized = _normalize_payload(parsed, doc_type_hint)
            return ExtractionResult(fields=normalized, engine=f"groq:{settings.groq_model}")
        except Exception as exc:
            logger.warning("Groq Llama extraction failed, falling back to heuristic extractor: %s", exc)
            fallback = heuristic_fallback_extract(raw_text, doc_type_hint)
            fallback["extraction_notes"] = f"Groq API error ({type(exc).__name__}); used fallback extractor."
            return ExtractionResult(fields=fallback, engine="fallback_heuristic")

    fallback = heuristic_fallback_extract(raw_text, doc_type_hint)
    return ExtractionResult(fields=fallback, engine="fallback_heuristic")
