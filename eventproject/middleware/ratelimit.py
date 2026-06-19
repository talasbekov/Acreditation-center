from django.http import HttpResponse
from django_ratelimit.exceptions import Ratelimited


class RatelimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Ratelimited:
            return HttpResponse(
                "Too many requests. Please try again later.",
                status=429,
            )
