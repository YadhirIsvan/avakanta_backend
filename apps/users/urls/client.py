from django.urls import path
from ..views.client import (
    ClientDashboardView,
    ClientProfileView,
    ClientNotificationPreferencesView,
    ClientFinancialProfileView,
    ClientProfileDetailView,
    ClientAvatarUploadView,
)

urlpatterns = [
    path('dashboard', ClientDashboardView.as_view(), name='client-dashboard'),
    path('profile', ClientProfileView.as_view(), name='client-profile'),
    path('notification-preferences', ClientNotificationPreferencesView.as_view(), name='client-notification-prefs'),
    path('financial-profile', ClientFinancialProfileView.as_view(), name='client-financial-profile'),
    path('profile-detail', ClientProfileDetailView.as_view(), name='client-profile-detail'),
    path('avatar-upload', ClientAvatarUploadView.as_view(), name='client-avatar-upload'),
]
