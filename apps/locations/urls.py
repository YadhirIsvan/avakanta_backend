from django.urls import path
from .views import CountryListView, StateListView, CityListView, AmenityListView

urlpatterns = [
    path('countries', CountryListView.as_view(), name='catalog-countries'),
    path('states', StateListView.as_view(), name='catalog-states'),
    path('cities', CityListView.as_view(), name='catalog-cities'),
    path('amenities', AmenityListView.as_view(), name='catalog-amenities'),
]
