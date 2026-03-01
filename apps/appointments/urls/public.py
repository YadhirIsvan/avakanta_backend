from django.urls import path
from ..views.public import AppointmentSlotsView, CreateAppointmentView

urlpatterns = [
    path('appointment/slots', AppointmentSlotsView.as_view(), name='public-appointment-slots'),
    path('properties/<int:pk>/appointment', CreateAppointmentView.as_view(), name='public-create-appointment'),
]
