# core/middleware.py
from django.conf import settings
from rest_framework.authentication import CSRFCheck

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


class JWTAuthCookieMiddleware:
    def __init__(self, get_response): self.get_response = get_response

    def __call__(self, request):
        used_cookie = False
        if "HTTP_AUTHORIZATION" not in request.META:
            token = request.COOKIES.get(
                getattr(settings, "JWT_ACCESS_COOKIE", "access_token"))
            if token:
                request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
                used_cookie = True
        if used_cookie and request.method in UNSAFE:
            def dummy(_): return None
            check = CSRFCheck(dummy)
            check.process_request(request)
            reason = check.process_view(request, None, (), {})
            if reason:
                from django.http import JsonResponse
                return JsonResponse({"detail": f"CSRF Failed: {reason}"}, status=403)
        return self.get_response(request)
