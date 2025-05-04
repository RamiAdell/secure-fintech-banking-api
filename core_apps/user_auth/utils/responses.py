# utils/responses.py

from rest_framework import status
from rest_framework.response import Response
from django.conf import settings

def locked_out_response():
    return Response(
        {
            "error": f"Account is locked due to multiple failed login attempts. Please "
            f"try again after {settings.LOCKOUT_DURATION.total_seconds() / 60} minutes.",
        },
        status=status.HTTP_403_FORBIDDEN,
    )

def account_inactive_response():
    return Response(
        {
            "error": "Please check your email and activate your account",
        },
        status=status.HTTP_403_FORBIDDEN,
    )

def exceeded_login_attempts_response():
    return Response(
        {
            "error": f"You have exceeded the maximum number of login attempts. "
            f"Your account has been locked for {settings.LOCKOUT_DURATION.total_seconds() / 60} minutes. "
            f"An email has been sent to you with further instructions.",
        },
        status=status.HTTP_403_FORBIDDEN,
    )

def invalid_credentials_response():
    return Response(
        {"error": "Your Login Credentials are not correct"},
        status=status.HTTP_400_BAD_REQUEST,
    )

def otp_missing_response():
    return Response(
        {"error": "OTP is required"},
        status=status.HTTP_400_BAD_REQUEST,
    )

def otp_invalid_response():
    return Response(
        {"error": "Invalid or expired OTP"},
        status=status.HTTP_400_BAD_REQUEST,
    )

def otp_successful_login_response():
    return Response(
        {
            "success": "Login successful. Now add your profile information, "
            "so that we can create an account for you"
        },
        status=status.HTTP_200_OK,
    )

def otp_sent_response(user_email):
    return Response(
        {
            "success": "OTP sent to your email",
            "email": user_email,
        },
        status=status.HTTP_200_OK,
    )
