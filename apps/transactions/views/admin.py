from django.db import transaction
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import StandardPagination
from core.permissions import IsAdmin
from apps.users.models import TenantMembership
from ..models import PurchaseProcess, SaleProcess, SellerLead
from ..serializers.admin import (
    AdminPurchaseProcessListSerializer,
    AdminPurchaseProcessCreateSerializer,
    AdminPurchaseProcessStatusSerializer,
    AdminPurchaseProcessUpdateSerializer,
    AdminSaleProcessListSerializer,
    AdminSaleProcessCreateSerializer,
    AdminSaleProcessStatusSerializer,
    AdminSellerLeadListSerializer,
    AdminSellerLeadDetailSerializer,
    AdminSellerLeadUpdateSerializer,
    AdminSellerLeadConvertSerializer,
)
from ..services import (
    update_purchase_process_status,
    update_sale_process_status,
    convert_seller_lead,
)


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


# ── Seller Leads ──────────────────────────────────────────────────────────────

def _lead_qs(tenant):
    return (
        SellerLead.objects
        .filter(tenant=tenant)
        .select_related('assigned_agent_membership__user', 'assigned_agent_membership__agent_profile')
        .order_by('-created_at')
    )


class AdminSellerLeadListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardPagination

    def get(self, request):
        qs = _lead_qs(request.tenant)

        status = request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)

        search = request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(full_name__icontains=search) | Q(email__icontains=search)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            AdminSellerLeadListSerializer(page, many=True).data
        )


class AdminSellerLeadDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, pk):
        lead = _lead_qs(request.tenant).filter(pk=pk).first()
        if not lead:
            return Response({'error': 'Seller lead no encontrado.'}, status=404)
        return Response(AdminSellerLeadDetailSerializer(lead).data)

    def patch(self, request, pk):
        lead = _lead_qs(request.tenant).filter(pk=pk).first()
        if not lead:
            return Response({'error': 'Seller lead no encontrado.'}, status=404)

        serializer = AdminSellerLeadUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        update_fields = []

        if 'status' in data:
            lead.status = data['status']
            update_fields.append('status')

        if 'assigned_agent_membership_id' in data:
            if data['assigned_agent_membership_id'] is None:
                lead.assigned_agent_membership = None
            else:
                agent = TenantMembership.objects.filter(
                    pk=data['assigned_agent_membership_id'],
                    tenant=request.tenant, role='agent', is_active=True
                ).first()
                if not agent:
                    return Response({'error': 'Agente no encontrado.'}, status=400)
                lead.assigned_agent_membership = agent
            update_fields.append('assigned_agent_membership')

        if 'notes' in data:
            lead.notes = data['notes']
            update_fields.append('notes')

        if update_fields:
            update_fields.append('updated_at')
            lead.save(update_fields=update_fields)

        lead = _lead_qs(request.tenant).get(pk=lead.pk)
        return Response(AdminSellerLeadDetailSerializer(lead).data)


class AdminSellerLeadConvertView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        lead = SellerLead.objects.filter(pk=pk, tenant=request.tenant).first()
        if not lead:
            return Response({'error': 'Seller lead no encontrado.'}, status=404)

        if lead.status == SellerLead.Status.CONVERTED:
            return Response({'error': 'Este lead ya fue convertido.'}, status=400)

        serializer = AdminSellerLeadConvertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        agent = TenantMembership.objects.filter(
            pk=data['agent_membership_id'], tenant=request.tenant, role='agent', is_active=True
        ).first()
        if not agent:
            return Response({'error': 'Agente no encontrado.'}, status=400)

        prop, sale_process = convert_seller_lead(lead=lead, agent_membership=agent)

        return Response({
            'property_id': prop.pk,
            'sale_process_id': sale_process.pk,
            'message': 'Lead convertido. Se creó la propiedad y el proceso de venta.',
        }, status=201)
