from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
import django.db.models.signals
from notifications.models import Notification
from webpush import send_user_notification
from pywebpush import WebPushException
from common.models import Comment
from ipware import get_client_ip
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
        logging.warning("%s failed for %s", e, notification.recipient)


@receiver(user_logged_in, sender=User)
def login_success(sender, request, user, **kwargs):
    logger = logging.getLogger("user_logins")

    client_ip, is_routable = get_client_ip(request)
    if client_ip is None:
        logger.info(f"No IP address for user: {user}.")
    else:
        if is_routable:
            logger.info(f"IP address for user: {user} is {client_ip}.")
        else:
            # The client's IP address is private
            pass
