from django.urls import path
from ..views.auth import OTPRequestView, OTPVerifyView

urlpatterns = [
    path('email/otp', OTPRequestView.as_view(), name='auth-email-otp'),
    path('email/verify', OTPVerifyView.as_view(), name='auth-email-verify'),
]
