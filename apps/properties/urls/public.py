from django.urls import path
from ..views.public import PublicPropertyListView

urlpatterns = [
    path('properties', PublicPropertyListView.as_view(), name='public-property-list'),
]
