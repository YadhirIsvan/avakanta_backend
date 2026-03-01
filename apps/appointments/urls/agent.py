from django.urls import path
from ..views.agent import AgentAppointmentListView, AgentAppointmentStatusView

urlpatterns = [
    path('appointments', AgentAppointmentListView.as_view(), name='agent-appointment-list'),
    path('appointments/<int:pk>/status', AgentAppointmentStatusView.as_view(), name='agent-appointment-status'),
]
