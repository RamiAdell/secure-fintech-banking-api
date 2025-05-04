from typing import Any, List

from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, filters, generics
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.request import Request

from core_apps.common.models import ContentView
from core_apps.common.permissions import IsBranchManager
from core_apps.accounts.models import BankAccount
from core_apps.accounts.utils.account_helper import create_bank_account
from core_apps.common.renderers import GenericJSONRenderer
from .models import NextOfKin, Profile
from .serializers import NextOfKinSerializer, ProfileListSerializer, ProfileSerializer


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class ProfileListAPIView(generics.ListAPIView):
    serializer_class = ProfileListSerializer
    renderer_classes = [GenericJSONRenderer]
    pagination_class = StandardResultsSetPagination
    object_label = "profiles"
    permission_classes = [IsBranchManager]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ["user__first_name", "user__last_name", "user__id_no"]
    filterset_fields = ["user__first_name", "user__last_name", "user__id_no"]

    def get_queryset(self) -> List[Profile]:
        return Profile.objects.exclude(user__is_staff=True).exclude(
            user__is_superuser=True
        )


class ProfileDetailAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    renderer_classes = [GenericJSONRenderer]
    object_label = "profile"

    def get_object(self) -> Profile:
        try:
            profile = Profile.objects.get(user=self.request.user)
            self.record_profile_view(profile)
            return profile
        except Profile.DoesNotExist:
            raise Http404("Profile does not exist")

    def record_profile_view(self, profile: Profile) -> None:
        content_type = ContentType.objects.get_for_model(profile)
        viewer_ip = self.get_client_ip()
        user = self.request.user

        obj, created = ContentView.objects.update_or_create(
            content_type=content_type,
            object_id=profile.id,
            user=user,
            viewer_ip=viewer_ip,
            defaults={
                "last_viewed": timezone.now(),
            },
        )

    def get_client_ip(self) -> str:
        x_forwarded_for = self.request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = self.request.META.get("REMOTE_ADDR")
        return ip

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        try:
            serializer.is_valid(raise_exception=True)
            with transaction.atomic():
                updated_instance = serializer.save()

                if updated_instance.is_complete_with_next_of_kin():
                    existing_account = BankAccount.objects.filter(
                        user=request.user,
                        currency=updated_instance.account_currency,
                        account_type=updated_instance.account_type,
                    ).first()

                    if not existing_account:
                        bank_account = create_bank_account(
                            request.user,
                            currency=updated_instance.account_currency,
                            account_type=updated_instance.account_type,
                        )
                        message = (
                            "Profile updated and new bank account created successfully. An email "
                            "has been sent to you with further instructions"
                        )
                    else:
                        message = (
                            "Profile updated successfully. No new account created as one already "
                            "exists for this currency and type."
                        )
                    return Response(
                        {
                            "message": message,
                            "data": serializer.data,
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    return Response(
                        {
                            "message": "Profile updated successfully. Please complete all "
                            "required fields and at least one next of kin to create a "
                            "bank account.",
                            "data": serializer.data,
                        },
                        status=status.HTTP_200_OK,
                    )

        except serializers.ValidationError as e:
            return Response({"errors": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def perform_update(self, serializer: ProfileSerializer) -> None:
        serializer.save()


class NextOfKinAPIView(generics.ListCreateAPIView):
    serializer_class = NextOfKinSerializer
    pagination_class = StandardResultsSetPagination
    renderer_classes = [GenericJSONRenderer]
    object_label = "next_of_kin"

    def get_queryset(self) -> List[NextOfKin]:
        return NextOfKin.objects.filter(profile=self.request.user.profile)

    def get_serializer_context(self) -> dict[str, Any]:
        context = super().get_serializer_context()
        context["profile"] = self.request.user.profile
        return context

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def perform_create(self, serializer: NextOfKinSerializer) -> None:
        serializer.save()


class NextOfKinDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = NextOfKinSerializer
    renderer_classes = [GenericJSONRenderer]
    object_label = "next_of_kin"

    def get_queryset(self) -> List[NextOfKin]:
        return NextOfKin.objects.filter(profile=self.request.user.profile)

    def get_object(self) -> NextOfKin:
        queryset = self.get_queryset()
        obj = get_object_or_404(queryset, pk=self.kwargs["pk"])
        self.check_object_permissions(self.request, obj)
        return obj

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {"message": "Next of Kin deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )