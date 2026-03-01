from django.urls import path
from ..views.admin import (
    AdminPropertyListCreateView,
    AdminPropertyDetailView,
    AdminPropertyImageView,
    AdminPropertyImageDeleteView,
)

urlpatterns = [
    path('properties', AdminPropertyListCreateView.as_view(), name='admin-property-list-create'),
    path('properties/<int:pk>', AdminPropertyDetailView.as_view(), name='admin-property-detail'),
    path('properties/<int:pk>/images', AdminPropertyImageView.as_view(), name='admin-property-images'),
    path('properties/<int:pk>/images/<int:image_id>', AdminPropertyImageDeleteView.as_view(), name='admin-property-image-delete'),
]
