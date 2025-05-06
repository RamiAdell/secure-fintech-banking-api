from decimal import Decimal, InvalidOperation
from django.db import transaction
from loguru import logger
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from core_apps.accounts.models import Transaction
from core_apps.common.renderers import GenericJSONRenderer
from .emails import send_virtual_card_topup_email
from .models import VirtualCard
from .serializers import VirtualCardCreateSerializer, VirtualCardSerializer


class VirtualCardListCreateAPIView(generics.ListCreateAPIView):
    renderer_classes = [GenericJSONRenderer]
    object_label = "visa_card"

    def get_queryset(self):
        return VirtualCard.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return VirtualCardCreateSerializer
        return VirtualCardSerializer

    def create(self, request, *args, **kwargs) -> Response:
        if request.user.virtual_cards.count() >= 3:
            return Response(
                {"error": "You can only have up to 3 virtual cards at a time."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        bank_account_number = serializer.validated_data.get("bank_account_number")
        user_bank_accounts = request.user.bank_accounts.all()

        if not user_bank_accounts.filter(account_number=bank_account_number).exists():
            return Response({"error": "You can only create a virtual card linked to your own bank account"}, status=status.HTTP_403_FORBIDDEN)

        virtual_card = serializer.save(user=request.user)
        
        logger.info(f"Visa card number {virtual_card.card_number} created for user {request.user.full_name}")
        return Response(VirtualCardSerializer(virtual_card).data, status=status.HTTP_201_CREATED)


class VirtualCardDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VirtualCardSerializer
    renderer_classes = [GenericJSONRenderer]
    object_label = "visa_card"

    def get_queryset(self):
        return VirtualCard.objects.filter(user=self.request.user)

    def get_object(self):
        obj = super().get_object()
        if obj.user != self.request.user:
            raise PermissionDenied(
                "You can't perform this action, because the card does not belong to you"
            )
        return obj

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance.balance > 0:
                return Response(
                    {"error": "Cannot delete a card with non-zero balance"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            self.perform_destroy(instance)
            logger.info(
                f"Visa card number {instance.card_number}, belonging to "
                f"{instance.user.full_name} destroyed"
            )
            return Response(
                {"message": "Card successfully deleted"}, status=status.HTTP_200_OK
            )
        except VirtualCard.DoesNotExist:
            return Response(
                {"error": "Card not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except PermissionDenied as e:
            return Response({"error": str(e)})
        except Exception as e:
            logger.error(f"Error deleting card: {str(e)}")
            return Response(
                {"error": "An unexpected error occurred while deleting the card"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class VirtualCardTopUpAPIView(generics.UpdateAPIView):
    renderer_classes = [GenericJSONRenderer]
    object_label = "visa_card"

    def get_queryset(self):
        return VirtualCard.objects.filter(user=self.request.user)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        virtual_card = self.get_object()
        amount = request.data.get("amount")

        if not amount:
            return Response(
                {"error": "Amount must be provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            amount = Decimal(amount)
        except InvalidOperation:
            return Response(
                {"error": f"The Amount {amount} is not valid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if amount <= 0:
            return Response(
                {"error": "Amount must be greater than zero"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        bank_account = virtual_card.bank_account

        if bank_account.account_balance < amount:
            return Response(
                {"error": "Insufficient funds in the bank account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bank_account.account_balance -= amount
        virtual_card.balance += amount

        bank_account.save()
        virtual_card.save()

        transaction = Transaction.objects.create(
            user=request.user,
            amount=amount,
            description=f"Top-up for Visa card ending in {virtual_card.card_number[-4:]} ",
            transaction_type=Transaction.TransactionType.DEPOSIT,
            status=Transaction.TransactionStatus.COMPLETED,
            sender=request.user,
            receiver=request.user,
            sender_account=bank_account,
            receiver_account=bank_account,
        )
        send_virtual_card_topup_email(
            request.user, virtual_card, amount, virtual_card.balance
        )
        logger.info(
            f"Visa card {virtual_card.card_number} has been topped up with {amount} by "
            f"{virtual_card.user.full_name}. Transaction ID: {transaction.id}"
        )

        return Response(VirtualCardSerializer(virtual_card).data)