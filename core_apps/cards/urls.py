from django.urls import path

from .views import (
    VirtualCardDetailAPIView,
    VirtualCardListCreateAPIView,
    VirtualCardTopUpAPIView,
)

urlpatterns = [
    path(
        "virtual-cards/",
        VirtualCardListCreateAPIView.as_view(),
        name="virtual-card-list-create",
    ),
    path(
        "virtual-cards/<uuid:pk>/",
        VirtualCardDetailAPIView.as_view(),
        name="virtual-card-detail",
    ),
    path(
        "virtual-cards/<uuid:pk>/top-up/",
        VirtualCardTopUpAPIView.as_view(),
        name="virtual-card-topup",
    ),
]