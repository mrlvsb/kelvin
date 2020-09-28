import logging

from django.apps import AppConfig
from notifications.signals import notify
from webpush import send_user_notification
from pywebpush import WebPushException


def notification_to_webpush(sender, recipient, verb, action_object, **kwargs):
    from common.models import Comment
    def fmt(obj):
        if obj:
            if hasattr(obj, 'notification_str'):
                return obj.notification_str()
            return str(obj)
        return ""

    target = kwargs.get("target")
    msg = (f"{fmt(sender)} {verb} {fmt(action_object)} {fmt(target)}".strip())
    body = msg

    if isinstance(action_object, Comment):
        body = action_object.text

    url = None
    if hasattr(action_object, 'notification_url'):
        url = action_object.notification_url()

    for user in recipient:
        payload = {
            "head": msg,
            "body": body,
            "data": {},
        }

        if url:
            payload['data']['url'] = url

        try:
            send_user_notification(user=user, payload=payload)
        except WebPushException as e:
            logging.warn("%s failed for ", e, user)

class WebConfig(AppConfig):
    name = 'web'

    def ready(self):
        notify.connect(notification_to_webpush, dispatch_uid='notification_to_webpush')


