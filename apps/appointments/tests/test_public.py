from datetime import date, timedelta

from rest_framework.test import APITestCase

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership, AgentProfile
from apps.properties.models import Property, PropertyAssignment
from apps.appointments.models import AgentSchedule, AppointmentSettings, Appointment


SLOTS_URL = '/api/v1/public/appointment/slots'


def _book_url(property_pk):
    return f'/api/v1/public/properties/{property_pk}/appointment'


# Use a Monday far enough in the future
def _next_monday():
    today = date.today()
    days_ahead = 7 - today.weekday()  # days until next Monday
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


class AppointmentSlotsTestCase(APITestCase):
    """Tests for GET /public/appointment/slots."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Slots Tenant', slug='slots-tenant',
            email='slots@test.com', is_active=True,
        )
        AppointmentSettings.objects.create(
            tenant=self.tenant,
            slot_duration_minutes=60,
            day_start_time='09:00',
            day_end_time='17:00',
            min_advance_hours=0,
        )
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Casa slots',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000, is_active=True,
        )
        agent_user = User.objects.create(email='agent_slots@test.com', is_active=True)
        self.agent_m = TenantMembership.objects.create(
            user=agent_user, tenant=self.tenant,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        AgentProfile.objects.create(membership=self.agent_m)
        PropertyAssignment.objects.create(
            property=self.prop, agent_membership=self.agent_m, is_visible=True,
        )
        # Monday schedule (weekday 0)
        AgentSchedule.objects.create(
            tenant=self.tenant, agent_membership=self.agent_m,
            name='Lunes', monday=True,
            start_time='09:00', end_time='17:00',
            has_lunch_break=False, is_active=True,
        )
        self.target_date = _next_monday()

    def test_slots_returns_available_times(self):
        resp = self.client.get(SLOTS_URL, {
            'property_id': self.prop.pk,
            'date': str(self.target_date),
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('available_slots', resp.data)
        self.assertIsInstance(resp.data['available_slots'], list)
        self.assertGreater(len(resp.data['available_slots']), 0)

    def test_slots_missing_params_returns_400(self):
        resp = self.client.get(SLOTS_URL, {'property_id': self.prop.pk})
        self.assertEqual(resp.status_code, 400)

    def test_slots_past_date_returns_400(self):
        resp = self.client.get(SLOTS_URL, {
            'property_id': self.prop.pk,
            'date': '2020-01-01',
        })
        self.assertEqual(resp.status_code, 400)


class CreateAppointmentTestCase(APITestCase):
    """Tests for POST /public/properties/{id}/appointment."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Book Tenant', slug='book-tenant',
            email='book@test.com', is_active=True,
        )
        AppointmentSettings.objects.create(
            tenant=self.tenant,
            slot_duration_minutes=60,
            day_start_time='09:00',
            day_end_time='17:00',
            min_advance_hours=0,
        )
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Casa reserva',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000, is_active=True,
        )
        agent_user = User.objects.create(email='agent_book@test.com', is_active=True)
        self.agent_m = TenantMembership.objects.create(
            user=agent_user, tenant=self.tenant,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        AgentProfile.objects.create(membership=self.agent_m)
        PropertyAssignment.objects.create(
            property=self.prop, agent_membership=self.agent_m, is_visible=True,
        )
        AgentSchedule.objects.create(
            tenant=self.tenant, agent_membership=self.agent_m,
            name='Lunes', monday=True,
            start_time='09:00', end_time='17:00',
            has_lunch_break=False, is_active=True,
        )
        self.target_date = _next_monday()
        self.valid_slot = '09:00'

    def test_book_appointment_with_valid_slot_returns_201(self):
        resp = self.client.post(_book_url(self.prop.pk), {
            'date': str(self.target_date),
            'time': self.valid_slot,
            'name': 'Juan Pérez',
            'email': 'juan@test.com',
            'phone': '+52 272 111 0000',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('matricula', resp.data)
        self.assertEqual(resp.data['status'], 'programada')

    def test_book_appointment_occupied_slot_returns_400(self):
        # First booking
        self.client.post(_book_url(self.prop.pk), {
            'date': str(self.target_date),
            'time': self.valid_slot,
            'name': 'First Person',
            'email': 'first@test.com',
            'phone': '+52 272 111 0001',
        }, format='json')

        # Second booking at same slot — must fail
        resp = self.client.post(_book_url(self.prop.pk), {
            'date': str(self.target_date),
            'time': self.valid_slot,
            'name': 'Second Person',
            'email': 'second@test.com',
            'phone': '+52 272 111 0002',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_book_appointment_no_agent_returns_400(self):
        prop_no_agent = Property.objects.create(
            tenant=self.tenant, title='Sin agente',
            listing_type='sale', status='disponible',
            property_type='house', price=500_000, is_active=True,
        )
        resp = self.client.post(_book_url(prop_no_agent.pk), {
            'date': str(self.target_date),
            'time': '09:00',
            'name': 'Test',
            'email': 'test@test.com',
            'phone': '+52 272 111 0003',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_book_nonexistent_property_returns_404(self):
        resp = self.client.post(_book_url(99999), {
            'date': str(self.target_date),
            'time': '09:00',
            'name': 'Test',
            'email': 'test@test.com',
            'phone': '+52 272 111 0004',
        }, format='json')
        self.assertEqual(resp.status_code, 404)
