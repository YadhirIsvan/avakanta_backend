"""
Tests unitarios de AvailabilityService.

Cubren todos los casos del criterio T-079:
- Sin horario       → slots vacíos
- Break 14-15h      → slot 14:00 excluido
- Indisponibilidad  → todos los slots vacíos
- Cita en 10:00     → slot 10:00 excluido
- min_advance_hours → slots dentro de la ventana excluidos
"""
from datetime import date, timedelta

from django.test import TestCase

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership, AgentProfile
from apps.properties.models import Property, PropertyAssignment
from apps.appointments.models import (
    AgentSchedule, AgentUnavailability, Appointment,
    AppointmentSettings, ScheduleBreak,
)
from apps.appointments.services import AvailabilityService


def _next_monday():
    today = date.today()
    days_ahead = 7 - today.weekday()   # 1–7 (never 0)
    return today + timedelta(days=days_ahead)


class AvailabilityServiceTestCase(TestCase):
    """
    Fixture base: tenant, agente, propiedad y AppointmentSettings
    con min_advance_hours=0 para no interferir con los casos que
    no prueban ese filtro.
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Avail Tenant', slug='avail-tenant',
            email='avail@test.com', is_active=True,
        )
        self.settings = AppointmentSettings.objects.create(
            tenant=self.tenant,
            slot_duration_minutes=60,
            day_start_time='09:00',
            day_end_time='17:00',
            min_advance_hours=0,   # sin filtro de anticipación para la mayoría de tests
        )
        agent_user = User.objects.create(email='agent_avail@test.com', is_active=True)
        self.agent_m = TenantMembership.objects.create(
            user=agent_user, tenant=self.tenant,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        AgentProfile.objects.create(membership=self.agent_m)
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Casa Avail',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000, is_active=True,
        )
        PropertyAssignment.objects.create(
            property=self.prop, agent_membership=self.agent_m, is_visible=True,
        )
        self.svc = AvailabilityService()
        self.target = _next_monday()   # siempre un lunes futuro

    def _monday_schedule(self, **kwargs):
        """Helper: crea un horario de lunes con valores por defecto."""
        defaults = dict(
            tenant=self.tenant, agent_membership=self.agent_m,
            name='Lunes', monday=True,
            start_time='09:00', end_time='17:00',
            has_lunch_break=False, is_active=True,
        )
        defaults.update(kwargs)
        return AgentSchedule.objects.create(**defaults)

    # ── 1. Sin horario → slots vacíos ────────────────────────────────────────

    def test_no_schedule_returns_empty_slots(self):
        """Sin AgentSchedule para ese día → lista vacía."""
        # No se crea ningún horario
        result = self.svc.get_available_slots(self.prop.pk, self.target)
        self.assertEqual(result['available_slots'], [])

    def test_schedule_for_wrong_day_returns_empty_slots(self):
        """Horario solo para martes no aplica en lunes."""
        AgentSchedule.objects.create(
            tenant=self.tenant, agent_membership=self.agent_m,
            name='Martes', tuesday=True,
            start_time='09:00', end_time='17:00',
            has_lunch_break=False, is_active=True,
        )
        result = self.svc.get_available_slots(self.prop.pk, self.target)
        self.assertEqual(result['available_slots'], [])

    # ── 2. Break 14-15h → slot 14:00 excluido ────────────────────────────────

    def test_break_14_to_15_excludes_1400_slot(self):
        """ScheduleBreak 14:00-15:00 → 14:00 no disponible, 15:00 sí."""
        schedule = self._monday_schedule()
        ScheduleBreak.objects.create(
            schedule=schedule,
            break_type=ScheduleBreak.BreakType.REST,
            start_time='14:00',
            end_time='15:00',
        )
        result = self.svc.get_available_slots(self.prop.pk, self.target)
        slots = result['available_slots']
        self.assertGreater(len(slots), 0)
        self.assertNotIn('14:00', slots)
        self.assertIn('15:00', slots)

    def test_break_does_not_remove_adjacent_slots(self):
        """Break 14:00-15:00 no elimina 13:00 ni 15:00."""
        schedule = self._monday_schedule()
        ScheduleBreak.objects.create(
            schedule=schedule,
            break_type=ScheduleBreak.BreakType.LUNCH,
            start_time='14:00',
            end_time='15:00',
        )
        result = self.svc.get_available_slots(self.prop.pk, self.target)
        slots = result['available_slots']
        self.assertIn('13:00', slots)
        self.assertIn('15:00', slots)

    # ── 3. Indisponibilidad → todos los slots vacíos ──────────────────────────

    def test_unavailability_on_target_date_returns_empty_slots(self):
        """AgentUnavailability que cubre la fecha → lista vacía."""
        self._monday_schedule()
        AgentUnavailability.objects.create(
            tenant=self.tenant, agent_membership=self.agent_m,
            start_date=self.target,
            end_date=self.target,
            reason=AgentUnavailability.Reason.VACATION,
        )
        result = self.svc.get_available_slots(self.prop.pk, self.target)
        self.assertEqual(result['available_slots'], [])

    def test_unavailability_spanning_target_date_returns_empty_slots(self):
        """Unavailability que abarca la fecha también la bloquea."""
        self._monday_schedule()
        AgentUnavailability.objects.create(
            tenant=self.tenant, agent_membership=self.agent_m,
            start_date=self.target - timedelta(days=3),
            end_date=self.target + timedelta(days=3),
            reason=AgentUnavailability.Reason.SICK_LEAVE,
        )
        result = self.svc.get_available_slots(self.prop.pk, self.target)
        self.assertEqual(result['available_slots'], [])

    def test_unavailability_on_different_date_does_not_block(self):
        """Unavailability en otra fecha no afecta el día objetivo."""
        self._monday_schedule()
        AgentUnavailability.objects.create(
            tenant=self.tenant, agent_membership=self.agent_m,
            start_date=self.target + timedelta(days=7),
            end_date=self.target + timedelta(days=7),
            reason=AgentUnavailability.Reason.PERSONAL,
        )
        result = self.svc.get_available_slots(self.prop.pk, self.target)
        self.assertGreater(len(result['available_slots']), 0)

    # ── 4. Cita de 60min en 10:00 → slot 10:00 no disponible ─────────────────

    def test_existing_appointment_at_1000_removes_that_slot(self):
        """Appointment programada a las 10:00 → slot 10:00 excluido."""
        self._monday_schedule()
        Appointment.objects.create(
            tenant=self.tenant, property=self.prop,
            agent_membership=self.agent_m,
            matricula='CLI-2026-001',
            scheduled_date=self.target,
            scheduled_time='10:00',
            duration_minutes=60,
            status=Appointment.Status.PROGRAMADA,
        )
        result = self.svc.get_available_slots(self.prop.pk, self.target)
        slots = result['available_slots']
        self.assertNotIn('10:00', slots)
        self.assertIn('09:00', slots)
        self.assertIn('11:00', slots)

    def test_cancelled_appointment_does_not_block_slot(self):
        """Cita cancelada no bloquea el slot."""
        self._monday_schedule()
        Appointment.objects.create(
            tenant=self.tenant, property=self.prop,
            agent_membership=self.agent_m,
            matricula='CLI-2026-002',
            scheduled_date=self.target,
            scheduled_time='10:00',
            duration_minutes=60,
            status=Appointment.Status.CANCELADA,
        )
        result = self.svc.get_available_slots(self.prop.pk, self.target)
        self.assertIn('10:00', result['available_slots'])

    def test_reagendada_appointment_does_not_block_slot(self):
        """Cita reagendada no bloquea el slot."""
        self._monday_schedule()
        Appointment.objects.create(
            tenant=self.tenant, property=self.prop,
            agent_membership=self.agent_m,
            matricula='CLI-2026-003',
            scheduled_date=self.target,
            scheduled_time='10:00',
            duration_minutes=60,
            status=Appointment.Status.REAGENDADA,
        )
        result = self.svc.get_available_slots(self.prop.pk, self.target)
        self.assertIn('10:00', result['available_slots'])

    # ── 5. min_advance_hours → slots dentro de la ventana excluidos ───────────

    def test_min_advance_hours_excludes_slots_too_close_to_now(self):
        """
        Con min_advance_hours=24 y target_date=hoy, todos los slots
        del día quedan dentro de la ventana de 24h y deben ser excluidos.
        """
        # Actualizar settings del tenant a 24h de anticipación
        self.settings.min_advance_hours = 24
        self.settings.save()

        AgentSchedule.objects.create(
            tenant=self.tenant, agent_membership=self.agent_m,
            name='Hoy',
            **{_weekday_field(date.today()): True},
            start_time='09:00', end_time='17:00',
            has_lunch_break=False, is_active=True,
        )
        result = self.svc.get_available_slots(self.prop.pk, date.today())
        self.assertEqual(result['available_slots'], [])

    def test_min_advance_hours_zero_does_not_filter_future_slots(self):
        """Con min_advance_hours=0 los slots futuros no se filtran."""
        # settings ya tiene min_advance_hours=0
        self._monday_schedule()
        result = self.svc.get_available_slots(self.prop.pk, self.target)
        self.assertGreater(len(result['available_slots']), 0)

    # ── 6. Propiedad sin agente → agent=None ─────────────────────────────────

    def test_property_without_agent_returns_agent_none(self):
        """Propiedad sin PropertyAssignment is_visible=True → agent=None."""
        prop_no_agent = Property.objects.create(
            tenant=self.tenant, title='Sin agente',
            listing_type='sale', status='disponible',
            property_type='house', price=500_000, is_active=True,
        )
        result = self.svc.get_available_slots(prop_no_agent.pk, self.target)
        self.assertIsNone(result['agent'])
        self.assertEqual(result['available_slots'], [])


def _weekday_field(d):
    """Devuelve el nombre del campo boolean de AgentSchedule para el día d."""
    fields = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    return fields[d.weekday()]
