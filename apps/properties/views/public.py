from django.db.models import Count, Q
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from core.pagination import StandardPagination
from ..models import Property
from ..serializers.public import PublicPropertyListSerializer, PublicPropertyDetailSerializer
from ..filters import PublicPropertyFilter

BASE_QUERYSET = (
    Property.objects
    .filter(listing_type='sale', status='disponible', is_active=True)
    .select_related('city__state')
    .prefetch_related('images')
    .annotate(interested_count=Count('purchase_processes', distinct=True))
)


class PublicPropertyListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicPropertyListSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = PublicPropertyFilter
    search_fields = ['title', 'address_street', 'address_neighborhood']
    ordering_fields = ['price', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return BASE_QUERYSET
