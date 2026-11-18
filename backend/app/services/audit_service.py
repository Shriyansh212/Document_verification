from typing import Any

from sqlalchemy.orm import Session

from app.models.document import AuditLog


def record_audit_event(
    db: Session,
    *,
    document_id: str,
    event_type: str,
    stage: str,
    message: str,
    actor: str = "system",
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        document_id=document_id,
        event_type=event_type,
        stage=stage,
        actor=actor,
        message=message,
        metadata_json=metadata or {},
    )
    db.add(entry)
    db.flush()
    return entry
