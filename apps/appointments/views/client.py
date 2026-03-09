from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import TenantMembership
from core.permissions import IsClient
from ..models import Appointment
from ..serializers.client import ClientAppointmentListSerializer


class ClientAppointmentListView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def get(self, request):
        membership = TenantMembership.objects.get(
            user=request.user, tenant=request.tenant, is_active=True
        )
        appointments = (
            Appointment.objects
            .filter(client_membership=membership)
            .select_related(
                'property__city',
                'agent_membership__user',
            )
            .prefetch_related('property__images')
            .order_by('-scheduled_date', '-scheduled_time')
        )

        serializer = ClientAppointmentListSerializer(appointments, many=True, context={'request': request})
        return Response(serializer.data)


class ClientAppointmentCancelView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def patch(self, request, pk):
        membership = TenantMembership.objects.get(
            user=request.user, tenant=request.tenant, is_active=True
        )
        try:
            appointment = Appointment.objects.get(
                pk=pk, client_membership=membership
            )
        except Appointment.DoesNotExist:
            return Response({'error': 'Cita no encontrada.'}, status=404)

        # Only allow cancelling if not already in a terminal state
        terminal = {
            Appointment.Status.COMPLETADA,
            Appointment.Status.CANCELADA,
            Appointment.Status.NO_SHOW,
        }
        if appointment.status in terminal:
            return Response(
                {'error': 'Esta cita no se puede cancelar.'},
                status=400,
            )

        appointment.status = Appointment.Status.CANCELADA
        appointment.cancellation_reason = request.data.get('reason', 'Cancelada por el cliente')
        appointment.save(update_fields=['status', 'cancellation_reason', 'updated_at'])

        serializer = ClientAppointmentListSerializer(appointment, context={'request': request})
        return Response(serializer.data)
