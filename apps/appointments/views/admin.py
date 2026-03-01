from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAdmin
from apps.users.models import AgentProfile
from ..models import AgentSchedule, AgentUnavailability, ScheduleBreak
from ..serializers.admin import (
    AdminAgentScheduleSerializer,
    AdminAgentScheduleInputSerializer,
    AdminAgentUnavailabilitySerializer,
    AdminAgentUnavailabilityInputSerializer,
)


def _get_agent_profile(pk, tenant):
    return AgentProfile.objects.filter(
        pk=pk,
        membership__tenant=tenant,
        membership__is_active=True,
        membership__role='agent',
    ).select_related('membership').first()


class AdminAgentScheduleListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, agent_id):
        agent = _get_agent_profile(agent_id, request.tenant)
        if not agent:
            return Response({'error': 'Agente no encontrado.'}, status=404)
        schedules = (
            AgentSchedule.objects
            .filter(agent_membership=agent.membership)
            .prefetch_related('breaks')
            .order_by('-priority', 'id')
        )
        return Response(AdminAgentScheduleSerializer(schedules, many=True).data)

    @transaction.atomic
    def post(self, request, agent_id):
        agent = _get_agent_profile(agent_id, request.tenant)
        if not agent:
            return Response({'error': 'Agente no encontrado.'}, status=404)

        serializer = AdminAgentScheduleInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        breaks_data = data.pop('breaks', [])
        schedule = AgentSchedule.objects.create(
            tenant=request.tenant,
            agent_membership=agent.membership,
            **data,
        )
        for b in breaks_data:
            ScheduleBreak.objects.create(schedule=schedule, **b)

        schedule.refresh_from_db()
        schedule_out = AgentSchedule.objects.prefetch_related('breaks').get(pk=schedule.pk)
        return Response(AdminAgentScheduleSerializer(schedule_out).data, status=201)


class AdminAgentScheduleDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def _get_schedule(self, agent, schedule_id):
        return AgentSchedule.objects.filter(
            pk=schedule_id, agent_membership=agent.membership
        ).first()

    def patch(self, request, agent_id, schedule_id):
        agent = _get_agent_profile(agent_id, request.tenant)
        if not agent:
            return Response({'error': 'Agente no encontrado.'}, status=404)

        schedule = self._get_schedule(agent, schedule_id)
        if not schedule:
            return Response({'error': 'Horario no encontrado.'}, status=404)

        serializer = AdminAgentScheduleInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        breaks_data = data.pop('breaks', None)

        with transaction.atomic():
            schedule_fields = [k for k in data]
            for field, value in data.items():
                setattr(schedule, field, value)
            if schedule_fields:
                schedule.save(update_fields=schedule_fields)

            if breaks_data is not None:
                schedule.breaks.all().delete()
                for b in breaks_data:
                    ScheduleBreak.objects.create(schedule=schedule, **b)

        schedule_out = AgentSchedule.objects.prefetch_related('breaks').get(pk=schedule.pk)
        return Response(AdminAgentScheduleSerializer(schedule_out).data)

    def delete(self, request, agent_id, schedule_id):
        agent = _get_agent_profile(agent_id, request.tenant)
        if not agent:
            return Response({'error': 'Agente no encontrado.'}, status=404)

        schedule = self._get_schedule(agent, schedule_id)
        if not schedule:
            return Response({'error': 'Horario no encontrado.'}, status=404)

        schedule.delete()
        return Response(status=204)


class AdminAgentUnavailabilityListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, agent_id):
        agent = _get_agent_profile(agent_id, request.tenant)
        if not agent:
            return Response({'error': 'Agente no encontrado.'}, status=404)
        unavailabilities = AgentUnavailability.objects.filter(
            agent_membership=agent.membership
        ).order_by('start_date')
        return Response(AdminAgentUnavailabilitySerializer(unavailabilities, many=True).data)

    def post(self, request, agent_id):
        agent = _get_agent_profile(agent_id, request.tenant)
        if not agent:
            return Response({'error': 'Agente no encontrado.'}, status=404)

        serializer = AdminAgentUnavailabilityInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        unavailability = AgentUnavailability.objects.create(
            tenant=request.tenant,
            agent_membership=agent.membership,
            **data,
        )
        return Response(AdminAgentUnavailabilitySerializer(unavailability).data, status=201)


class AdminAgentUnavailabilityDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, agent_id, unavailability_id):
        agent = _get_agent_profile(agent_id, request.tenant)
        if not agent:
            return Response({'error': 'Agente no encontrado.'}, status=404)

        try:
            unavailability = AgentUnavailability.objects.get(
                pk=unavailability_id, agent_membership=agent.membership
            )
        except AgentUnavailability.DoesNotExist:
            return Response({'error': 'Indisponibilidad no encontrada.'}, status=404)

        unavailability.delete()
        return Response(status=204)
