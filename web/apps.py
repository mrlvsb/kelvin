from django.apps import AppConfig


class WebConfig(AppConfig):
    name = "web"

    def ready(self):
        import web.signals

        from notifications.signals import notify
        from notifications.models import notify_handler

        # Disconnect the default handler
        notify.disconnect(notify_handler, dispatch_uid="notifications.models.notification")

        # Connect our custom wrapper
        notify.connect(
            web.signals.custom_notify_handler, dispatch_uid="kelvin.notifications.notify_handler"
        )
