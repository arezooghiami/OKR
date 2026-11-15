import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.models.audit import AuditEvent

GENESIS = "0" * 64


def compute_hash(prev_hash: str, at: datetime, actor_id: str | None, action: str, resource: str,
                 resource_id: str | None, before: Any, after: Any) -> str:
    payload = json.dumps(
        [prev_hash, at.isoformat(), actor_id, action, resource, resource_id, before, after],
        sort_keys=True, ensure_ascii=False, default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _plain(v: Any) -> Any:
    """JSON-safe copy (UUID, datetime -> str) so stored values equal what the hash covered."""
    return None if v is None else json.loads(json.dumps(v, default=str, ensure_ascii=False))


def record(db: Session, *, actor_id, action: str, resource: str, resource_id=None,
           before: Any = None, after: Any = None, ip: str | None = None) -> AuditEvent:
    before = _plain(before)
    after = _plain(after)
    # serialize writers so the chain has no forks; the lock is held until the transaction ends, so within one
    # transaction the chain head is ours and can be remembered (bulk work such as an import writes hundreds)
    tx = db.get_transaction()
    cached = db.info.get("audit_head")
    if cached and cached[0] is tx:
        prev = cached[1]
    else:
        db.execute(text("SELECT pg_advisory_xact_lock(727001)"))
        last = db.scalars(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1)).first()
        prev = last.hash if last else GENESIS
    at = utcnow()
    actor = str(actor_id) if actor_id else None
    rid = str(resource_id) if resource_id else None
    ev = AuditEvent(
        prev_hash=prev, at=at, actor_id=actor_id, action=action, resource=resource, resource_id=rid,
        before=before, after=after, ip=ip,
        hash=compute_hash(prev, at, actor, action, resource, rid, before, after),
    )
    db.add(ev)
    db.flush()
    db.info["audit_head"] = (tx, ev.hash)
    return ev


def verify_chain(db: Session) -> int | None:
    """Return the seq of the first broken row, or None when intact."""
    prev = GENESIS
    for ev in db.scalars(select(AuditEvent).order_by(AuditEvent.seq)):
        actor = str(ev.actor_id) if ev.actor_id else None
        if ev.prev_hash != prev or ev.hash != compute_hash(
            prev, ev.at, actor, ev.action, ev.resource, ev.resource_id, ev.before, ev.after
        ):
            return ev.seq
        prev = ev.hash
    return None
