from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.forms.models import model_to_dict
from django.core.exceptions import SuspiciousOperation
from django.views.decorators.csrf import csrf_exempt
from common.models import Comment
from django.core.cache import caches

CACHE_KEY = "notification:{}"

cache = caches["default"]


@login_required
@csrf_exempt
def mark_as_read(request, notification_id=None):
    if request.method == "POST":
        notifications = request.user.notifications.unread()

        if notification_id:
            notifications = notifications.filter(pk=notification_id)
        else:
            notifications = notifications.filter(public=True)

        for notification in notifications:
            notification.mark_as_read()
            cache.delete(CACHE_KEY.format(notification.id))
    else:
        raise SuspiciousOperation()
    return all_notifications(request)


@login_required
def all_notifications(request):
    all_list = []

    def to_json(notification):
        key = CACHE_KEY.format(notification.id)
        result = cache.get(key)
        if result:
            return result
        struct = model_to_dict(notification)
        if struct.get("data"):
            struct = {**struct, **struct["data"]}
            del struct["data"]

        for obj_type in ["actor", "target", "action_object"]:
            obj = getattr(notification, obj_type)
            if obj:
                if hasattr(obj, "notification_str"):
                    struct[obj_type] = obj.notification_str()
                else:
                    struct[obj_type] = str(obj)
                if hasattr(obj, "notification_url"):
                    struct[f"{obj_type}_url"] = obj.notification_url()

        if isinstance(notification.action_object, Comment):
            comment = notification.action_object
            struct["description"] = comment.text
            if comment.source and comment.line > 0:
                struct["action_object_url"] += f";{comment.source}:{comment.line}"

        cache.set(key, struct, timeout=60 * 60 * 24)
        return struct

    for notification in request.user.notifications.filter(unread=True):
        all_list.append(to_json(notification))

    data = {"notifications": all_list}
    return JsonResponse(data)
