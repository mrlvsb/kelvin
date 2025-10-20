"""kelvin URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/dev/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings

# import notifications.urls

if settings.CAS_ENABLE:
    from django_cas_ng import views as auth_views
else:
    from django.contrib.auth import views as auth_views

urlpatterns = [
    path("", include("web.urls")),
    path("admin/", admin.site.urls),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="cas_ng_logout"),
    path("accounts/login/", auth_views.LoginView.as_view(), name="cas_ng_login"),
    path("api/", include("api.urls")),
    path("django-rq/", include("django_rq.urls")),
    path("survey/", include("survey.urls")),
    path("webpush/", include("webpush.urls")),
    # For django-tasks-scheduler
    path("scheduler/", include("scheduler.urls")),
]

if settings.DEBUG:
    from django.contrib.auth import login as login_fn
    from django.contrib.auth.models import User
    from django.shortcuts import redirect

    def su(request, login):
        login_fn(
            request,
            User.objects.get(username=login.upper()),
            backend="django.contrib.auth.backends.ModelBackend",
        )
        return redirect("/")

    urlpatterns.append(path("su/<str:login>", su))

    try:
        from debug_toolbar.toolbar import debug_toolbar_urls

        urlpatterns += debug_toolbar_urls()
    except ImportError:
        pass
