from django.db.models import Count

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import StandardPagination
from core.permissions import IsAgent
from apps.users.models import TenantMembership
from apps.transactions.models import PurchaseProcess
from ..models import PropertyAssignment
from ..serializers.agent import AgentPropertyListSerializer, AgentPropertyLeadSerializer


def _get_agent_membership(request):
    return (
        TenantMembership.objects
        .select_related('user', 'agent_profile')
        .get(user=request.user, tenant=request.tenant, is_active=True)
    )


class AgentPropertyListView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]
    pagination_class = StandardPagination

    def get(self, request):
        membership = _get_agent_membership(request)

        qs = (
            PropertyAssignment.objects
            .filter(agent_membership=membership)
            .select_related(
                'property__city__state',
            )
            .prefetch_related('property__images')
            .annotate(
                leads_count=Count('property__purchase_processes', distinct=True)
            )
            .order_by('-assigned_at')
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            AgentPropertyListSerializer(page, many=True).data
        )


class AgentPropertyLeadsView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]
    pagination_class = StandardPagination

    def get(self, request, pk):
        membership = _get_agent_membership(request)

        # Verify the property is assigned to this agent
        assignment = PropertyAssignment.objects.filter(
            property_id=pk,
            agent_membership=membership,
        ).first()
        if not assignment:
            return Response({'error': 'Propiedad no encontrada o no asignada.'}, status=404)

        qs = (
            PurchaseProcess.objects
            .filter(tenant=request.tenant, property_id=pk, agent_membership=membership)
            .select_related('client_membership__user')
            .order_by('-created_at')
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            AgentPropertyLeadSerializer(page, many=True).data
        )
