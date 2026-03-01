from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from core.mixins import TenantQuerySetMixin
from core.pagination import StandardPagination
from core.permissions import IsAdmin
from ..models import Property
from ..serializers.admin import (
    AdminPropertyListSerializer,
    AdminPropertyDetailSerializer,
    AdminPropertyCreateUpdateSerializer,
)


class AdminPropertyListCreateView(TenantQuerySetMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardPagination
    filter_backends = [SearchFilter]
    search_fields = ['title', 'address_street', 'address_neighborhood']

    queryset = (
        Property.objects
        .select_related('city__state')
        .prefetch_related('images', 'assignments__agent_membership__user', 'documents')
    )

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AdminPropertyCreateUpdateSerializer
        return AdminPropertyListSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        status = self.request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)

        listing_type = self.request.query_params.get('listing_type')
        if listing_type:
            qs = qs.filter(listing_type=listing_type)

        property_type = self.request.query_params.get('property_type')
        if property_type:
            qs = qs.filter(property_type=property_type)

        agent_id = self.request.query_params.get('agent_id')
        if agent_id:
            qs = qs.filter(assignments__agent_membership_id=agent_id, assignments__is_visible=True)

        return qs.order_by('-created_at')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        detail_serializer = AdminPropertyDetailSerializer(
            instance, context=self.get_serializer_context(),
        )
        return Response(detail_serializer.data, status=201)


class AdminPropertyDetailView(TenantQuerySetMixin, RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    queryset = (
        Property.objects
        .select_related('city__state')
        .prefetch_related(
            'images',
            'property_amenities__amenity',
            'nearby_places',
            'documents',
            'assignments__agent_membership__user',
        )
    )

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return AdminPropertyCreateUpdateSerializer
        return AdminPropertyDetailSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Reload with all relations for detail response
        instance.refresh_from_db()
        detail = AdminPropertyDetailSerializer(
            self.get_queryset().get(pk=instance.pk),
            context=self.get_serializer_context(),
        )
        return Response(detail.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        return Response(status=204)
