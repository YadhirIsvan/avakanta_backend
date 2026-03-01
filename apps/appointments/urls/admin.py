from django.urls import path
from ..views.admin import (
    AdminAgentScheduleListCreateView,
    AdminAgentScheduleDetailView,
    AdminAgentUnavailabilityListCreateView,
    AdminAgentUnavailabilityDeleteView,
)

urlpatterns = [
    path('agents/<int:agent_id>/schedules', AdminAgentScheduleListCreateView.as_view(), name='admin-agent-schedules'),
    path('agents/<int:agent_id>/schedules/<int:schedule_id>', AdminAgentScheduleDetailView.as_view(), name='admin-agent-schedule-detail'),
    path('agents/<int:agent_id>/unavailabilities', AdminAgentUnavailabilityListCreateView.as_view(), name='admin-agent-unavailabilities'),
    path('agents/<int:agent_id>/unavailabilities/<int:unavailability_id>', AdminAgentUnavailabilityDeleteView.as_view(), name='admin-agent-unavailability-delete'),
]
