from django.urls import path
from ..views.admin import AdminAgentListCreateView, AdminAgentDetailView

urlpatterns = [
    path('agents', AdminAgentListCreateView.as_view(), name='admin-agent-list-create'),
    path('agents/<int:pk>', AdminAgentDetailView.as_view(), name='admin-agent-detail'),
]
