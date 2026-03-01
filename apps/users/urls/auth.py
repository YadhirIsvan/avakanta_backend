from django.urls import path
from ..views.auth import OTPRequestView

urlpatterns = [
    path('email/otp', OTPRequestView.as_view(), name='auth-email-otp'),
]
