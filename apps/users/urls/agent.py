from django.urls import path
from ..views.agent import AgentDashboardView

urlpatterns = [
    path('dashboard', AgentDashboardView.as_view(), name='agent-dashboard'),
]
