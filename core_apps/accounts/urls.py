from django.urls import path
from .views import (
    AccountVerificationView,
)

urlpatterns = [
    path(
        "verify/<uuid:pk>/",
        AccountVerificationView.as_view(),
        name="account_verification",
    ),
    
    ]