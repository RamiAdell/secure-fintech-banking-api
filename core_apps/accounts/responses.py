from rest_framework.response import Response
from rest_framework import status


def already_verified_response():
    return Response(
        {"message": "This Account has already been verified and fully activated"},
        status=status.HTTP_400_BAD_REQUEST,
    )


def kyc_not_submitted_response():
    return Response(
        {"error": "KYC must be submitted before it can be verified."},
        status=status.HTTP_400_BAD_REQUEST,
    )


def verification_success_response(data):
    return Response(
        {
            "message": "Account Verification status updated successfully",
            "data": data,
        },
        status=status.HTTP_200_OK,
    )


def invalid_account_number_response():
    return Response(
        {"error": "Account number is required."},
        status=status.HTTP_400_BAD_REQUEST,
    )


def account_found_response(data):
    return Response(
        {
            "message": "Account found",
            "data": data,
        },
        status=status.HTTP_200_OK,
    )


def account_not_found_response():
    return Response(
        {"error": "Account not found."},
        status=status.HTTP_404_NOT_FOUND,
    )


def account_not_active_response():
    return Response(
        {"error": "Account is not active."},
        status=status.HTTP_400_BAD_REQUEST,
    )


def deposit_success_response(account_number, new_balance):
    return Response(
        {
            "message": "Deposit successful",
            "data": {
                "account_number": account_number,
                "new_balance": str(new_balance),
            },
        },
        status=status.HTTP_200_OK,
    )


def deposit_failed_response():
    return Response(
        {"error": "Failed to process deposit."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
