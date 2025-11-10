# core/middleware.py
from django.conf import settings
from rest_framework.authentication import CSRFCheck

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


AUTH_ALLOWLIST = (
    "/api/login/",
    "/api/token/refresh/",
    "/api/register/",
    "/login/",
    "/api/createQuiz/",
    "/api/createQuiz",
    "/token/refresh/",
    "/register/",
    "/api/quizzes/",
    "/api/quizzes",
)


def _is_auth_allowlisted(path: str) -> bool:
    return any(path == p or path.startswith(p) for p in AUTH_ALLOWLIST)


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
        if used_cookie and request.method in UNSAFE and not _is_auth_allowlisted(request.path):
            def dummy(_): return None
            check = CSRFCheck(dummy)
            check.process_request(request)
            reason = check.process_view(request, None, (), {})
            if reason:
                from django.http import JsonResponse
                return JsonResponse({"detail": f"CSRF Failed: {reason}"}, status=403)

        return self.get_response(request)
