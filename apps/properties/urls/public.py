from django.urls import path
from ..views.public import PublicPropertyListView, PublicPropertyDetailView

urlpatterns = [
    path('properties', PublicPropertyListView.as_view(), name='public-property-list'),
    path('properties/<int:pk>', PublicPropertyDetailView.as_view(), name='public-property-detail'),
]
