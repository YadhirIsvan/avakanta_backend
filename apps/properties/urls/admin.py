from django.urls import path
from ..views.admin import (
    AdminPropertyListCreateView,
    AdminPropertyDetailView,
    AdminPropertyImageView,
    AdminPropertyImageDeleteView,
    AdminPropertyDocumentView,
    AdminPropertyToggleFeaturedView,
    AdminAssignmentView,
    AdminAssignmentDetailView,
)

urlpatterns = [
    path('properties', AdminPropertyListCreateView.as_view(), name='admin-property-list-create'),
    path('properties/<int:pk>', AdminPropertyDetailView.as_view(), name='admin-property-detail'),
    path('properties/<int:pk>/images', AdminPropertyImageView.as_view(), name='admin-property-images'),
    path('properties/<int:pk>/images/<int:image_id>', AdminPropertyImageDeleteView.as_view(), name='admin-property-image-delete'),
    path('properties/<int:pk>/documents', AdminPropertyDocumentView.as_view(), name='admin-property-documents'),
    path('properties/<int:pk>/toggle-featured', AdminPropertyToggleFeaturedView.as_view(), name='admin-property-toggle-featured'),
    path('assignments', AdminAssignmentView.as_view(), name='admin-assignments'),
    path('assignments/<int:pk>', AdminAssignmentDetailView.as_view(), name='admin-assignment-detail'),
]
