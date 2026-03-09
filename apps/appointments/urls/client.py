from django.urls import path
from ..views.client import ClientAppointmentListView, ClientAppointmentCancelView

urlpatterns = [
    path('appointments', ClientAppointmentListView.as_view(), name='client-appointments'),
    path('appointments/<int:pk>/cancel', ClientAppointmentCancelView.as_view(), name='client-appointment-cancel'),
]
