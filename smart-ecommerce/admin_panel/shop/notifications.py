"""Create an in-app notification, send an email, and push it to the FastAPI WebSocket hub."""
import json
import logging
import urllib.request

from django.conf import settings
from django.core.mail import send_mail

from .models import Notification

log = logging.getLogger(__name__)


def push_to_api(user_id, notification):
    """Best-effort real-time push via the FastAPI internal endpoint."""
    body = json.dumps(
        {
            "user_id": user_id,
            "notification": {
                "id": notification.id,
                "type": notification.type,
                "message": notification.message,
                "is_read": notification.is_read,
                "created_at": notification.created_at.isoformat(),
            },
        }
    ).encode()
    req = urllib.request.Request(
        settings.FASTAPI_INTERNAL_URL.rstrip("/") + "/api/internal/notify",
        data=body,
        headers={"Content-Type": "application/json", "X-Internal-Secret": settings.INTERNAL_SECRET},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=2).close()
    except Exception as exc:  # the API may be down; the notification is already stored
        log.warning("Realtime push failed: %s", exc)


def notify_user(user, ntype, message, subject=None):
    notification = Notification.objects.create(user=user, type=ntype, message=message)
    send_mail(subject or "Update from Smart Shop", message, None, [user.email], fail_silently=True)
    push_to_api(user.id, notification)
    return notification
