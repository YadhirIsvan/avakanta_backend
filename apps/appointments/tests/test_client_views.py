"""
Comprehensive tests for client-facing appointment views in apps/appointments/views/client.py

Covers:
- ClientAppointmentListView (GET)
- ClientAppointmentCancelView (PATCH)
"""
from datetime import date, time, timedelta

from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership, AgentProfile
from apps.properties.models import Property, PropertyImage
from apps.appointments.models import Appointment
from apps.locations.models import Country, State, City


def _token(user):
    """Generate JWT access token for user."""
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    """Return authorization header."""
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


class AppointmentSetup(APITestCase):
    """Base setup for appointment tests."""

    def setUp(self):
        # Tenant
        self.tenant = Tenant.objects.create(
            name='Appointment Tenant', slug='appointment-tenant',
            email='appointment@test.com',
        )

        # Location setup
        self.country = Country.objects.create(name='Mexico')
        self.state = State.objects.create(name='Mexico City', country=self.country)
        self.city = City.objects.create(name='Mexico City', state=self.state)

        # Client
        self.client_user = User.objects.create(
            email='client_appointment@test.com',
            first_name='Juan',
            last_name='Pérez',
            is_active=True,
        )
        self.client_membership = TenantMembership.objects.create(
            user=self.client_user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT,
        )
        self.token = _token(self.client_user)

        # Other client for isolation tests
        self.other_client_user = User.objects.create(
            email='other_client_appointment@test.com',
        )
        self.other_client_membership = TenantMembership.objects.create(
            user=self.other_client_user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT,
        )

        # Agent
        self.agent_user = User.objects.create(
            email='agent_appointment@test.com',
        )
        self.agent_membership = TenantMembership.objects.create(
            user=self.agent_user, tenant=self.tenant,
            role=TenantMembership.Role.AGENT,
        )
        AgentProfile.objects.create(membership=self.agent_membership)

        # Property
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Casa Appointment',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
            city=self.city,
        )
        PropertyImage.objects.create(
            property=self.prop, image_url='http://example.com/image.jpg',
            is_cover=True,
        )


class TestClientAppointmentList(AppointmentSetup):
    """Test ClientAppointmentListView GET endpoint."""

    def test_get_appointment_list_returns_200_authenticated(self):
        """GET /client/appointments returns 200 with auth."""
        resp = self.client.get('/api/v1/client/appointments', **_auth(self.token))
        self.assertEqual(resp.status_code, 200)

    def test_get_appointment_list_returns_401_unauthenticated(self):
        """GET /client/appointments without auth returns 401."""
        resp = self.client.get('/api/v1/client/appointments')
        self.assertEqual(resp.status_code, 401)

    def test_get_appointment_list_empty(self):
        """GET /client/appointments returns empty list when no appointments."""
        resp = self.client.get('/api/v1/client/appointments', **_auth(self.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 0)

    def test_get_appointment_list_returns_array(self):
        """GET /client/appointments returns array of appointments."""
        resp = self.client.get('/api/v1/client/appointments', **_auth(self.token))
        self.assertIsInstance(resp.data, list)

    def test_get_appointment_list_shows_own_appointments(self):
        """GET /client/appointments only shows own appointments."""
        # Create appointment for this client
        Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-001',
            scheduled_date=date.today() + timedelta(days=1),
            scheduled_time=time(10, 0),
        )

        # Create appointment for other client
        Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.other_client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-002',
            scheduled_date=date.today() + timedelta(days=1),
            scheduled_time=time(14, 0),
        )

        resp = self.client.get('/api/v1/client/appointments', **_auth(self.token))
        self.assertEqual(len(resp.data), 1)

    def test_get_appointment_list_multiple_appointments(self):
        """GET /client/appointments returns multiple own appointments."""
        for i in range(3):
            Appointment.objects.create(
                tenant=self.tenant,
                property=self.prop,
                client_membership=self.client_membership,
                agent_membership=self.agent_membership,
                matricula=f'CLI-2025-{i+1:03d}',
                scheduled_date=date.today() + timedelta(days=i+1),
                scheduled_time=time(10, 0),
            )

        resp = self.client.get('/api/v1/client/appointments', **_auth(self.token))
        self.assertEqual(len(resp.data), 3)

    def test_get_appointment_list_ordered_by_date_time_desc(self):
        """GET /client/appointments ordered by scheduled_date and time descending."""
        # Create appointments in chronological order
        a1 = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-001',
            scheduled_date=date.today() + timedelta(days=1),
            scheduled_time=time(10, 0),
        )
        a2 = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-002',
            scheduled_date=date.today() + timedelta(days=2),
            scheduled_time=time(14, 0),
        )
        a3 = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-003',
            scheduled_date=date.today() + timedelta(days=2),
            scheduled_time=time(9, 0),
        )

        resp = self.client.get('/api/v1/client/appointments', **_auth(self.token))
        # Most recent first (latest date, then latest time)
        results = resp.data
        self.assertEqual(results[0]['matricula'], 'CLI-2025-002')

    def test_get_appointment_list_includes_appointment_details(self):
        """GET /client/appointments includes appointment details."""
        Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-001',
            scheduled_date=date.today() + timedelta(days=1),
            scheduled_time=time(10, 0),
            status=Appointment.Status.PROGRAMADA,
        )

        resp = self.client.get('/api/v1/client/appointments', **_auth(self.token))
        appointment = resp.data[0]
        self.assertIn('id', appointment)
        self.assertIn('matricula', appointment)
        self.assertIn('scheduled_date', appointment)
        self.assertIn('scheduled_time', appointment)
        self.assertIn('status', appointment)


class TestClientCancelAppointment(AppointmentSetup):
    """Test ClientAppointmentCancelView PATCH endpoint."""

    def test_patch_cancel_appointment_returns_200(self):
        """PATCH /client/appointments/{id}/cancel returns 200."""
        appt = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-001',
            scheduled_date=date.today() + timedelta(days=1),
            scheduled_time=time(10, 0),
            status=Appointment.Status.PROGRAMADA,
        )

        resp = self.client.patch(
            f'/api/v1/client/appointments/{appt.pk}/cancel',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)

    def test_patch_cancel_appointment_updates_status(self):
        """PATCH /client/appointments/{id}/cancel updates status to CANCELADA."""
        appt = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-001',
            scheduled_date=date.today() + timedelta(days=1),
            scheduled_time=time(10, 0),
            status=Appointment.Status.PROGRAMADA,
        )

        self.client.patch(
            f'/api/v1/client/appointments/{appt.pk}/cancel',
            {},
            format='json',
            **_auth(self.token),
        )

        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.CANCELADA)

    def test_patch_cancel_appointment_sets_cancellation_reason(self):
        """PATCH /client/appointments/{id}/cancel sets cancellation_reason."""
        appt = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-001',
            scheduled_date=date.today() + timedelta(days=1),
            scheduled_time=time(10, 0),
            status=Appointment.Status.PROGRAMADA,
        )

        reason = 'Cambio de planes'
        resp = self.client.patch(
            f'/api/v1/client/appointments/{appt.pk}/cancel',
            {'reason': reason},
            format='json',
            **_auth(self.token),
        )

        appt.refresh_from_db()
        self.assertEqual(appt.cancellation_reason, reason)

    def test_patch_cancel_appointment_default_reason(self):
        """PATCH without reason uses default cancellation reason."""
        appt = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-001',
            scheduled_date=date.today() + timedelta(days=1),
            scheduled_time=time(10, 0),
            status=Appointment.Status.PROGRAMADA,
        )

        self.client.patch(
            f'/api/v1/client/appointments/{appt.pk}/cancel',
            {},
            format='json',
            **_auth(self.token),
        )

        appt.refresh_from_db()
        self.assertIsNotNone(appt.cancellation_reason)

    def test_patch_cancel_appointment_returns_404_not_found(self):
        """PATCH /client/appointments/{bad_id}/cancel returns 404."""
        resp = self.client.patch(
            '/api/v1/client/appointments/99999/cancel',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_patch_cancel_appointment_other_client_returns_404(self):
        """PATCH other client's appointment returns 404."""
        appt = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.other_client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-001',
            scheduled_date=date.today() + timedelta(days=1),
            scheduled_time=time(10, 0),
            status=Appointment.Status.PROGRAMADA,
        )

        resp = self.client.patch(
            f'/api/v1/client/appointments/{appt.pk}/cancel',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_patch_cancel_appointment_already_completed_returns_400(self):
        """PATCH cancel on COMPLETADA appointment returns 400."""
        appt = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-001',
            scheduled_date=date.today() - timedelta(days=1),
            scheduled_time=time(10, 0),
            status=Appointment.Status.COMPLETADA,
        )

        resp = self.client.patch(
            f'/api/v1/client/appointments/{appt.pk}/cancel',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_patch_cancel_appointment_already_cancelled_returns_400(self):
        """PATCH cancel on CANCELADA appointment returns 400."""
        appt = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-001',
            scheduled_date=date.today() + timedelta(days=1),
            scheduled_time=time(10, 0),
            status=Appointment.Status.CANCELADA,
        )

        resp = self.client.patch(
            f'/api/v1/client/appointments/{appt.pk}/cancel',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_patch_cancel_appointment_no_show_returns_400(self):
        """PATCH cancel on NO_SHOW appointment returns 400."""
        appt = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-001',
            scheduled_date=date.today() - timedelta(days=1),
            scheduled_time=time(10, 0),
            status=Appointment.Status.NO_SHOW,
        )

        resp = self.client.patch(
            f'/api/v1/client/appointments/{appt.pk}/cancel',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_patch_cancel_appointment_confirmada_returns_200(self):
        """PATCH cancel on CONFIRMADA appointment succeeds."""
        appt = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-001',
            scheduled_date=date.today() + timedelta(days=1),
            scheduled_time=time(10, 0),
            status=Appointment.Status.CONFIRMADA,
        )

        resp = self.client.patch(
            f'/api/v1/client/appointments/{appt.pk}/cancel',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.CANCELADA)

    def test_patch_cancel_appointment_en_progreso_returns_200(self):
        """PATCH cancel on EN_PROGRESO appointment succeeds."""
        appt = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-001',
            scheduled_date=date.today(),
            scheduled_time=time(10, 0),
            status=Appointment.Status.EN_PROGRESO,
        )

        resp = self.client.patch(
            f'/api/v1/client/appointments/{appt.pk}/cancel',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)

    def test_patch_cancel_appointment_returns_401_unauthenticated(self):
        """PATCH without auth returns 401."""
        appt = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-001',
            scheduled_date=date.today() + timedelta(days=1),
            scheduled_time=time(10, 0),
        )

        resp = self.client.patch(
            f'/api/v1/client/appointments/{appt.pk}/cancel',
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, 401)

    def test_patch_cancel_appointment_returns_updated_appointment(self):
        """PATCH response includes updated appointment data."""
        appt = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            matricula='CLI-2025-001',
            scheduled_date=date.today() + timedelta(days=1),
            scheduled_time=time(10, 0),
            status=Appointment.Status.PROGRAMADA,
        )

        resp = self.client.patch(
            f'/api/v1/client/appointments/{appt.pk}/cancel',
            {'reason': 'No puedo asistir'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], Appointment.Status.CANCELADA)
