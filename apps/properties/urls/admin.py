from django.urls import path
from ..views.admin import AdminPropertyListCreateView, AdminPropertyDetailView

urlpatterns = [
    path('properties', AdminPropertyListCreateView.as_view(), name='admin-property-list-create'),
    path('properties/<int:pk>', AdminPropertyDetailView.as_view(), name='admin-property-detail'),
]
