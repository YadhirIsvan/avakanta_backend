from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from .models import Country, State, City, Amenity
from .serializers import CountrySerializer, StateSerializer, CitySerializer, AmenitySerializer


class CountryListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CountrySerializer
    pagination_class = None
    queryset = Country.objects.all()


class StateListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = StateSerializer
    pagination_class = None

    def get_queryset(self):
        qs = State.objects.all()
        country_id = self.request.query_params.get('country_id')
        if country_id:
            qs = qs.filter(country_id=country_id)
        return qs


class CityListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CitySerializer
    pagination_class = None

    def get_queryset(self):
        qs = City.objects.all()
        state_id = self.request.query_params.get('state_id')
        if state_id:
            qs = qs.filter(state_id=state_id)
        return qs


class AmenityListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = AmenitySerializer
    pagination_class = None
    queryset = Amenity.objects.all()
