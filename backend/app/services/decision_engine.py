from dataclasses import dataclass

from app.schemas.document import DecisionType, ValidationFlag


@dataclass
class DecisionResult:
    decision: DecisionType
    risk_score: int
    confidence_score: float
    summary_reason: str


def route_decision(
    flags: list[ValidationFlag],
    extraction_confidence: float,
    ocr_confidence: float | None = None,
) -> DecisionResult:
    """Compute risk score and route document to PASS, FAIL, or MANUAL_REVIEW."""
    critical_flags = [f for f in flags if f.severity == "CRITICAL"]
    warning_flags = [f for f in flags if f.severity == "WARNING"]
    info_flags = [f for f in flags if f.severity == "INFO"]

    combined_confidence = extraction_confidence
    if ocr_confidence is not None:
        combined_confidence = round((extraction_confidence * 0.65) + (ocr_confidence * 0.35), 4)
    else:
        combined_confidence = round(extraction_confidence, 4)

    risk_score = (
        len(critical_flags) * 35
        + len(warning_flags) * 15
        + len(info_flags) * 3
    )
    if combined_confidence < 0.80:
        risk_score += int((0.80 - combined_confidence) * 40)
    risk_score = max(0, min(100, risk_score))

    if critical_flags or risk_score >= 60:
        decision: DecisionType = "FAIL"
        codes = ", ".join(f.rule_code for f in critical_flags[:3]) or "HIGH_RISK_SCORE"
        summary = (
            f"Automatic FAIL triggered by {len(critical_flags)} critical violation(s) "
            f"[{codes}] with risk score {risk_score}/100."
        )
    elif warning_flags or risk_score >= 20 or combined_confidence < 0.78:
        decision = "MANUAL_REVIEW"
        codes = ", ".join(f.rule_code for f in warning_flags[:3]) or "CONFIDENCE_THRESHOLD"
        summary = (
            f"Routed to MANUAL REVIEW due to {len(warning_flags)} warning flag(s) "
            f"[{codes}] (risk score {risk_score}/100, confidence {combined_confidence:.0%})."
        )
    else:
        decision = "PASS"
        summary = (
            f"Document PASSED all automated OCR, extraction, and validation checks "
            f"(risk score {risk_score}/100, confidence {combined_confidence:.0%})."
        )

    return DecisionResult(
        decision=decision,
        risk_score=risk_score,
        confidence_score=combined_confidence,
        summary_reason=summary,
    )
