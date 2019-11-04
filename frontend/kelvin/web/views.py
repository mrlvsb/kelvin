from django.shortcuts import render

from django.http import HttpResponse

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView


def index(request):
    return HttpResponse("Hello, world. You're at the kelvin index.")


@login_required()
def ll(request):
    return HttpResponse("In login.")

