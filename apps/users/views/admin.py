from django.db import transaction
from django.db.models import Count, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import StandardPagination
from core.permissions import IsAdmin
from ..models import AgentProfile, TenantMembership, User
from ..serializers.admin import (
    AdminAgentListSerializer,
    AdminAgentDetailSerializer,
    AdminAgentCreateSerializer,
    AdminClientListSerializer,
    AdminClientDetailSerializer,
)


def _agent_queryset(tenant):
    return (
        AgentProfile.objects
        .filter(
            membership__tenant=tenant,
            membership__is_active=True,
            membership__role=TenantMembership.Role.AGENT,
        )
        .select_related('membership__user')
        .annotate(
            properties_count=Count('membership__property_assignments', distinct=True),
            sales_count=Count(
                'membership__agent_purchase_processes',
                filter=Q(membership__agent_purchase_processes__status='cerrado'),
                distinct=True,
            ),
            leads_count=Count('membership__agent_purchase_processes', distinct=True),
            active_leads=Count(
                'membership__agent_purchase_processes',
                filter=~Q(membership__agent_purchase_processes__status__in=['cerrado', 'cancelado']),
                distinct=True,
            ),
        )
    )


class AdminAgentListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardPagination

    def get(self, request):
        qs = _agent_queryset(request.tenant).order_by('membership__user__first_name')
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = AdminAgentListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @transaction.atomic
    def post(self, request):
        serializer = AdminAgentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        email = data['email']
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        phone = data.get('phone', '')
        zone = data.get('zone', '')
        bio = data.get('bio', '')

        # Get or create the user
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone or None,
            },
        )

        # Check if membership already exists
        if TenantMembership.objects.filter(user=user, tenant=request.tenant).exists():
            return Response({'error': 'Este usuario ya tiene una membresía en este tenant.'}, status=400)

        membership = TenantMembership.objects.create(
            user=user,
            tenant=request.tenant,
            role=TenantMembership.Role.AGENT,
            is_active=True,
        )

        agent_profile = AgentProfile.objects.create(
            membership=membership,
            zone=zone or None,
            bio=bio or None,
        )

        # Load with annotations for response
        agent = _agent_queryset(request.tenant).get(pk=agent_profile.pk)
        return Response(AdminAgentDetailSerializer(agent).data, status=201)


class AdminAgentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def _get_agent(self, request, pk):
        return _agent_queryset(request.tenant).filter(pk=pk).first()

    def get(self, request, pk):
        agent = self._get_agent(request, pk)
        if not agent:
            return Response({'error': 'Agente no encontrado.'}, status=404)
        return Response(AdminAgentDetailSerializer(agent).data)

    def patch(self, request, pk):
        agent = self._get_agent(request, pk)
        if not agent:
            return Response({'error': 'Agente no encontrado.'}, status=404)

        # Updatable user fields
        user = agent.membership.user
        user_fields = ('first_name', 'last_name', 'phone')
        user_changed = False
        for field in user_fields:
            if field in request.data:
                setattr(user, field, request.data[field])
                user_changed = True
        if user_changed:
            user.save(update_fields=[f for f in user_fields if f in request.data])

        # Updatable profile fields
        profile_fields = ('zone', 'bio', 'score')
        profile_changed = False
        for field in profile_fields:
            if field in request.data:
                setattr(agent, field, request.data[field])
                profile_changed = True
        if profile_changed:
            agent.save(update_fields=[f for f in profile_fields if f in request.data])

        # Reload with annotations
        agent = self._get_agent(request, pk)
        return Response(AdminAgentDetailSerializer(agent).data)

    def delete(self, request, pk):
        agent = self._get_agent(request, pk)
        if not agent:
            return Response({'error': 'Agente no encontrado.'}, status=404)
        membership = agent.membership
        membership.is_active = False
        membership.save(update_fields=['is_active'])
        return Response(status=204)


def _client_queryset(tenant):
    return (
        TenantMembership.objects
        .filter(tenant=tenant, role=TenantMembership.Role.CLIENT, is_active=True)
        .select_related('user')
        .annotate(
            purchase_processes_count=Count('client_purchase_processes', distinct=True),
            sale_processes_count=Count('client_sale_processes', distinct=True),
        )
    )


class AdminClientListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardPagination

    def get(self, request):
        qs = _client_queryset(request.tenant)

        search = request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search)
            )

        qs = qs.order_by('user__first_name', 'user__last_name')
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            AdminClientListSerializer(page, many=True).data
        )


class AdminClientDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, pk):
        # pk = User.pk
        membership = (
            TenantMembership.objects
            .filter(tenant=request.tenant, role=TenantMembership.Role.CLIENT,
                    is_active=True, user__pk=pk)
            .select_related('user')
            .first()
        )
        if not membership:
            return Response({'error': 'Cliente no encontrado.'}, status=404)
        return Response(AdminClientDetailSerializer(membership).data)
