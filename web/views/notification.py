from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.http import JsonResponse
from django.forms.models import model_to_dict
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import SuspiciousOperation

@login_required
def mark_as_read(request, notification_id=None):
    if request.method == 'POST':
        notifications = request.user.notifications.unread()

        if notification_id:
            notifications = notifications.filter(pk=notification_id)

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

    for notification in request.user.notifications.all()[0:num_to_fetch]:
        struct = model_to_dict(notification)
        if notification.actor:
            struct['actor'] = str(notification.actor)
            if ContentType.objects.get_for_model(User).id == struct['actor_content_type']:
                struct['actor_full_name'] = notification.actor.get_full_name()
        if notification.target:
            struct['target'] = str(notification.target)
        if notification.action_object:
            struct['action_object'] = str(notification.action_object)
            if hasattr(notification.action_object, 'notification_url'):
                struct['action_url'] = notification.action_object.notification_url()
    
        if notification.data:
            struct = {**struct, **notification.data}

        all_list.append(struct)

        if not struct['unread']:
            read_count += 1
            if read_count >= 5:
                break
    data = {
        'unread_count': request.user.notifications.filter(unread=True).count(),
        'notifications': all_list
    }
    return JsonResponse(data)
