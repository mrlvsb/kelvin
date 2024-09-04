from django.dispatch import receiver
import django.db.models.signals
from notifications.models import Notification
from webpush import send_user_notification
from pywebpush import WebPushException
from common.models import Comment
import logging


@receiver(django.db.models.signals.post_save, sender=Notification)
def send_webpush_notification(sender, instance, created, **kwargs):
    if not created:
        return

    notification = instance

    def fmt(obj):
        if obj:
            if hasattr(obj, "notification_str"):
                return obj.notification_str()
            return str(obj)
        return ""

    msg = f"{fmt(notification.actor)} {notification.verb} {fmt(notification.action_object)} {fmt(notification.target)}".strip()
    body = msg

    if isinstance(notification.action_object, Comment):
        body = notification.action_object.text

    url = None
    if hasattr(notification.action_object, "notification_url"):
        url = notification.action_object.notification_url()

    payload = {
        "head": msg,
        "body": body,
        "data": {
            "notification_id": notification.id,
        },
    }

    if url:
        payload["data"]["url"] = url

    try:
        send_user_notification(user=notification.recipient, payload=payload)
    except WebPushException as e:
        logging.warn("%s failed for %s", e, notification.recipient)
