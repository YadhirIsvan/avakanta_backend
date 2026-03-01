from django.urls import path
from ..views.agent import AgentPropertyListView, AgentPropertyLeadsView

urlpatterns = [
    path('properties', AgentPropertyListView.as_view(), name='agent-property-list'),
    path('properties/<int:pk>/leads', AgentPropertyLeadsView.as_view(), name='agent-property-leads'),
]
