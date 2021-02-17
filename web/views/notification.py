from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.http import JsonResponse
from django.forms.models import model_to_dict
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import SuspiciousOperation
from django.views.decorators.csrf import csrf_exempt


@login_required
@csrf_exempt
def mark_as_read(request, notification_id=None):
    if request.method == 'POST':
        notifications = request.user.notifications.unread()

        if notification_id:
            notifications = notifications.filter(pk=notification_id)
        else:
            notifications = notifications.filter(public=True)

        for notification in notifications:
            notification.mark_as_read()
    else:
        raise SuspiciousOperation()
    return all_notifications(request)

@login_required
def all_notifications(request):
    all_list = []

    num_to_fetch = 50
    read_count = 0
    unread = request.user.notifications.filter(unread=True).count()
    unread_found = 0

    def to_json(notification):
        struct = model_to_dict(notification)
        if struct.get('data'):
            struct = {**struct, **struct['data']}
            del struct['data']

        for obj_type in ['actor', 'target', 'action_object']:
            obj = getattr(notification, obj_type)
            if obj:
                if hasattr(obj, 'notification_str'):
                    struct[obj_type] = obj.notification_str()
                else:
                    struct[obj_type] = str(obj)
                if hasattr(obj, 'notification_url'):
                    struct[f"{obj_type}_url"] = obj.notification_url()

        return struct
        

    for notification in request.user.notifications.all()[0:num_to_fetch]:
        all_list.append(to_json(notification))      

        if not notification.unread:
            if unread_found == unread:
                read_count += 1
                if read_count >= 5:
                    break
        else:
            unread_found += 1

    if unread_found < unread:
        args = {}
        if all_list:
            args['id__lt'] = all_list[-1]['id']

        for notification in request.user.notifications.filter(unread=True, **args):
            all_list.append(to_json(notification))


    data = {
        'unread_count': unread,
        'notifications': all_list
    }
    return JsonResponse(data)
