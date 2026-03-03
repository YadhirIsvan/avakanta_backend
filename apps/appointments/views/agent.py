from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import StandardPagination
from core.permissions import IsAgent
from apps.users.models import TenantMembership
from ..models import Appointment
from ..services import sync_purchase_process_on_appointment
from ..serializers.agent import (
    AgentAppointmentListSerializer,
    AgentAppointmentStatusSerializer,
    VALID_TRANSITIONS,
)


def _get_agent_membership(request):
    return TenantMembership.objects.get(
        user=request.user, tenant=request.tenant, is_active=True
    )


def _appointment_qs(membership):
    return (
        Appointment.objects
        .filter(agent_membership=membership)
        .select_related('property')
        .order_by('scheduled_date', 'scheduled_time')
    )


class AgentAppointmentListView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]
    pagination_class = StandardPagination

    def get(self, request):
        membership = _get_agent_membership(request)
        qs = _appointment_qs(membership)

        status = request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)

        date = request.query_params.get('date')
        if date:
            qs = qs.filter(scheduled_date=date)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            AgentAppointmentListSerializer(page, many=True).data
        )


class AgentAppointmentStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]

    def patch(self, request, pk):
        membership = _get_agent_membership(request)

        appointment = _appointment_qs(membership).filter(pk=pk).first()
        if not appointment:
            return Response({'error': 'Cita no encontrada.'}, status=404)

        serializer = AgentAppointmentStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        new_status = data['status']
        allowed = VALID_TRANSITIONS.get(appointment.status, [])
        if new_status not in allowed:
            return Response(
                {'error': f'Transición inválida: {appointment.status} → {new_status}.'},
                status=400,
            )

        appointment.status = new_status
        if data.get('notes'):
            appointment.notes = data['notes']
        appointment.save(update_fields=['status', 'notes', 'updated_at'])

        # Sync PurchaseProcess when status changes
        sync_purchase_process_on_appointment(appointment, is_new=False)

        return Response(AgentAppointmentListSerializer(appointment).data)
