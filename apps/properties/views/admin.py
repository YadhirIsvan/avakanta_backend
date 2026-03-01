from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter

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
            instance,
            context=self.get_serializer_context(),
        )
        from rest_framework.response import Response
        return Response(detail_serializer.data, status=201)
