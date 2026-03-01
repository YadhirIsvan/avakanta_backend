from django.urls import path
from ..views.admin import AdminPropertyListCreateView

urlpatterns = [
    path('properties', AdminPropertyListCreateView.as_view(), name='admin-property-list-create'),
]
