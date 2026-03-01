from django.urls import path
from ..views.admin import (
    AdminAgentScheduleListCreateView,
    AdminAgentScheduleDetailView,
    AdminAgentUnavailabilityListCreateView,
    AdminAgentUnavailabilityDeleteView,
    AdminAppointmentListCreateView,
    AdminAppointmentDetailView,
    AdminAppointmentAvailabilityView,
)

urlpatterns = [
    # Schedules
    path('agents/<int:agent_id>/schedules', AdminAgentScheduleListCreateView.as_view(), name='admin-agent-schedules'),
    path('agents/<int:agent_id>/schedules/<int:schedule_id>', AdminAgentScheduleDetailView.as_view(), name='admin-agent-schedule-detail'),
    # Unavailabilities
    path('agents/<int:agent_id>/unavailabilities', AdminAgentUnavailabilityListCreateView.as_view(), name='admin-agent-unavailabilities'),
    path('agents/<int:agent_id>/unavailabilities/<int:unavailability_id>', AdminAgentUnavailabilityDeleteView.as_view(), name='admin-agent-unavailability-delete'),
    # Appointments
    path('appointments/availability', AdminAppointmentAvailabilityView.as_view(), name='admin-appointment-availability'),
    path('appointments', AdminAppointmentListCreateView.as_view(), name='admin-appointment-list-create'),
    path('appointments/<int:pk>', AdminAppointmentDetailView.as_view(), name='admin-appointment-detail'),
]
