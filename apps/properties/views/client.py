from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import StandardPagination
from core.permissions import IsClient
from apps.users.models import TenantMembership
from ..models import Property, SavedProperty
from ..serializers.client import ClientSavedPropertySerializer


def _get_client_membership(request):
    return TenantMembership.objects.get(
        user=request.user, tenant=request.tenant, is_active=True
    )


class ClientSavedPropertiesView(APIView):
    permission_classes = [IsAuthenticated, IsClient]
    pagination_class = StandardPagination

    def get(self, request):
        membership = _get_client_membership(request)
        qs = (
            SavedProperty.objects
            .filter(client_membership=membership)
            .select_related('property__city__state')
            .prefetch_related('property__images')
            .order_by('-created_at')
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = ClientSavedPropertySerializer(
            page, many=True, context={'request': request}
        )
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        membership = _get_client_membership(request)
        property_id = request.data.get('property_id')

        if not property_id:
            return Response({'error': 'property_id es requerido.'}, status=400)

        try:
            prop = Property.objects.get(
                pk=property_id,
                is_active=True,
                listing_type='sale',
            )
        except Property.DoesNotExist:
            return Response({'error': 'Propiedad no encontrada.'}, status=404)

        saved, created = SavedProperty.objects.get_or_create(
            client_membership=membership,
            property=prop,
            defaults={'tenant': request.tenant},
        )

        return Response({'id': saved.pk, 'property_id': prop.pk}, status=201)


class ClientSavedPropertyCheckView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def get(self, request):
        membership = _get_client_membership(request)
        property_id = request.query_params.get('property_id')

        if not property_id:
            return Response({'error': 'property_id es requerido.'}, status=400)

        is_saved = SavedProperty.objects.filter(
            client_membership=membership, property_id=property_id
        ).exists()

        return Response({'is_saved': is_saved})


class ClientSavedPropertyDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def delete(self, request, property_id):
        membership = _get_client_membership(request)

        deleted, _ = SavedProperty.objects.filter(
            client_membership=membership, property_id=property_id
        ).delete()

        if deleted == 0:
            return Response({'error': 'Propiedad guardada no encontrada.'}, status=404)

        return Response(status=204)
