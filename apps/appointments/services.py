from datetime import datetime, date, time, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import AgentSchedule, AgentUnavailability, Appointment, AppointmentSettings


# Mapping from Python weekday() (0=Monday) to schedule field name
_WEEKDAY_FIELD = {
    0: 'monday',
    1: 'tuesday',
    2: 'wednesday',
    3: 'thursday',
    4: 'friday',
    5: 'saturday',
    6: 'sunday',
}


class AvailabilityService:

    def get_active_schedule_for_day(self, agent_membership_id: int, target_date: date):
        """
        Returns the highest-priority active AgentSchedule for the agent on
        target_date's weekday, or None if no schedule covers that day.
        """
        weekday_field = _WEEKDAY_FIELD[target_date.weekday()]

        return (
            AgentSchedule.objects
            .filter(
                agent_membership_id=agent_membership_id,
                is_active=True,
                **{weekday_field: True},
            )
            .filter(Q(valid_from__isnull=True) | Q(valid_from__lte=target_date))
            .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=target_date))
            .order_by('-priority')
            .prefetch_related('breaks')
            .first()
        )

    def check_unavailability(self, agent_membership_id: int, target_date: date) -> bool:
        """Returns True if the agent is marked unavailable on target_date."""
        return AgentUnavailability.objects.filter(
            agent_membership_id=agent_membership_id,
            start_date__lte=target_date,
            end_date__gte=target_date,
        ).exists()

    def get_existing_appointments(self, agent_membership_id: int, target_date: date,
                                  exclude_appointment_id: int = None):
        """Returns confirmed/scheduled appointments for the agent on target_date."""
        qs = Appointment.objects.filter(
            agent_membership_id=agent_membership_id,
            scheduled_date=target_date,
        ).exclude(status__in=['cancelada', 'no_show', 'reagendada'])

        if exclude_appointment_id:
            qs = qs.exclude(pk=exclude_appointment_id)

        return list(qs.values('scheduled_time', 'duration_minutes'))

    def get_available_slots(self, property_id: int, target_date: date,
                            exclude_appointment_id: int = None) -> dict:
        """
        Returns available time slots for the property's visible agent on target_date.

        Logic:
        1. Find the visible agent assignment for the property.
        2. Load AppointmentSettings for the tenant.
        3. If agent is unavailable → return empty slots.
        4. Get active schedule for the day → if none → return empty slots.
        5. Generate candidate slots within schedule's start/end.
        6. Remove slots blocked by schedule breaks.
        7. Remove slots blocked by existing appointments.
        8. Remove slots in the past or within min_advance_hours from now.
        """
        from apps.properties.models import Property, PropertyAssignment

        # 1. Find property and its visible agent
        try:
            prop = Property.objects.select_related('tenant').get(pk=property_id)
        except Property.DoesNotExist:
            return {'available_slots': [], 'slot_duration_minutes': 60, 'agent': None}

        assignment = (
            PropertyAssignment.objects
            .filter(property=prop, is_visible=True)
            .select_related('agent_membership__user')
            .first()
        )
        if not assignment:
            return {'available_slots': [], 'slot_duration_minutes': 60, 'agent': None}

        agent_membership_id = assignment.agent_membership_id
        agent_user = assignment.agent_membership.user

        # 2. Load AppointmentSettings
        try:
            settings = AppointmentSettings.objects.get(tenant=prop.tenant)
        except AppointmentSettings.DoesNotExist:
            return {'available_slots': [], 'slot_duration_minutes': 60,
                    'agent': {'name': agent_user.get_full_name() or agent_user.email}}

        slot_duration = settings.slot_duration_minutes

        # 3. Check unavailability
        if self.check_unavailability(agent_membership_id, target_date):
            return {
                'available_slots': [],
                'slot_duration_minutes': slot_duration,
                'agent': {'name': agent_user.get_full_name() or agent_user.email},
            }

        # 4. Get active schedule for the day
        schedule = self.get_active_schedule_for_day(agent_membership_id, target_date)
        if not schedule:
            return {
                'available_slots': [],
                'slot_duration_minutes': slot_duration,
                'agent': {'name': agent_user.get_full_name() or agent_user.email},
            }

        # 5. Generate candidate slots
        slots = self._generate_slots(schedule.start_time, schedule.end_time, slot_duration)

        # 6. Remove slots blocked by breaks
        breaks = list(schedule.breaks.values('start_time', 'end_time'))
        slots = [s for s in slots if not self._slot_in_break(s, slot_duration, breaks)]

        # 7. Remove slots occupied by existing appointments
        existing = self.get_existing_appointments(
            agent_membership_id, target_date, exclude_appointment_id
        )
        slots = [s for s in slots if not self._slot_conflicts(s, slot_duration, existing)]

        # 8. Remove past slots and those within min_advance_hours
        now = timezone.now()
        cutoff = now + timedelta(hours=settings.min_advance_hours)
        slots = [
            s for s in slots
            if datetime.combine(target_date, s, tzinfo=timezone.get_current_timezone()) >= cutoff
        ]

        return {
            'available_slots': [s.strftime('%H:%M') for s in slots],
            'slot_duration_minutes': slot_duration,
            'agent': {'name': agent_user.get_full_name() or agent_user.email},
        }

    # ---- private helpers ----

    def _generate_slots(self, start: time, end: time, duration_minutes: int) -> list:
        """Generate candidate slot start times between start and end."""
        slots = []
        current = datetime.combine(date.today(), start)
        limit = datetime.combine(date.today(), end)
        delta = timedelta(minutes=duration_minutes)
        while current + delta <= limit:
            slots.append(current.time())
            current += delta
        return slots

    def _slot_in_break(self, slot: time, duration_minutes: int, breaks: list) -> bool:
        """Returns True if the slot overlaps with any break."""
        slot_end = (datetime.combine(date.today(), slot)
                    + timedelta(minutes=duration_minutes)).time()
        for br in breaks:
            br_start = br['start_time']
            br_end = br['end_time']
            if slot < br_end and slot_end > br_start:
                return True
        return False

    def _slot_conflicts(self, slot: time, duration_minutes: int, appointments: list) -> bool:
        """Returns True if the slot overlaps with any existing appointment."""
        slot_end = (datetime.combine(date.today(), slot)
                    + timedelta(minutes=duration_minutes)).time()
        for appt in appointments:
            appt_start = appt['scheduled_time']
            appt_dur = appt['duration_minutes'] or duration_minutes
            appt_end = (datetime.combine(date.today(), appt_start)
                        + timedelta(minutes=appt_dur)).time()
            if slot < appt_end and slot_end > appt_start:
                return True
        return False


# ── Purchase-Process auto-sync ────────────────────────────────────────────────

PURCHASE_PROGRESS = {
    'lead':   0,
    'visita': 11,
}

# Statuses that push PurchaseProcess → visita
_VISITA_STATUSES = {
    Appointment.Status.EN_PROGRESO,
    Appointment.Status.COMPLETADA,
}

# Statuses that push PurchaseProcess back → lead
_LEAD_STATUSES = {
    Appointment.Status.PROGRAMADA,
    Appointment.Status.CONFIRMADA,
    Appointment.Status.CANCELADA,
    Appointment.Status.NO_SHOW,
}


@transaction.atomic
def sync_purchase_process_on_appointment(appointment, is_new=False):
    """
    Syncs PurchaseProcess state when a 'primera_visita' appointment is
    created or its status changes.

    On create (is_new=True):
      - If type is primera_visita and client_membership is set:
          • No active process for that client+property → create one in 'lead',
            keep appointment type as primera_visita.
          • Active process already exists → downgrade appointment type to 'seguimiento'.

    On status update (is_new=False):
      - If type is primera_visita:
          • New status in {en_progreso, completada} → push process to 'visita'.
          • New status in {programada, confirmada, cancelada, no_show}
            → push process back to 'lead' (only if it was in 'visita').
    """
    from apps.transactions.models import PurchaseProcess

    # Only meaningful when we know which client this appointment belongs to
    if not appointment.client_membership_id:
        return

    Appt = Appointment

    if is_new:
        if appointment.appointment_type != Appt.AppointmentType.PRIMERA_VISITA:
            return

        existing = PurchaseProcess.objects.filter(
            tenant=appointment.tenant,
            property=appointment.property,
            client_membership=appointment.client_membership,
        ).exclude(status='cancelado').first()

        if existing:
            # A process already exists → this is a follow-up, not a first visit
            appointment.appointment_type = Appt.AppointmentType.SEGUIMIENTO
            appointment.save(update_fields=['appointment_type'])
        else:
            # First time → create a new process in lead
            PurchaseProcess.objects.create(
                tenant=appointment.tenant,
                property=appointment.property,
                client_membership=appointment.client_membership,
                agent_membership=appointment.agent_membership,
                status=PurchaseProcess.Status.LEAD,
                overall_progress=PURCHASE_PROGRESS['lead'],
                notes='Creado automáticamente al agendar primera visita.',
            )
        return

    # ── Status-change sync (only for primera_visita appointments) ──
    if appointment.appointment_type != Appt.AppointmentType.PRIMERA_VISITA:
        return

    process = PurchaseProcess.objects.filter(
        tenant=appointment.tenant,
        property=appointment.property,
        client_membership=appointment.client_membership,
    ).exclude(status='cancelado').first()

    if not process:
        return

    if appointment.status in _VISITA_STATUSES:
        if process.status == PurchaseProcess.Status.LEAD:
            process.status = PurchaseProcess.Status.VISITA
            process.overall_progress = PURCHASE_PROGRESS['visita']
            process.save(update_fields=['status', 'overall_progress', 'updated_at'])

    elif appointment.status in _LEAD_STATUSES:
        if process.status == PurchaseProcess.Status.VISITA:
            process.status = PurchaseProcess.Status.LEAD
            process.overall_progress = PURCHASE_PROGRESS['lead']
            process.save(update_fields=['status', 'overall_progress', 'updated_at'])
