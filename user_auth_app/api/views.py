from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.middleware.csrf import get_token
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.exceptions import ValidationError as DRFValidationError, AuthenticationFailed
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import RegistrationSerializer


User = get_user_model()


def set_jwt_cookies(response, access_token: str, refresh_token: str):
    """
    Sets httpOnly cookies for access and refresh tokens.
    Uses the cookie names defined in settings:
    - settings.JWT_ACCESS_COOKIE
    - settings.JWT_REFRESH_COOKIE
    """
    secure = getattr(settings, "CSRF_COOKIE_SECURE",
                     False)
    samesite = "Lax"

    response.set_cookie(
        getattr(settings, "JWT_ACCESS_COOKIE", "access_token"),
        access_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/",
        max_age=15 * 60,
    )
    response.set_cookie(
        getattr(settings, "JWT_REFRESH_COOKIE", "refresh_token"),
        refresh_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/",
        max_age=7 * 24 * 60 * 60,
    )
    return response


def clear_jwt_cookies(response):
    """ 
    Deletes the JWT cookies
    """
    response.delete_cookie(
        getattr(settings, "JWT_ACCESS_COOKIE", "access_token"), path="/")
    response.delete_cookie(
        getattr(settings, "JWT_REFRESH_COOKIE", "refresh_token"), path="/")
    return response


class RegistrationView(APIView):
    """
    POST /api/register/
    Registers a new user with username, email, password, and confirmed_password.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'detail': 'Invalid data', 'errors': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST,)
        try:
            serializer.save()
        except Exception:
            return Response({'detail': 'Internal Server Errror'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR,)
        return Response({'detail': 'User created successfully'}, status=status.HTTP_201_CREATED,)


@method_decorator(ensure_csrf_cookie, name='get')
@method_decorator(csrf_exempt, name='post')
class LoginView(TokenObtainPairView):
    """
    POST /api/login/
    Description: Authenticates a user and returns JWT tokens in HttpOnly cookies.
    Expected request data: {"username": "<username>", "password": "<password>"}
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        get_token(request)
        return Response({'detail': 'CSRF cookie set'}, status=200)

    def post(self, request, *args, **kwargs):
        try:
            sjwt_response = super().post(request, *args, **kwargs)
        except (DRFValidationError, AuthenticationFailed, InvalidToken, TokenError):
            return Response(
                {"detail": "incorrect login Data."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception:
            return Response(
                {"detail": "Internal server error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if sjwt_response.status_code != status.HTTP_200_OK:
            return Response(
                {"detail": "incorrect login data."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        access = sjwt_response.data.get("access")
        refresh = sjwt_response.data.get("refresh")
        username = request.data.get("username")
        user = User.objects.filter(username=username).first()
        user_info = {
            "id": user.id if user else None,
            "username": user.username if user else username,
            "email": user.email if user else None,
        }

        final_response = Response(
            {
                "detail": "Login successfully!",
                "user": user_info,
            },
            status=status.HTTP_200_OK,
        )
        return set_jwt_cookies(final_response, access, refresh)


class LogoutView(APIView):
    """
    POST /api/logout/
    Description: Logs out the user by deleting JWT cookies.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            resp = Response(
                {
                    "detail": "Log-Out successfully! All Tokens will be deleted. Refresh token is now invalid."
                },
                status=status.HTTP_200_OK,
            )

            access_cookie = getattr(
                settings, "JWT_ACCESS_COOKIE", "access_token")
            refresh_cookie = getattr(
                settings, "JWT_REFRESH_COOKIE", "refresh_token")

            cookie_kwargs = {
                "path": "/",
                "domain": getattr(settings, "SESSION_COOKIE_DOMAIN", None),
                "secure": getattr(settings, "SESSION_COOKIE_SECURE", False),
                "samesite": getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax"),
            }
            resp.delete_cookie(access_cookie, **cookie_kwargs)
            resp.delete_cookie(refresh_cookie, **cookie_kwargs)
            csrf_token = get_token(request)
            resp.set_cookie(
                getattr(settings, "CSRF_COOKIE_NAME", "csrftoken"),
                csrf_token,
                max_age=None,
                path="/",
                domain=getattr(settings, "CSRF_COOKIE_DOMAIN", None),
                secure=getattr(settings, "CSRF_COOKIE_SECURE", False),
                httponly=False,
                samesite=getattr(settings, "CSRF_COOKIE_SAMESITE", "Lax"),
            )

            return resp

        except Exception:
            return Response(
                {"detail": "Internal Server Error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@method_decorator(csrf_exempt, name='post')
class RefreshView(TokenRefreshView):
    """
    POST /api/token/refresh/
    Description: refreshes the access-token with the refresh-token (from HttpOnly-Cookie).
    Response (200):
    {
      "detail": "Token refreshed",
      "access": "<new_access_token>"
    }
    Status: 200 / 401 / 500
    """
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        try:
            if "refresh" not in request.data:
                refresh_cookie_name = getattr(
                    settings, "JWT_REFRESH_COOKIE", "refresh_token")
                token_from_cookie = request.COOKIES.get(refresh_cookie_name)
                if not token_from_cookie:
                    return Response({"detail": "Refresh Token invalid or missing."},
                                    status=status.HTTP_401_UNAUTHORIZED)
                data = request.data.copy()
                data["refresh"] = token_from_cookie
                request._full_data = data
            res = super().post(request, *args, **kwargs)
        except (InvalidToken, TokenError):
            return Response({"detail": "Refresh Token invalid or missing."},
                            status=status.HTTP_401_UNAUTHORIZED)
        except Exception:
            return Response({"detail": "internal server error."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if res.status_code != status.HTTP_200_OK:
            return Response({"detail": "Refresh Token ungültig oder fehlt."},
                            status=status.HTTP_401_UNAUTHORIZED)
        new_access = res.data.get("access")
        rotated_refresh = res.data.get("refresh")
        response = Response(
            {"detail": "Token refreshed", "access": new_access},
            status=status.HTTP_200_OK,
        )
        secure = getattr(settings, "CSRF_COOKIE_SECURE", False)
        samesite = "Lax"
        response.set_cookie(
            getattr(settings, "JWT_ACCESS_COOKIE", "access_token"),
            new_access,
            httponly=True,
            secure=secure,
            samesite=samesite,
            path="/",
            max_age=15 * 60,
        )

        return response
