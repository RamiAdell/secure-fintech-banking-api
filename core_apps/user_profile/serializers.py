import base64
from typing import Any, Dict

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django_countries.serializer_fields import CountryField
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers

from core_apps.common.models import ContentView
from .models import Profile, NextOfKin
from .tasks import upload_photos_to_cloudinary

User = get_user_model()


class UUIDField(serializers.Field):
    def to_representation(self, value: str) -> str:
        return str(value)


class NextOfKinSerializer(serializers.ModelSerializer):
    id = UUIDField(read_only=True)
    country = CountryField(name_only=True)
    phone_number = PhoneNumberField()

    class Meta:
        model = NextOfKin
        exclude = ["profile"]

    def create(self, validated_data: dict) -> NextOfKin:
        profile = self.context.get("profile")
        if not profile:
            raise serializers.ValidationError("Profile context is required")
        return NextOfKin.objects.create(profile=profile, **validated_data)


class ProfileSerializer(serializers.ModelSerializer):
    id = UUIDField(read_only=True)
    first_name = serializers.CharField(source="user.first_name")
    middle_name = serializers.CharField(source="user.middle_name", required=False, allow_blank=True)
    last_name = serializers.CharField(source="user.last_name")
    username = serializers.ReadOnlyField(source="user.username")
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.ReadOnlyField(source="user.full_name")
    id_no = serializers.ReadOnlyField(source="user.id_no")
    date_joined = serializers.DateTimeField(source="user.date_joined", read_only=True)
    country_of_birth = CountryField(name_only=True)
    country = CountryField(name_only=True)
    phone_number = PhoneNumberField()
    next_of_kin = NextOfKinSerializer(many=True, read_only=True)
    photo = serializers.ImageField(write_only=True, required=False)
    id_photo = serializers.ImageField(write_only=True, required=False)
    signature_photo = serializers.ImageField(write_only=True, required=False)

    photo_url = serializers.URLField(read_only=True)
    id_photo_url = serializers.URLField(read_only=True)
    signature_photo_url = serializers.URLField(read_only=True)
    view_count = serializers.SerializerMethodField()


    class Meta:
        model = Profile
        fields = [
            "id",
            "first_name",
            "middle_name",
            "last_name",
            "username",
            "id_no",
            "email",
            "full_name",
            "date_joined",
            "title",
            "gender",
            "date_of_birth",
            "country_of_birth",
            "place_of_birth",
            "marital_status",
            "means_of_identification",
            "id_issue_date",
            "id_expiry_date",
            "passport_number",
            "nationality",
            "phone_number",
            "address",
            "city",
            "country",
            "employment_status",
            "employer_name",
            "annual_income",
            "date_of_employment",
            "employer_address",
            "employer_city",
            "employer_state",
            "next_of_kin",
            "created_at",
            "updated_at",
            "photo",
            "photo_url",
            "id_photo",
            "id_photo_url",
            "signature_photo",
            "signature_photo_url",
            "view_count"
        ]
        read_only_fields = [
            "user",
            "id",
            "username",
            "email",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        id_issue_date = attrs.get("id_issue_date")
        id_expiry_date = attrs.get("id_expiry_date")

        if id_issue_date and id_expiry_date and id_expiry_date <= id_issue_date:
            raise serializers.ValidationError(
                {"id_expiry_date": "ID expiry date must be after the issue date"}
            )

        return attrs

    def to_representation(self, instance: Profile) -> dict:
        representation = super().to_representation(instance)

        representation["next_of_kin"] = NextOfKinSerializer(
            instance.next_of_kin.all(), many=True
        ).data

        return representation

    def update(self, instance: Profile, validated_data: dict) -> Profile:
        user_data = validated_data.pop("user", {})

        if user_data:
            for attr, value in user_data.items():
                if attr not in ["email", "username"]:
                    setattr(instance.user, attr, value)
            instance.user.save()

        photos_to_upload = {}

        for field in ["photo", "id_photo", "signature_photo"]:
            if field in validated_data:
                photo = validated_data.pop(field)
                if photo.size > settings.MAX_UPLOAD_SIZE:
                    temp_file = default_storage.save(
                        f"temp_{instance.id}_{field}.jpg", ContentFile(photo.read())
                    )
                    temp_file_path = default_storage.path(temp_file)
                    photos_to_upload[field] = {"type": "file", "path": temp_file_path}
                else:
                    image_content = photo.read()
                    encoded_image = base64.b64encode(image_content).decode("utf-8")
                    photos_to_upload[field] = {"type": "base64", "data": encoded_image}

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if photos_to_upload:
            upload_photos_to_cloudinary.delay(str(instance.id), photos_to_upload)

        return instance

    def get_view_count(self, obj: Profile) -> int:
        content_type = ContentType.objects.get_for_model(obj)
        return ContentView.objects.filter(
            content_type=content_type, object_id=obj.id
        ).count()


class ProfileListSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField(source="user.full_name")
    username = serializers.ReadOnlyField(source="user.username")
    email = serializers.EmailField(source="user.email", read_only=True)
    photo = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "full_name",
            "username",
            "gender",
            "nationality",
            "country_of_birth",
            "email",
            "phone_number",
            "photo",
        ]

    def get_photo(self, obj: Profile) -> str | None:
        try:
            return obj.photo.url
        except AttributeError:
            return None