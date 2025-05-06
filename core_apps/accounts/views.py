import random
from typing import Any

from django.utils import timezone
from rest_framework import generics, status, serializers
from rest_framework.request import Request
from rest_framework.response import Response
from core_apps.common.permissions import IsAccountExecutive, IsTeller
from core_apps.common.renderers import GenericJSONRenderer
from .emails import (
    send_full_activation_email,
    send_deposit_email
)
from django.db import transaction
from loguru import logger
from .models import BankAccount, Transaction
from decimal import Decimal
from .serializers import (
    AccountVerificationSerializer,
    DepositSerializer,
    CustomerInfoSerializer,
)
from .responses import (
    already_verified_response,
    kyc_not_submitted_response,
    verification_success_response,
    invalid_account_number_response,
    account_found_response,
    account_not_found_response,
    account_not_active_response,
    deposit_success_response,
    deposit_failed_response,
)


class AccountVerificationView(generics.UpdateAPIView):
    queryset = BankAccount.objects.all()
    serializer_class = AccountVerificationSerializer
    renderer_classes = [GenericJSONRenderer]
    object_label = "verification"
    permission_classes = [IsAccountExecutive]

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()

        if instance.kyc_verified and instance.fully_activated:
            return already_verified_response()

        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        if serializer.is_valid(raise_exception=True):
            kyc_submitted = serializer.validated_data.get(
                "kyc_submitted", instance.kyc_submitted
            )

            kyc_verified = serializer.validated_data.get(
                "kyc_verified", instance.kyc_verified
            )

            if kyc_verified and not kyc_submitted:
                return kyc_not_submitted_response()

            instance.kyc_submitted = kyc_submitted
            instance.save()

            if kyc_submitted and kyc_verified:
                instance.kyc_verified = kyc_verified
                instance.verified_by = request.user
                instance.verification_date = serializer.validated_data.get(
                    "verification_date", timezone.now()
                )
                instance.verification_notes = serializer.validated_data.get(
                    "verification_notes", ""
                )
                instance.fully_activated = True
                instance.account_status = BankAccount.AccountStatus.ACTIVE
                instance.save()

                send_full_activation_email(instance)

            return verification_success_response(self.get_serializer(instance).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DepositView(generics.CreateAPIView):
    serializer_class = DepositSerializer
    renderer_classes = [GenericJSONRenderer]
    object_label = "deposit"
    permission_classes = [IsTeller]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        account_number = request.query_params.get("account_number")
        if not account_number:
            return invalid_account_number_response()
        try:
            account = BankAccount.objects.get(account_number=account_number)
            serializer = CustomerInfoSerializer(account)
            return account_found_response(serializer.data)
        except BankAccount.DoesNotExist:
            return account_not_found_response()

    @transaction.atomic
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = serializer.context["account"]
        amount = serializer.validated_data["amount"]

        try:
            if account.account_status != BankAccount.AccountStatus.ACTIVE:
                return account_not_active_response()

            account.account_balance += amount
            account.full_clean()
            account.save()
            logger.info(
                f"Deposit of {amount} to account {account.account_number} by {request.user.username}"
            )

            send_deposit_email(
                user=request.user,
                user_email=account.user.email,
                amount=amount,
                currency=account.currency,
                new_balance=account.account_balance,
                account_number=account.account_number,
            )
            return deposit_success_response(account.account_number, account.account_balance)
        except Exception as e:
            logger.error(
                f"Failed to deposit {amount} to account {account.account_number}: {str(e)}"
            )
            return deposit_failed_response()
