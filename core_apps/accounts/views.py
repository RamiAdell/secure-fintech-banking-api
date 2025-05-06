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
    send_deposit_email,
    send_transfer_email,
    send_withdrawal_email,
    send_transfer_otp_email
)
from django.db import transaction
from loguru import logger
from .models import BankAccount, Transaction
from decimal import Decimal
from .serializers import (
    AccountVerificationSerializer,
    DepositSerializer,
    CustomerInfoSerializer,
    TransactionSerializer,
    UsernameVerificationSerializer,
    SecurityQuestionSerializer,
    OTPVerificationSerializer
)
from .utils.account_helper import generate_otp
from .pagination import StandardResultsSetPagination
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
from .tasks import generate_transaction_pdf
from dateutil import parser
from django.db.models import Q
from rest_framework.filters import OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView

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

class InitiateWithdrawalView(generics.CreateAPIView):
    serializer_class = TransactionSerializer
    renderer_classes = [GenericJSONRenderer]
    object_label = "initiate_withdrawal"

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        account_number = request.data.get("account_number")
        amount = request.data.get("amount")

        if not account_number:
            return Response(
                {"error": "Account number is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            account = BankAccount.objects.get(
                account_number=account_number, user=request.user
            )

            if not (account.fully_activated and account.kyc_verified):
                return Response(
                    {
                        "error": "Your account is not fully verified. Please complete the "
                        "verification process"
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        except BankAccount.DoesNotExist:
            return Response(
                {"error": "You are not authorized to withdraw from this account"},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(
            data={
                "amount": amount,
                "description": f"Withdrawal from account {account_number}",
                "transaction_type": Transaction.TransactionType.WITHDRAWAL,
                "sender_account": account_number,
                "receiver_account": account_number,
            }
        )
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        amount = serializer.validated_data["amount"]

        if account.account_balance < amount:
            return Response(
                {"error": "Insufficient funds for withdrawal"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.session["withdrawal_data"] = {
            "account_number": account_number,
            "amount": str(amount),
        }
        logger.info("Withdrawal data stored in session")

        return Response(
            {
                "message": "Withdrawal Initiated. Please verify your username to complete the withdrawal",
                "next_step": "Verify your username to complete the withdrawal",
            },
            status=status.HTTP_200_OK,
        )

class InitiateTransferView(generics.CreateAPIView):
    serializer_class = TransactionSerializer
    renderer_classes = [GenericJSONRenderer]
    object_label = "initiate_transfer"

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        data = request.data.copy()
        data["transaction_type"] = Transaction.TransactionType.TRANSFER

        sender_account_number = data.get("sender_account")
        receiver_account_number = data.get("receiver_account")

        try:
            sender_account = BankAccount.objects.get( account_number=sender_account_number, user=request.user )
            if not (sender_account.fully_activated and sender_account.kyc_verified):
                return Response(
                    {
                        "error": "This account is not fully verified. Please complete the "
                        "verification process, by visiting any of our local bank branches"
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        except BankAccount.DoesNotExist:
            return Response(
                {
                    "error": "Sender account number not found or you're not authorized to use "
                    "this account."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(data=data)

        if serializer.is_valid():
            request.session["transfer_data"] = {

                "sender_account": sender_account_number,
                "receiver_account": receiver_account_number,
                "amount": str(serializer.validated_data["amount"]),
                "description": serializer.validated_data.get("description", ""),
            }
            return Response(
                {
                    "message": "Please answer your security question to proceed with the transfer",
                    "next_step": "verify security question",
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class VerifyUsernameAndWithdrawAPIView(generics.CreateAPIView):
    serializer_class = UsernameVerificationSerializer
    renderer_classes = [GenericJSONRenderer]
    object_label = "verify_username_and_withdraw"

    @transaction.atomic
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        withdrawal_data = request.session.get("withdrawal_data")
        if not withdrawal_data:
            return Response(
                {
                    "error": "No pending withdrawal found. Please initiate a withdrawal first"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        account_number = withdrawal_data["account_number"]
        amount = Decimal(withdrawal_data["amount"])

        try:
            account = BankAccount.objects.get(
                account_number=account_number, user=request.user
            )
        except BankAccount.DoesNotExist:
            return Response(
                {"error": f"Account number {account_number} does not exist"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if account.account_balance < amount:
            return Response(
                {"error": "Insufficient funds for withdrawal"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        account.account_balance -= amount
        account.save()

        withdraw_transaction = Transaction.objects.create(
            user=request.user,
            sender=request.user,
            sender_account=account,
            amount=amount,
            description=f"Withdrawal from account {account_number}",
            transaction_type=Transaction.TransactionType.WITHDRAWAL,
            status=Transaction.TransactionStatus.COMPLETED,
        )
        logger.info(f"Withdrawal of {amount} made from account {account_number}")

        send_withdrawal_email(
            user=account.user,
            user_email=account.user.email,
            amount=amount,
            currency=account.currency,
            new_balance=account.account_balance,
            account_number=account.account_number,
        )

        del request.session["withdrawal_data"]

        return Response(
            {
                "message": "Withdrawal completed successfully",
                "transaction": TransactionSerializer(withdraw_transaction).data,
            },
            status=status.HTTP_200_OK,
        )

class VerifySecurityQuestionView(generics.CreateAPIView):
    serializer_class = SecurityQuestionSerializer
    renderer_classes = [GenericJSONRenderer]
    object_label = "verification_answer"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer( data=request.data, context={"request": request})
        if serializer.is_valid():
            otp = generate_otp()
            request.user.set_otp(otp)
            send_transfer_otp_email(request.user.email, otp)
            return Response(
                {
                    "message": "Security question verified. An OTP has been sent to your email",
                    "next_step": "verify otp",
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VerifyOTPView(generics.CreateAPIView):
    serializer_class = OTPVerificationSerializer
    renderer_classes = [GenericJSONRenderer]
    object_label = "verify_otp"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            return self.process_transfer(request)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def process_transfer(self, request) -> Response:
        transfer_data = request.session.get("transfer_data")
        if not transfer_data:
            return Response(
                {"error": "Transfer data not found. Please start the process again."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            sender_account = BankAccount.objects.get(
                account_number=transfer_data["sender_account"]
            )
            receiver_account = BankAccount.objects.get(
                account_number=transfer_data["receiver_account"]
            )
        except BankAccount.DoesNotExist:
            return Response(
                {"error": "One or both accounts not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        amount = Decimal(transfer_data["amount"])

        if sender_account.account_balance < amount:
            return Response(
                {"error": "Insufficient funds for transfer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sender_account.account_balance -= amount
        receiver_account.account_balance += amount
        sender_account.save()
        receiver_account.save()

        transfer_transaction = Transaction.objects.create(
            user=request.user,
            sender=request.user,
            sender_account=sender_account,
            receiver=receiver_account.user,
            receiver_account=receiver_account,
            amount=amount,
            description=transfer_data.get("description", ""),
            transaction_type=Transaction.TransactionType.TRANSFER,
            status=Transaction.TransactionStatus.COMPLETED,
        )

        del request.session["transfer_data"]

        send_transfer_email(
            sender_name=sender_account.user.full_name,
            sender_email=sender_account.user.email,
            receiver_name=receiver_account.user.full_name,
            receiver_email=receiver_account.user.email,
            amount=amount,
            currency=sender_account.currency,
            sender_new_balance=sender_account.account_balance,
            receiver_new_balance=receiver_account.account_balance,
            sender_account_number=sender_account.account_number,
            receiver_account_number=receiver_account.account_number,
        )

        logger.info(
            f"Transfer of {amount} made from account {sender_account.account_number} to "
            f"{receiver_account.account_number}"
        )

        return Response(
            TransactionSerializer(transfer_transaction).data,
            status=status.HTTP_201_CREATED,
        )


class TransactionListAPIView(generics.ListAPIView):
    serializer_class = TransactionSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = ["created_at", "amount"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        queryset = Transaction.objects.filter(Q(sender=user) | Q(receiver=user))
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        account_number = self.request.query_params.get("account_number")

        if start_date:
            try:
                start_date = parser.parse(start_date)
                queryset = queryset.filter(created_at__gte=start_date)
            except ValueError:
                pass

        if end_date:
            try:
                end_date = parser.parse(end_date)
                queryset = queryset.filter(created_at__lte=end_date)
            except ValueError:
                pass

        if account_number:
            try:
                account = BankAccount.objects.get(account_number=account_number, user=user)
                queryset = queryset.filter(Q(sender_account=account) | Q(receiver_account=account))
            except BankAccount.DoesNotExist:
                queryset = Transaction.objects.none()

        return queryset

    def list(self, request, *args, **kwargs) -> Response:
        response = super().list(request, *args, **kwargs)

        account_number = request.query_params.get("account_number")
        if account_number:
            logger.info(f"User {request.user.email} successfully retrieved transactions for account: {account_number}")
        else:
            logger.info(f"User {request.user.email} retrieved transactions(all accounts)")
        return response
    
class TransactionPDFView(APIView):
    renderer_classes = [GenericJSONRenderer]
    object_label = "transaction_pdf"

    def post(self, request) -> Response:
        user = request.user
        start_date = request.data.get("start_date") or request.query_params.get("start_date")
        end_date = request.data.get("end_date") or request.query_params.get("end_date")
        account_number = request.data.get("account_number") or request.query_params.get("account_number")

        if not end_date:
            end_date = timezone.now().date().isoformat()

        if not start_date:
            start_date = ( ( parser.parse(end_date) - timezone.timedelta(days=30) ).date().isoformat() )
        try:
            start_date = parser.parse(start_date).date().isoformat()
            end_date = parser.parse(end_date).date().isoformat()
        except ValueError as e:
            return Response(
                {"error": f"Invalid date format: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        generate_transaction_pdf.delay(user.id, start_date, end_date, account_number)

        return Response(
            {
                "message": "Your Transaction history PDF is being generated and will be sent to "
                "your email shortly",
                "email": user.email,
            },
            status=status.HTTP_202_ACCEPTED,
        )