from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import authenticate
from django.http import HttpResponse


class TokenAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not hasattr(request, "user") or request.user.is_anonymous:
            header = request.META.get("HTTP_AUTHORIZATION", "")
            if header.startswith("Bearer"):
                _, token = header.split(' ', 2)
                user = authenticate(request=request, token=token)
                if not user:
                    return HttpResponse('<h1>Unauthorized</h1>', status=401)
                request.user = request._cached_user = user

