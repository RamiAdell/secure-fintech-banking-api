from typing import Any, Optional
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from djoser.views import TokenCreateView
from djoser.views import User
from loguru import logger
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from .cookie_manager import set_auth_cookies
from .emails import send_otp_email
from .utils.responses import *
from .utils.auth_helper import generate_otp


User = get_user_model()


class CustomTokenCreateView(TokenCreateView): # creation activation account view
    def _action(self, serializer): # Think of _action() as the “what to do if login is successful” handler.
        user = serializer.user
        if user.is_locked_out:
            return locked_out_response()
        
        user.reset_failed_login_attempts()

        otp = generate_otp()
        user.set_otp(otp)
        send_otp_email(user.email, otp)

        logger.info(f"OTP sent for login to user: {user.email}")

        return otp_sent_response(user.email)

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            email = request.data.get("email")
            user = User.objects.filter(email=email).first()
            if user:
                if not user.is_active:
                    return account_inactive_response()

                user.handle_failed_login_attempts()
                failed_attempts = user.failed_login_attempts
                logger.error(
                    f"Failed login attempts: {failed_attempts}  for user: {email}"
                )

                if failed_attempts >= settings.LOGIN_ATTEMPTS:
                    return exceeded_login_attempts_response()
            else:
                logger.error(f"Failed login attempt for non-existent user: {email}")

            return invalid_credentials_response()

        return self._action(serializer)


class CustomTokenRefreshView(TokenRefreshView):
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        refresh_token = request.COOKIES.get("refresh")

        if refresh_token:
            request.data["refresh"] = refresh_token

        refresh_res = super().post(request, *args, **kwargs)

        if refresh_res.status_code == status.HTTP_200_OK:
            access_token = refresh_res.data.get("access")
            refresh_token = refresh_res.data.get("refresh")

            if access_token and refresh_token:
                set_auth_cookies(
                    refresh_res,
                    access_token=access_token,
                    refresh_token=refresh_token,
                )

                refresh_res.data.pop("access", None)
                refresh_res.data.pop("refresh", None)

                refresh_res.data["message"] = "Access tokens refreshed successfully."

            else:
                refresh_res.data["message"] = ("Access or refresh token not found in refresh response data")
                logger.error("Access or refresh token not found in refresh response data")

        return refresh_res


class OTPVerifyView(APIView): ## Login OTP verification view 2FA
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        otp = request.data.get("otp")

        if not otp:
            return otp_missing_response()

        user = User.objects.filter(otp=otp, otp_expiry_time__gt=timezone.now()).first()

        if not user:
            return otp_invalid_response()

        if user.is_locked_out:
            return locked_out_response()

        user.verify_otp(otp)

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        response = otp_successful_login_response()
        set_auth_cookies(response, access_token, refresh_token)
        logger.info(f"Successful login with OTP: {user.email}")
        return response


class LogoutAPIView(APIView):
    def post(self, request, *args, **kwargs):
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie("access")
        response.delete_cookie("refresh")
        response.delete_cookie("logged_in")
        return response