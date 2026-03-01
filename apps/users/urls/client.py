from django.urls import path
from ..views.client import (
    ClientDashboardView,
    ClientProfileView,
    ClientNotificationPreferencesView,
)

urlpatterns = [
    path('dashboard', ClientDashboardView.as_view(), name='client-dashboard'),
    path('profile', ClientProfileView.as_view(), name='client-profile'),
    path('notification-preferences', ClientNotificationPreferencesView.as_view(), name='client-notification-prefs'),
]
