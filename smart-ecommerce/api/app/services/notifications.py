from sqlalchemy.orm import Session

from ..models import Notification, User
from ..realtime import manager
from .email import send_email


def serialize(n: Notification) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "message": n.message,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


def notify(db: Session, user_id: int, ntype: str, message: str, email_subject: str | None = None) -> Notification:
    """Store an in-app notification, push it over WebSocket and (optionally) email it.
    NOTE: commits the session, so call it after your other changes."""
    note = Notification(user_id=user_id, type=ntype, message=message)
    db.add(note)
    db.commit()
    manager.push(user_id, {"event": "notification", "notification": serialize(note)})
    if email_subject:
        user = db.get(User, user_id)
        if user:
            send_email(user.email, email_subject, message)
    return note
