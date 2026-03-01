from django.urls import path
from ..views.public import AppointmentSlotsView

urlpatterns = [
    path('appointment/slots', AppointmentSlotsView.as_view(), name='public-appointment-slots'),
]
