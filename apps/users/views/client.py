import os
from django.db.models import Q

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from core.permissions import IsClient
from apps.users.models import TenantMembership, UserNotificationPreferences, ClientFinancialProfile, ClientProfile
from django.core.files.storage import default_storage

from apps.users.serializers.client import (
    ClientProfileSerializer,
    ClientProfileUpdateSerializer,
    ClientNotificationPreferencesSerializer,
    ClientFinancialProfileSerializer,
    ClientFinancialProfileCreateUpdateSerializer,
    ClientProfileDetailSerializer,
    ClientAvatarUploadSerializer,
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
        for field in ('first_name', 'last_name', 'phone', 'city', 'avatar'):
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


class ClientFinancialProfileView(APIView):
    """GET, POST, PUT /client/financial-profile/
    
    GET: obtener perfil financiero del cliente
    POST: crear perfil financiero (primera vez)
    PUT: actualizar perfil financiero
    """
    permission_classes = [IsAuthenticated, IsClient]

    def _get_membership(self, request):
        return TenantMembership.objects.select_related('user').get(
            user=request.user, tenant=request.tenant, is_active=True
        )

    def _calculate_budget(self, loan_type, monthly_income, partner_monthly_income, savings):
        """Calcula presupuesto máximo usando fórmula de amortización."""
        # Ingresos totales mensuales
        total_monthly_income = float(monthly_income)
        if loan_type == 'conyugal' and partner_monthly_income:
            total_monthly_income += float(partner_monthly_income)

        # Parámetros asumidos: tasa 11% anual, plazo 15 años
        monthly_rate = 0.11 / 12
        months = 15 * 12

        # Máximo a pagar por mes (40% del ingreso)
        max_monthly_payment = total_monthly_income * 0.4

        # Fórmula de amortización inversa: principal = pago / factor
        if monthly_rate == 0:
            max_principal = max_monthly_payment * months
        else:
            amortization_factor = (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
            max_principal = max_monthly_payment / amortization_factor

        # Presupuesto total = lo que puede financiar + su ahorro actual
        total_budget = max_principal + float(savings)
        return round(total_budget, 2)

    def get(self, request):
        """GET: obtener perfil financiero"""
        membership = self._get_membership(request)
        try:
            profile = ClientFinancialProfile.objects.get(membership=membership)
            return Response(ClientFinancialProfileSerializer(profile).data)
        except ClientFinancialProfile.DoesNotExist:
            return Response(None)

    def post(self, request):
        """POST: crear perfil financiero (primera vez)"""
        membership = self._get_membership(request)
        
        # Validar que no exista ya
        if ClientFinancialProfile.objects.filter(membership=membership).exists():
            return Response(
                {'error': 'Financial profile already exists. Use PUT to update.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ClientFinancialProfileCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Calcular presupuesto
        calculated_budget = self._calculate_budget(
            loan_type=data['loan_type'],
            monthly_income=data['monthly_income'],
            partner_monthly_income=data.get('partner_monthly_income'),
            savings=data['savings_for_enganche']
        )

        # Crear perfil
        profile = ClientFinancialProfile.objects.create(
            membership=membership,
            loan_type=data['loan_type'],
            monthly_income=data['monthly_income'],
            partner_monthly_income=data.get('partner_monthly_income', 0),
            savings_for_enganche=data['savings_for_enganche'],
            has_infonavit=data.get('has_infonavit', False),
            infonavit_subcuenta_balance=data.get('infonavit_subcuenta_balance', 0),
            calculated_budget=calculated_budget
        )

        return Response(
            ClientFinancialProfileSerializer(profile).data,
            status=status.HTTP_201_CREATED
        )

    def put(self, request):
        """PUT: actualizar perfil financiero"""
        membership = self._get_membership(request)
        
        try:
            profile = ClientFinancialProfile.objects.get(membership=membership)
        except ClientFinancialProfile.DoesNotExist:
            return Response(
                {'error': 'No financial profile found. Use POST to create.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ClientFinancialProfileCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Calcular presupuesto con nuevos datos
        calculated_budget = self._calculate_budget(
            loan_type=data['loan_type'],
            monthly_income=data['monthly_income'],
            partner_monthly_income=data.get('partner_monthly_income'),
            savings=data['savings_for_enganche']
        )

        # Actualizar perfil
        profile.loan_type = data['loan_type']
        profile.monthly_income = data['monthly_income']
        profile.partner_monthly_income = data.get('partner_monthly_income', 0)
        profile.savings_for_enganche = data['savings_for_enganche']
        profile.has_infonavit = data.get('has_infonavit', False)
        profile.infonavit_subcuenta_balance = data.get('infonavit_subcuenta_balance', 0)
        profile.calculated_budget = calculated_budget
        profile.save()

        return Response(ClientFinancialProfileSerializer(profile).data)


class ClientProfileDetailView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def get(self, request):
        membership = _get_client_membership(request)
        profile, _ = ClientProfile.objects.get_or_create(membership=membership)
        return Response(ClientProfileDetailSerializer(profile).data)

    def patch(self, request):
        membership = _get_client_membership(request)
        profile, _ = ClientProfile.objects.get_or_create(membership=membership)
        serializer = ClientProfileDetailSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ClientAvatarUploadView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def post(self, request):
        serializer = ClientAvatarUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        avatar_file = serializer.validated_data['avatar']
        safe_name = os.path.basename(avatar_file.name)
        path = f'avatars/{request.user.pk}/{safe_name}'
        saved_path = default_storage.save(path, avatar_file)
        avatar_url = request.build_absolute_uri(f'/media/{saved_path}')
        request.user.avatar = avatar_url
        request.user.save(update_fields=['avatar'])
        return Response({'avatar': avatar_url})
