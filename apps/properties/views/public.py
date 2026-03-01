from django.db.models import Value
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from core.pagination import StandardPagination
from ..models import Property
from ..serializers.public import PublicPropertyListSerializer, PublicPropertyDetailSerializer
from ..filters import PublicPropertyFilter

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
        return (
            Property.objects
            .filter(listing_type='sale', status='disponible', is_active=True)
            .select_related('city__state')
            .prefetch_related('images')
            .annotate(interested_count=Value(0))
        )


class PublicPropertyDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicPropertyDetailSerializer

    def get_queryset(self):
        return (
            Property.objects
            .filter(listing_type='sale', status='disponible', is_active=True)
            .select_related('city__state')
            .prefetch_related(
                'images',
                'property_amenities__amenity',
                'nearby_places',
                'assignments__agent_membership__user',
            )
            .annotate(interested_count=Value(0))
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        Property.objects.filter(pk=instance.pk).update(views=instance.views + 1)
        instance.views += 1
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
