from django.db import transaction
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import StandardPagination
from core.permissions import IsAdmin
from apps.users.models import TenantMembership
from ..models import PurchaseProcess, SaleProcess
from ..serializers.admin import (
    AdminPurchaseProcessListSerializer,
    AdminPurchaseProcessCreateSerializer,
    AdminPurchaseProcessStatusSerializer,
    AdminPurchaseProcessUpdateSerializer,
    AdminSaleProcessListSerializer,
    AdminSaleProcessCreateSerializer,
    AdminSaleProcessStatusSerializer,
)
from ..services import update_purchase_process_status, update_sale_process_status


def _purchase_qs(tenant):
    return (
        PurchaseProcess.objects
        .filter(tenant=tenant)
        .select_related(
            'property',
            'client_membership__user',
            'agent_membership__user',
            'agent_membership__agent_profile',
        )
        .prefetch_related('property__images')
        .order_by('-created_at')
    )


def _sale_qs(tenant):
    return (
        SaleProcess.objects
        .filter(tenant=tenant)
        .select_related(
            'property',
            'client_membership__user',
            'agent_membership__user',
            'agent_membership__agent_profile',
        )
        .prefetch_related('property__images')
        .order_by('-created_at')
    )


def _get_membership(pk, tenant, role=None):
    qs = TenantMembership.objects.filter(pk=pk, tenant=tenant, is_active=True)
    if role:
        qs = qs.filter(role=role)
    return qs.select_related('user', 'agent_profile').first()


# ── Purchase Process ──────────────────────────────────────────────────────────

class AdminPurchaseProcessListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardPagination

    def get(self, request):
        qs = _purchase_qs(request.tenant)

        status = request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)

        agent_id = request.query_params.get('agent_id')
        if agent_id:
            qs = qs.filter(agent_membership__agent_profile__pk=agent_id)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            AdminPurchaseProcessListSerializer(page, many=True).data
        )

    @transaction.atomic
    def post(self, request):
        serializer = AdminPurchaseProcessCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from apps.properties.models import Property
        prop = Property.objects.filter(pk=data['property_id'], tenant=request.tenant).first()
        if not prop:
            return Response({'error': 'Propiedad no encontrada.'}, status=400)

        client = _get_membership(data['client_membership_id'], request.tenant)
        if not client:
            return Response({'error': 'Cliente no encontrado.'}, status=400)

        agent = _get_membership(data['agent_membership_id'], request.tenant, role='agent')
        if not agent:
            return Response({'error': 'Agente no encontrado.'}, status=400)

        process = PurchaseProcess.objects.create(
            tenant=request.tenant,
            property=prop,
            client_membership=client,
            agent_membership=agent,
            status=PurchaseProcess.Status.LEAD,
            overall_progress=0,
            notes=data.get('notes', ''),
        )

        process = _purchase_qs(request.tenant).get(pk=process.pk)
        return Response(AdminPurchaseProcessListSerializer(process).data, status=201)


class AdminPurchaseProcessStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, pk):
        process = _purchase_qs(request.tenant).filter(pk=pk).first()
        if not process:
            return Response({'error': 'Proceso no encontrado.'}, status=404)

        serializer = AdminPurchaseProcessStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Resolve current membership for history
        from core.middleware import _authenticate_jwt
        membership = TenantMembership.objects.filter(
            user=request.user, tenant=request.tenant, is_active=True
        ).first()

        process = update_purchase_process_status(
            process=process,
            new_status=data['status'],
            notes=data.get('notes', ''),
            changed_by_membership=membership,
            sale_price=data.get('sale_price'),
            payment_method=data.get('payment_method', ''),
        )

        return Response({
            'id': process.pk,
            'status': process.status,
            'overall_progress': process.overall_progress,
            'updated_at': process.updated_at,
        })


class AdminPurchaseProcessDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, pk):
        process = _purchase_qs(request.tenant).filter(pk=pk).first()
        if not process:
            return Response({'error': 'Proceso no encontrado.'}, status=404)

        serializer = AdminPurchaseProcessUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        update_fields = []

        if 'agent_membership_id' in data:
            agent = _get_membership(data['agent_membership_id'], request.tenant, role='agent')
            if not agent:
                return Response({'error': 'Agente no encontrado.'}, status=400)
            process.agent_membership = agent
            update_fields.append('agent_membership')

        for field in ('notes', 'sale_price', 'payment_method'):
            if field in data:
                setattr(process, field, data[field])
                update_fields.append(field)

        if update_fields:
            update_fields.append('updated_at')
            process.save(update_fields=update_fields)

        process = _purchase_qs(request.tenant).get(pk=process.pk)
        return Response(AdminPurchaseProcessListSerializer(process).data)


# ── Sale Process ──────────────────────────────────────────────────────────────

class AdminSaleProcessListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardPagination

    def get(self, request):
        qs = _sale_qs(request.tenant)

        status = request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)

        agent_id = request.query_params.get('agent_id')
        if agent_id:
            qs = qs.filter(agent_membership__agent_profile__pk=agent_id)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            AdminSaleProcessListSerializer(page, many=True).data
        )

    @transaction.atomic
    def post(self, request):
        serializer = AdminSaleProcessCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from apps.properties.models import Property
        prop = Property.objects.filter(pk=data['property_id'], tenant=request.tenant).first()
        if not prop:
            return Response({'error': 'Propiedad no encontrada.'}, status=400)

        client = _get_membership(data['client_membership_id'], request.tenant)
        if not client:
            return Response({'error': 'Cliente no encontrado.'}, status=400)

        agent = None
        if data.get('agent_membership_id'):
            agent = _get_membership(data['agent_membership_id'], request.tenant, role='agent')
            if not agent:
                return Response({'error': 'Agente no encontrado.'}, status=400)

        process = SaleProcess.objects.create(
            tenant=request.tenant,
            property=prop,
            client_membership=client,
            agent_membership=agent,
            status=SaleProcess.Status.CONTACTO_INICIAL,
            notes=data.get('notes', ''),
        )

        process = _sale_qs(request.tenant).get(pk=process.pk)
        return Response(AdminSaleProcessListSerializer(process).data, status=201)


class AdminSaleProcessStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, pk):
        process = _sale_qs(request.tenant).filter(pk=pk).first()
        if not process:
            return Response({'error': 'Proceso no encontrado.'}, status=404)

        serializer = AdminSaleProcessStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        membership = TenantMembership.objects.filter(
            user=request.user, tenant=request.tenant, is_active=True
        ).first()

        process = update_sale_process_status(
            process=process,
            new_status=data['status'],
            notes=data.get('notes', ''),
            changed_by_membership=membership,
        )

        return Response({
            'id': process.pk,
            'status': process.status,
            'updated_at': process.updated_at,
        })
