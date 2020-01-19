from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist


class TokenBackend(ModelBackend):
    def authenticate(self, request, token=None):
        if token:
            try:
                return get_user_model().objects.get(usertoken__token=token)
            except ObjectDoesNotExist:
                pass
        return None
