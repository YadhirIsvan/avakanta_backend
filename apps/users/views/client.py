from django.db.models import Q

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsClient
from apps.users.models import TenantMembership, UserNotificationPreferences
from apps.users.serializers.client import (
    ClientProfileSerializer,
    ClientProfileUpdateSerializer,
    ClientNotificationPreferencesSerializer,
)
from apps.transactions.models import PurchaseProcess, ProcessStatusHistory, SaleProcess


def _get_client_membership(request):
    return TenantMembership.objects.select_related('user').get(
        user=request.user, tenant=request.tenant, is_active=True
    )


def _cover_image(prop):
    cover = prop.images.filter(is_cover=True).first()
    return cover.image_url if cover else None


# Human-readable status labels
PURCHASE_STATUS_LABELS = {
    'lead': 'Lead',
    'visita': 'Visita',
    'interes': 'Interés',
    'pre_aprobacion': 'Pre-aprobación',
    'avaluo': 'Avalúo',
    'credito': 'Crédito',
    'docs_finales': 'Docs finales',
    'escrituras': 'Escrituras',
    'cerrado': 'Cerrado',
    'cancelado': 'Cancelado',
}

SALE_STATUS_LABELS = {
    'contacto_inicial': 'Contacto inicial',
    'evaluacion': 'Evaluación',
    'valuacion': 'Valuación',
    'presentacion': 'Presentación',
    'firma_contrato': 'Firma de contrato',
    'marketing': 'Marketing',
    'publicacion': 'Publicación',
    'cancelado': 'Cancelado',
}


class ClientDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def get(self, request):
        membership = _get_client_membership(request)
        user = membership.user

        # Recent activity from ProcessStatusHistory
        purchase_ids = list(
            PurchaseProcess.objects.filter(
                tenant=request.tenant, client_membership=membership
            ).values_list('pk', flat=True)
        )
        sale_ids = list(
            SaleProcess.objects.filter(
                tenant=request.tenant, client_membership=membership
            ).values_list('pk', flat=True)
        )

        history_qs = ProcessStatusHistory.objects.filter(
            Q(process_type='purchase', process_id__in=purchase_ids) |
            Q(process_type='sale', process_id__in=sale_ids)
        ).order_by('-created_at')[:5]

        recent_activity = []
        for h in history_qs:
            if h.process_type == 'purchase':
                label = PURCHASE_STATUS_LABELS.get(h.new_status, h.new_status)
                description = f'Tu proceso de compra avanzó a {label}'
                activity_type = 'purchase_status_change'
            else:
                label = SALE_STATUS_LABELS.get(h.new_status, h.new_status)
                description = f'Tu proceso de venta avanzó a {label}'
                activity_type = 'sale_status_change'
            recent_activity.append({
                'type': activity_type,
                'description': description,
                'created_at': h.created_at,
            })

        # Sale processes preview (last 3)
        sale_preview_qs = (
            SaleProcess.objects
            .filter(tenant=request.tenant, client_membership=membership)
            .select_related('property')
            .prefetch_related('property__images')
            .order_by('-created_at')[:3]
        )
        sale_processes_preview = [
            {
                'id': sp.pk,
                'property_title': sp.property.title,
                'status': sp.status,
                'image': _cover_image(sp.property),
            }
            for sp in sale_preview_qs
        ]

        # Purchase processes preview (last 3)
        purchase_preview_qs = (
            PurchaseProcess.objects
            .filter(tenant=request.tenant, client_membership=membership)
            .select_related('property')
            .prefetch_related('property__images')
            .order_by('-created_at')[:3]
        )
        purchase_processes_preview = [
            {
                'id': pp.pk,
                'property_title': pp.property.title,
                'status': pp.status,
                'overall_progress': pp.overall_progress,
                'image': _cover_image(pp.property),
            }
            for pp in purchase_preview_qs
        ]

        return Response({
            'client': {
                'name': user.get_full_name() or user.email,
                'avatar': user.avatar,
                'city': user.city,
            },
            'credit_score': None,
            'recent_activity': recent_activity,
            'sale_processes_preview': sale_processes_preview,
            'purchase_processes_preview': purchase_processes_preview,
        })


class ClientProfileView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def get(self, request):
        return Response(ClientProfileSerializer(request.user).data)

    def patch(self, request):
        serializer = ClientProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        update_fields = []
        for field in ('first_name', 'last_name', 'phone', 'city'):
            if field in data:
                setattr(request.user, field, data[field])
                update_fields.append(field)

        if update_fields:
            request.user.save(update_fields=update_fields)

        return Response(ClientProfileSerializer(request.user).data)


class ClientNotificationPreferencesView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def _get_prefs(self, request):
        membership = _get_client_membership(request)
        prefs, _ = UserNotificationPreferences.objects.get_or_create(
            membership=membership,
            defaults={
                'new_properties': True,
                'price_updates': True,
                'appointment_reminders': True,
                'offers': True,
            },
        )
        return prefs

    def get(self, request):
        prefs = self._get_prefs(request)
        return Response(ClientNotificationPreferencesSerializer(prefs).data)

    def put(self, request):
        prefs = self._get_prefs(request)
        serializer = ClientNotificationPreferencesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        prefs.new_properties = data['new_properties']
        prefs.price_updates = data['price_updates']
        prefs.appointment_reminders = data['appointment_reminders']
        prefs.offers = data['offers']
        prefs.save(update_fields=[
            'new_properties', 'price_updates', 'appointment_reminders', 'offers', 'updated_at'
        ])

        return Response(ClientNotificationPreferencesSerializer(prefs).data)
