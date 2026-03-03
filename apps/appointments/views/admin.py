from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import StandardPagination
from core.permissions import IsAdmin
from core.utils import generate_matricula
from apps.users.models import AgentProfile, TenantMembership
from ..models import Appointment, AgentSchedule, AgentUnavailability, AppointmentSettings, ScheduleBreak
from ..serializers.admin import (
    AdminAgentScheduleSerializer,
    AdminAgentScheduleInputSerializer,
    AdminAgentUnavailabilitySerializer,
    AdminAgentUnavailabilityInputSerializer,
    AdminAppointmentListSerializer,
    AdminAppointmentCreateSerializer,
    AdminAppointmentUpdateSerializer,
)
from ..services import AvailabilityService, sync_purchase_process_on_appointment


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


# ── helpers ──────────────────────────────────────────────────────────────────

def _check_slot_available(agent_membership_id, tenant, target_date, target_time,
                           duration, exclude_id=None):
    """
    Returns (True, None) if the slot is available,
    or (False, error_message) if not.
    """
    svc = AvailabilityService()

    if svc.check_unavailability(agent_membership_id, target_date):
        return False, 'El agente no está disponible en esa fecha.'

    schedule = svc.get_active_schedule_for_day(agent_membership_id, target_date)
    if not schedule:
        return False, 'El agente no tiene horario activo ese día.'

    try:
        settings = AppointmentSettings.objects.get(tenant=tenant)
        slot_duration = settings.slot_duration_minutes
    except AppointmentSettings.DoesNotExist:
        slot_duration = duration or 60

    if target_time < schedule.start_time or target_time >= schedule.end_time:
        return False, 'El horario está fuera del rango de trabajo del agente.'

    breaks = list(schedule.breaks.values('start_time', 'end_time'))
    if svc._slot_in_break(target_time, slot_duration, breaks):
        return False, 'El horario coincide con un descanso del agente.'

    existing = svc.get_existing_appointments(agent_membership_id, target_date, exclude_id)
    if svc._slot_conflicts(target_time, slot_duration, existing):
        return False, 'El horario ya está ocupado por otra cita.'

    return True, None


def _appointment_queryset(tenant):
    return (
        Appointment.objects
        .filter(tenant=tenant)
        .select_related(
            'property',
            'agent_membership__user',
            'agent_membership__agent_profile',
        )
        .order_by('-scheduled_date', '-scheduled_time')
    )


# ── Appointments ──────────────────────────────────────────────────────────────

class AdminAppointmentListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardPagination

    def get(self, request):
        qs = _appointment_queryset(request.tenant)

        date = request.query_params.get('date')
        if date:
            qs = qs.filter(scheduled_date=date)

        agent_id = request.query_params.get('agent_id')
        if agent_id:
            qs = qs.filter(agent_membership__agent_profile__pk=agent_id)

        status = request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)

        search = request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(matricula__icontains=search) | Q(client_name__icontains=search)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            AdminAppointmentListSerializer(page, many=True).data
        )

    @transaction.atomic
    def post(self, request):
        serializer = AdminAppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Validate property belongs to tenant
        from apps.properties.models import Property
        prop = Property.objects.filter(pk=data['property_id'], tenant=request.tenant).first()
        if not prop:
            return Response({'error': 'Propiedad no encontrada.'}, status=400)

        # Validate agent membership belongs to tenant
        agent_membership = TenantMembership.objects.filter(
            pk=data['agent_membership_id'], tenant=request.tenant, role='agent', is_active=True
        ).select_related('user', 'agent_profile').first()
        if not agent_membership:
            return Response({'error': 'Agente no encontrado.'}, status=400)

        # Validate slot availability
        ok, error = _check_slot_available(
            agent_membership.pk, request.tenant,
            data['scheduled_date'], data['scheduled_time'],
            data.get('duration_minutes'),
        )
        if not ok:
            return Response({'error': error}, status=400)

        # Resolve optional client membership
        client_membership = None
        if data.get('client_membership_id'):
            client_membership = TenantMembership.objects.filter(
                pk=data['client_membership_id'], tenant=request.tenant
            ).first()

        matricula = generate_matricula(request.tenant.pk)
        appointment = Appointment.objects.create(
            tenant=request.tenant,
            property=prop,
            agent_membership=agent_membership,
            client_membership=client_membership,
            matricula=matricula,
            scheduled_date=data['scheduled_date'],
            scheduled_time=data['scheduled_time'],
            duration_minutes=data.get('duration_minutes'),
            appointment_type=data.get('appointment_type', Appointment.AppointmentType.PRIMERA_VISITA),
            notes=data.get('notes', ''),
        )

        # Auto-create PurchaseProcess if this is a primera_visita
        sync_purchase_process_on_appointment(appointment, is_new=True)

        appt = _appointment_queryset(request.tenant).get(pk=appointment.pk)
        return Response(AdminAppointmentListSerializer(appt).data, status=201)


class AdminAppointmentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, pk):
        appt = _appointment_queryset(request.tenant).filter(pk=pk).first()
        if not appt:
            return Response({'error': 'Cita no encontrada.'}, status=404)

        serializer = AdminAppointmentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # If date or time is changing, re-validate availability
        new_date = data.get('scheduled_date', appt.scheduled_date)
        new_time = data.get('scheduled_time', appt.scheduled_time)
        date_or_time_changed = (
            'scheduled_date' in data or 'scheduled_time' in data
        )
        if date_or_time_changed:
            ok, error = _check_slot_available(
                appt.agent_membership_id, request.tenant,
                new_date, new_time,
                data.get('duration_minutes', appt.duration_minutes),
                exclude_id=appt.pk,
            )
            if not ok:
                return Response({'error': error}, status=400)

        update_fields = []
        status_changed = 'status' in data
        for field in ('status', 'scheduled_date', 'scheduled_time',
                      'duration_minutes', 'notes', 'cancellation_reason'):
            if field in data:
                setattr(appt, field, data[field])
                update_fields.append(field)

        if update_fields:
            appt.save(update_fields=update_fields)

        # Sync PurchaseProcess when the appointment status changes
        if status_changed:
            sync_purchase_process_on_appointment(appt, is_new=False)

        appt = _appointment_queryset(request.tenant).get(pk=appt.pk)
        return Response(AdminAppointmentListSerializer(appt).data)

    def delete(self, request, pk):
        appt = Appointment.objects.filter(pk=pk, tenant=request.tenant).first()
        if not appt:
            return Response({'error': 'Cita no encontrada.'}, status=404)
        appt.delete()
        return Response(status=204)


class AdminAppointmentAvailabilityView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        agent_id = request.query_params.get('agent_id')
        date_str = request.query_params.get('date')
        exclude_id = request.query_params.get('exclude_appointment_id')

        if not agent_id or not date_str:
            return Response({'error': 'agent_id y date son requeridos.'}, status=400)

        # Resolve AgentProfile → membership
        agent = AgentProfile.objects.filter(
            pk=agent_id,
            membership__tenant=request.tenant,
            membership__is_active=True,
            membership__role='agent',
        ).select_related('membership').first()
        if not agent:
            return Response({'error': 'Agente no encontrado.'}, status=404)

        try:
            from datetime import date
            target_date = date.fromisoformat(date_str)
        except ValueError:
            return Response({'error': 'Formato de fecha inválido. Use YYYY-MM-DD.'}, status=400)

        svc = AvailabilityService()

        try:
            settings = AppointmentSettings.objects.get(tenant=request.tenant)
            slot_duration = settings.slot_duration_minutes
        except AppointmentSettings.DoesNotExist:
            slot_duration = 60

        if svc.check_unavailability(agent.membership_id, target_date):
            return Response({'available_slots': [], 'slot_duration_minutes': slot_duration})

        schedule = svc.get_active_schedule_for_day(agent.membership_id, target_date)
        if not schedule:
            return Response({'available_slots': [], 'slot_duration_minutes': slot_duration})

        slots = svc._generate_slots(schedule.start_time, schedule.end_time, slot_duration)
        breaks = list(schedule.breaks.values('start_time', 'end_time'))
        slots = [s for s in slots if not svc._slot_in_break(s, slot_duration, breaks)]

        exclude_appointment_id = int(exclude_id) if exclude_id else None
        existing = svc.get_existing_appointments(
            agent.membership_id, target_date, exclude_appointment_id
        )
        slots = [s for s in slots if not svc._slot_conflicts(s, slot_duration, existing)]

        return Response({
            'available_slots': [s.strftime('%H:%M') for s in slots],
            'slot_duration_minutes': slot_duration,
        })
