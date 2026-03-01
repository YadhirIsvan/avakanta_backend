from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from ..views.auth import (
    OTPRequestView,
    OTPVerifyView,
    LogoutView,
    GoogleLoginView,
    AppleLoginView,
)

urlpatterns = [
    path('email/otp', OTPRequestView.as_view(), name='auth-email-otp'),
    path('email/verify', OTPVerifyView.as_view(), name='auth-email-verify'),
    path('refresh', TokenRefreshView.as_view(), name='auth-refresh'),
    path('logout', LogoutView.as_view(), name='auth-logout'),
    path('google', GoogleLoginView.as_view(), name='auth-google'),
    path('apple', AppleLoginView.as_view(), name='auth-apple'),
]
