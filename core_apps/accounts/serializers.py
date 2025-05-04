from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from .models import BankAccount, Transaction
from decimal import Decimal


class AccountVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = [
            "kyc_submitted",
            "kyc_verified",
            "verification_date",
            "verification_notes",
            "fully_activated",
            "account_status",
        ]
        read_only_fields = ["fully_activated"]

    def validate(self, data: dict) -> dict:
        kyc_verified = data.get("kyc_verified")
        kyc_submitted = data.get("kyc_submitted")
        verification_date = data.get("verification_date")
        verification_notes = data.get("verification_notes")

        if kyc_verified:
            if not verification_date:
                raise serializers.ValidationError(
                    _("Verification date is required when verifying an account.")
                )
            if not verification_notes:
                raise serializers.ValidationError(
                    _("Verification notes are required when verifying an account.")
                )

            if kyc_submitted and not all(
                [kyc_verified, verification_date, verification_notes]
            ):
                raise serializers.ValidationError(
                    _(
                        "All Verification fields (KYC Verified,verification date and notes) must be"
                        " provided when KYC is submitted"
                    )
                )

        return data
