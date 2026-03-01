from django.urls import path
from ..views.admin import (
    AdminAgentListCreateView,
    AdminAgentDetailView,
    AdminClientListView,
    AdminClientDetailView,
)

urlpatterns = [
    path('agents', AdminAgentListCreateView.as_view(), name='admin-agent-list-create'),
    path('agents/<int:pk>', AdminAgentDetailView.as_view(), name='admin-agent-detail'),
    path('clients', AdminClientListView.as_view(), name='admin-client-list'),
    path('clients/<int:pk>', AdminClientDetailView.as_view(), name='admin-client-detail'),
]
