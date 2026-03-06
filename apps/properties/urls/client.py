from django.urls import path

from ..views.client import (
    ClientSavedPropertiesView,
    ClientSavedPropertyCheckView,
    ClientSavedPropertyDeleteView,
)

urlpatterns = [
    path('saved-properties', ClientSavedPropertiesView.as_view()),
    path('saved-properties/check', ClientSavedPropertyCheckView.as_view()),
    path('saved-properties/<int:property_id>', ClientSavedPropertyDeleteView.as_view()),
]
