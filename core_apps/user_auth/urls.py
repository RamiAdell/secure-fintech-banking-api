from django.urls import path

from .views import (
    CustomTokenCreateView,
    CustomTokenRefreshView,
    LogoutAPIView,
    OTPVerifyView,
)


urlpatterns = [
    path("login/", CustomTokenCreateView.as_view(), name="login"),
    path("verify-otp/", OTPVerifyView.as_view(), name="verify_otp"),
    path("refresh/", CustomTokenRefreshView.as_view(), name="refresh"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
]