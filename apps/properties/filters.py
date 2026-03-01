import django_filters
from .models import Property


class PublicPropertyFilter(django_filters.FilterSet):
    zone = django_filters.CharFilter(field_name='zone', lookup_expr='iexact')
    type = django_filters.CharFilter(field_name='property_type', lookup_expr='exact')
    state = django_filters.CharFilter(field_name='property_condition', lookup_expr='exact')
    amenities = django_filters.BaseInFilter(
        field_name='property_amenities__amenity_id', lookup_expr='in'
    )
    price_min = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    featured = django_filters.BooleanFilter(field_name='is_featured')

    class Meta:
        model = Property
        fields = ['zone', 'type', 'state', 'amenities', 'price_min', 'price_max', 'featured']
