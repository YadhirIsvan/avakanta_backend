"""
Comprehensive tests for apps/appointments/views/admin.py

Test coverage for:
- AdminAgentScheduleListCreateView (GET/POST)
- AdminAgentScheduleDetailView (PATCH/DELETE)
- AdminAgentUnavailabilityListCreateView (GET/POST)
- AdminAgentUnavailabilityDeleteView (DELETE)
- AdminAppointmentListCreateView (GET/POST)
- AdminAppointmentDetailView (PATCH/DELETE)
- AdminAppointmentAvailabilityView (GET)
"""
from datetime import date, time, timedelta

from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership, AgentProfile
from apps.properties.models import Property
from apps.appointments.models import (
    Appointment, AgentSchedule, ScheduleBreak, AgentUnavailability, AppointmentSettings
)


def _token(user):
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


class AdminAppointmentsTestSetup(APITestCase):
    """Base setup: Tenant with admin, agents, clients, and properties."""

    def setUp(self):
        # Create tenant
        self.tenant = Tenant.objects.create(
            name='Appointments Test', slug='appt-test',
            email='appt@test.com', is_active=True,
        )

        # Create admin
        self.admin_user = User.objects.create(email='admin@appt.com', is_active=True)
        self.admin_membership = TenantMembership.objects.create(
            user=self.admin_user, tenant=self.tenant,
            role=TenantMembership.Role.ADMIN, is_active=True,
        )
        self.admin_token = _token(self.admin_user)

        # Create agents
        self.agent1_user = User.objects.create(email='agent1@appt.com', is_active=True, first_name='Carlos', last_name='Agent')
        self.agent1_membership = TenantMembership.objects.create(
            user=self.agent1_user, tenant=self.tenant,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        self.agent1_profile = AgentProfile.objects.create(membership=self.agent1_membership)

        self.agent2_user = User.objects.create(email='agent2@appt.com', is_active=True)
        self.agent2_membership = TenantMembership.objects.create(
            user=self.agent2_user, tenant=self.tenant,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        self.agent2_profile = AgentProfile.objects.create(membership=self.agent2_membership)

        # Create client
        self.client_user = User.objects.create(email='client@appt.com', is_active=True)
        self.client_membership = TenantMembership.objects.create(
            user=self.client_user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT, is_active=True,
        )

        # Create property
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Test Property',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000, is_active=True,
        )

        # Create non-admin user for permission tests
        self.non_admin_user = User.objects.create(email='user@appt.com', is_active=True)
        self.non_admin_membership = TenantMembership.objects.create(
            user=self.non_admin_user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT, is_active=True,
        )
        self.non_admin_token = _token(self.non_admin_user)

        # Create appointment settings
        self.settings = AppointmentSettings.objects.create(
            tenant=self.tenant,
            slot_duration_minutes=60,
            max_advance_days=30,
            min_advance_hours=24,
        )


class TestAdminAgentScheduleListCreate(AdminAppointmentsTestSetup):
    """Tests for AdminAgentScheduleListCreateView."""

    def test_list_empty(self):
        """GET with no schedules returns empty list."""
        resp = self.client.get(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/schedules',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [])

    def test_list_with_schedules(self):
        """GET returns agent schedules."""
        schedule = AgentSchedule.objects.create(
            tenant=self.tenant,
            agent_membership=self.agent1_membership,
            name='Morning Schedule',
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            start_time=time(9, 0),
            end_time=time(13, 0),
        )

        resp = self.client.get(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/schedules',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['name'], 'Morning Schedule')

    def test_list_agent_not_found(self):
        """GET with invalid agent_id returns 404."""
        resp = self.client.get(
            '/api/v1/admin/agents/9999/schedules',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_create_success(self):
        """POST creates agent schedule with breaks."""
        resp = self.client.post(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/schedules',
            {
                'name': 'Full Day',
                'monday': True,
                'tuesday': True,
                'wednesday': True,
                'thursday': True,
                'friday': True,
                'start_time': '09:00',
                'end_time': '18:00',
                'has_lunch_break': True,
                'lunch_start': '12:00',
                'lunch_end': '13:00',
                'breaks': [
                    {'break_type': 'lunch', 'start_time': '12:00', 'end_time': '13:00'},
                    {'break_type': 'coffee', 'start_time': '15:00', 'end_time': '15:15'},
                ],
            },
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['name'], 'Full Day')
        self.assertEqual(len(resp.data['breaks']), 2)

    def test_create_without_breaks(self):
        """POST without breaks field creates schedule."""
        resp = self.client.post(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/schedules',
            {
                'name': 'Simple Schedule',
                'monday': True,
                'friday': True,
                'start_time': '09:00',
                'end_time': '17:00',
            },
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['breaks'], [])

    def test_create_agent_not_found(self):
        """POST with invalid agent_id returns 404."""
        resp = self.client.post(
            '/api/v1/admin/agents/9999/schedules',
            {'name': 'Test', 'start_time': '09:00', 'end_time': '17:00'},
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_create_invalid_data(self):
        """POST with invalid data returns 400."""
        resp = self.client.post(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/schedules',
            {'name': 'Test'},  # Missing required fields
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_permission_denied_non_admin(self):
        """Non-admin gets 403."""
        resp = self.client.get(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/schedules',
            **_auth(self.non_admin_token),
        )
        self.assertEqual(resp.status_code, 403)

    def test_unauthorized_no_token(self):
        """GET without token returns 401."""
        resp = self.client.get(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/schedules',
        )
        self.assertEqual(resp.status_code, 401)


class TestAdminAgentScheduleDetail(AdminAppointmentsTestSetup):
    """Tests for AdminAgentScheduleDetailView."""

    def setUp(self):
        super().setUp()
        self.schedule = AgentSchedule.objects.create(
            tenant=self.tenant,
            agent_membership=self.agent1_membership,
            name='Morning Schedule',
            monday=True,
            tuesday=True,
            start_time=time(9, 0),
            end_time=time(13, 0),
            priority=1,
        )
        self.break1 = ScheduleBreak.objects.create(
            schedule=self.schedule,
            break_type='coffee',
            start_time=time(11, 0),
            end_time=time(11, 15),
        )

    def test_patch_name(self):
        """PATCH updates schedule name."""
        resp = self.client.patch(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/schedules/{self.schedule.pk}',
            {'name': 'Afternoon Schedule'},
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.name, 'Afternoon Schedule')

    def test_patch_time_range(self):
        """PATCH updates start and end times."""
        resp = self.client.patch(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/schedules/{self.schedule.pk}',
            {'start_time': '08:00', 'end_time': '16:00'},
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.start_time, time(8, 0))
        self.assertEqual(self.schedule.end_time, time(16, 0))

    def test_patch_days(self):
        """PATCH updates weekday flags."""
        resp = self.client.patch(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/schedules/{self.schedule.pk}',
            {'friday': True, 'saturday': False},
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.schedule.refresh_from_db()
        self.assertTrue(self.schedule.friday)

    def test_patch_breaks(self):
        """PATCH replaces breaks."""
        resp = self.client.patch(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/schedules/{self.schedule.pk}',
            {
                'breaks': [
                    {'break_type': 'lunch', 'start_time': '12:00', 'end_time': '13:00'},
                ],
            },
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        # Old break should be deleted
        self.assertEqual(ScheduleBreak.objects.filter(schedule=self.schedule).count(), 1)
        new_break = ScheduleBreak.objects.get(schedule=self.schedule)
        self.assertEqual(new_break.break_type, 'lunch')

    def test_patch_agent_not_found(self):
        """PATCH with invalid agent returns 404."""
        resp = self.client.patch(
            f'/api/v1/admin/agents/9999/schedules/{self.schedule.pk}',
            {'name': 'Test'},
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_patch_schedule_not_found(self):
        """PATCH with invalid schedule returns 404."""
        resp = self.client.patch(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/schedules/9999',
            {'name': 'Test'},
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_success(self):
        """DELETE removes schedule."""
        resp = self.client.delete(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/schedules/{self.schedule.pk}',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(AgentSchedule.objects.filter(pk=self.schedule.pk).exists())

    def test_delete_agent_not_found(self):
        """DELETE with invalid agent returns 404."""
        resp = self.client.delete(
            f'/api/v1/admin/agents/9999/schedules/{self.schedule.pk}',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_schedule_not_found(self):
        """DELETE with invalid schedule returns 404."""
        resp = self.client.delete(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/schedules/9999',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 404)


class TestAdminAgentUnavailabilityListCreate(AdminAppointmentsTestSetup):
    """Tests for AdminAgentUnavailabilityListCreateView."""

    def test_list_empty(self):
        """GET with no unavailabilities returns empty list."""
        resp = self.client.get(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/unavailabilities',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, [])

    def test_list_with_unavailabilities(self):
        """GET returns agent unavailabilities."""
        today = date.today()
        unavail = AgentUnavailability.objects.create(
            tenant=self.tenant,
            agent_membership=self.agent1_membership,
            start_date=today,
            end_date=today + timedelta(days=5),
            reason=AgentUnavailability.Reason.VACATION,
        )

        resp = self.client.get(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/unavailabilities',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['reason'], 'vacation')

    def test_create_success(self):
        """POST creates unavailability."""
        today = date.today()
        resp = self.client.post(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/unavailabilities',
            {
                'start_date': str(today),
                'end_date': str(today + timedelta(days=3)),
                'reason': 'vacation',
                'notes': 'Family vacation',
            },
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['reason'], 'vacation')
        self.assertTrue(AgentUnavailability.objects.filter(
            agent_membership=self.agent1_membership, reason='vacation'
        ).exists())

    def test_create_agent_not_found(self):
        """POST with invalid agent returns 404."""
        resp = self.client.post(
            '/api/v1/admin/agents/9999/unavailabilities',
            {'start_date': str(date.today()), 'end_date': str(date.today() + timedelta(days=1)), 'reason': 'vacation'},
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_permission_denied_non_admin(self):
        """Non-admin gets 403."""
        resp = self.client.post(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/unavailabilities',
            {'start_date': str(date.today()), 'end_date': str(date.today() + timedelta(days=1)), 'reason': 'vacation'},
            format='json',
            **_auth(self.non_admin_token),
        )
        self.assertEqual(resp.status_code, 403)


class TestAdminAgentUnavailabilityDelete(AdminAppointmentsTestSetup):
    """Tests for AdminAgentUnavailabilityDeleteView."""

    def setUp(self):
        super().setUp()
        today = date.today()
        self.unavail = AgentUnavailability.objects.create(
            tenant=self.tenant,
            agent_membership=self.agent1_membership,
            start_date=today,
            end_date=today + timedelta(days=5),
            reason=AgentUnavailability.Reason.VACATION,
        )

    def test_delete_success(self):
        """DELETE removes unavailability."""
        resp = self.client.delete(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/unavailabilities/{self.unavail.pk}',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(AgentUnavailability.objects.filter(pk=self.unavail.pk).exists())

    def test_delete_agent_not_found(self):
        """DELETE with invalid agent returns 404."""
        resp = self.client.delete(
            f'/api/v1/admin/agents/9999/unavailabilities/{self.unavail.pk}',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_unavailability_not_found(self):
        """DELETE with invalid unavailability returns 404."""
        resp = self.client.delete(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/unavailabilities/9999',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_permission_denied_non_admin(self):
        """Non-admin gets 403."""
        resp = self.client.delete(
            f'/api/v1/admin/agents/{self.agent1_profile.pk}/unavailabilities/{self.unavail.pk}',
            **_auth(self.non_admin_token),
        )
        self.assertEqual(resp.status_code, 403)


class TestAdminAppointmentListCreate(AdminAppointmentsTestSetup):
    """Tests for AdminAppointmentListCreateView."""

    def test_list_empty(self):
        """GET with no appointments returns empty list."""
        resp = self.client.get(
            '/api/v1/admin/appointments',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)

    def test_list_with_appointments(self):
        """GET returns appointments."""
        tomorrow = date.today() + timedelta(days=1)
        Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            agent_membership=self.agent1_membership,
            client_membership=self.client_membership,
            matricula='CLI-2025-001',
            scheduled_date=tomorrow,
            scheduled_time=time(10, 0),
            appointment_type=Appointment.AppointmentType.PRIMERA_VISITA,
        )

        resp = self.client.get(
            '/api/v1/admin/appointments',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_list_filter_by_date(self):
        """GET with date filter returns matching appointments."""
        tomorrow = date.today() + timedelta(days=1)
        Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            agent_membership=self.agent1_membership,
            client_membership=self.client_membership,
            matricula='CLI-2025-001',
            scheduled_date=tomorrow,
            scheduled_time=time(10, 0),
        )

        resp = self.client.get(
            f'/api/v1/admin/appointments?date={tomorrow}',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_list_filter_by_agent(self):
        """GET with agent_id filter returns matching appointments."""
        tomorrow = date.today() + timedelta(days=1)
        Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            agent_membership=self.agent1_membership,
            matricula='CLI-2025-001',
            scheduled_date=tomorrow,
            scheduled_time=time(10, 0),
        )

        resp = self.client.get(
            f'/api/v1/admin/appointments?agent_id={self.agent1_profile.pk}',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_list_filter_by_status(self):
        """GET with status filter returns matching appointments."""
        tomorrow = date.today() + timedelta(days=1)
        appt = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            agent_membership=self.agent1_membership,
            matricula='CLI-2025-001',
            scheduled_date=tomorrow,
            scheduled_time=time(10, 0),
            status=Appointment.Status.PROGRAMADA,
        )

        resp = self.client.get(
            f'/api/v1/admin/appointments?status=programada',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_list_search_by_matricula(self):
        """GET with search filter finds by matricula."""
        tomorrow = date.today() + timedelta(days=1)
        Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            agent_membership=self.agent1_membership,
            matricula='CLI-2025-999',
            scheduled_date=tomorrow,
            scheduled_time=time(10, 0),
        )

        resp = self.client.get(
            '/api/v1/admin/appointments?search=CLI-2025-999',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_list_search_by_client_name(self):
        """GET with search filter finds by client name."""
        tomorrow = date.today() + timedelta(days=1)
        Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            agent_membership=self.agent1_membership,
            matricula='CLI-2025-001',
            client_name='Juan Pérez',
            scheduled_date=tomorrow,
            scheduled_time=time(10, 0),
        )

        resp = self.client.get(
            '/api/v1/admin/appointments?search=Juan',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_create_success(self):
        """POST creates appointment."""
        tomorrow = date.today() + timedelta(days=1)

        # Create schedule so slot is available
        schedule = AgentSchedule.objects.create(
            tenant=self.tenant,
            agent_membership=self.agent1_membership,
            name='Work Schedule',
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            start_time=time(9, 0),
            end_time=time(18, 0),
        )

        resp = self.client.post(
            '/api/v1/admin/appointments',
            {
                'property_id': self.prop.pk,
                'agent_membership_id': self.agent1_membership.pk,
                'client_membership_id': self.client_membership.pk,
                'scheduled_date': str(tomorrow),
                'scheduled_time': '10:00',
                'appointment_type': 'primera_visita',
            },
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Appointment.objects.filter(
            property=self.prop, agent_membership=self.agent1_membership
        ).exists())

    def test_create_property_not_found(self):
        """POST with invalid property returns 400."""
        tomorrow = date.today() + timedelta(days=1)
        resp = self.client.post(
            '/api/v1/admin/appointments',
            {
                'property_id': 9999,
                'agent_membership_id': self.agent1_membership.pk,
                'scheduled_date': str(tomorrow),
                'scheduled_time': '10:00',
            },
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_agent_not_found(self):
        """POST with invalid agent returns 400."""
        tomorrow = date.today() + timedelta(days=1)
        resp = self.client.post(
            '/api/v1/admin/appointments',
            {
                'property_id': self.prop.pk,
                'agent_membership_id': 9999,
                'scheduled_date': str(tomorrow),
                'scheduled_time': '10:00',
            },
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_no_available_schedule(self):
        """POST when agent has no schedule returns 400."""
        tomorrow = date.today() + timedelta(days=1)
        # Agent has no schedule
        resp = self.client.post(
            '/api/v1/admin/appointments',
            {
                'property_id': self.prop.pk,
                'agent_membership_id': self.agent2_membership.pk,
                'scheduled_date': str(tomorrow),
                'scheduled_time': '10:00',
            },
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)

    def test_create_permission_denied(self):
        """Non-admin gets 403."""
        tomorrow = date.today() + timedelta(days=1)
        resp = self.client.post(
            '/api/v1/admin/appointments',
            {
                'property_id': self.prop.pk,
                'agent_membership_id': self.agent1_membership.pk,
                'scheduled_date': str(tomorrow),
                'scheduled_time': '10:00',
            },
            format='json',
            **_auth(self.non_admin_token),
        )
        self.assertEqual(resp.status_code, 403)

    def test_unauthorized_no_token(self):
        """GET without token returns 401."""
        resp = self.client.get('/api/v1/admin/appointments')
        self.assertEqual(resp.status_code, 401)


class TestAdminAppointmentDetail(AdminAppointmentsTestSetup):
    """Tests for AdminAppointmentDetailView."""

    def setUp(self):
        super().setUp()
        tomorrow = date.today() + timedelta(days=1)
        self.appt = Appointment.objects.create(
            tenant=self.tenant,
            property=self.prop,
            agent_membership=self.agent1_membership,
            client_membership=self.client_membership,
            matricula='CLI-2025-001',
            scheduled_date=tomorrow,
            scheduled_time=time(10, 0),
            status=Appointment.Status.PROGRAMADA,
        )

    def test_patch_status(self):
        """PATCH status updates status."""
        resp = self.client.patch(
            f'/api/v1/admin/appointments/{self.appt.pk}',
            {'status': 'confirmada'},
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, Appointment.Status.CONFIRMADA)

    def test_patch_notes(self):
        """PATCH notes updates notes."""
        resp = self.client.patch(
            f'/api/v1/admin/appointments/{self.appt.pk}',
            {'notes': 'Cliente confirmó asistencia'},
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.notes, 'Cliente confirmó asistencia')

    def test_patch_not_found(self):
        """PATCH with invalid pk returns 404."""
        resp = self.client.patch(
            '/api/v1/admin/appointments/9999',
            {'status': 'confirmada'},
            format='json',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_success(self):
        """DELETE removes appointment."""
        resp = self.client.delete(
            f'/api/v1/admin/appointments/{self.appt.pk}',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Appointment.objects.filter(pk=self.appt.pk).exists())

    def test_delete_not_found(self):
        """DELETE with invalid pk returns 404."""
        resp = self.client.delete(
            '/api/v1/admin/appointments/9999',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_permission_denied_non_admin(self):
        """Non-admin gets 403."""
        resp = self.client.patch(
            f'/api/v1/admin/appointments/{self.appt.pk}',
            {'status': 'confirmada'},
            format='json',
            **_auth(self.non_admin_token),
        )
        self.assertEqual(resp.status_code, 403)


class TestAdminAppointmentAvailability(AdminAppointmentsTestSetup):
    """Tests for AdminAppointmentAvailabilityView."""

    def setUp(self):
        super().setUp()
        # Create schedule for agent
        self.schedule = AgentSchedule.objects.create(
            tenant=self.tenant,
            agent_membership=self.agent1_membership,
            name='Full Day',
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            saturday=False,
            sunday=False,
            start_time=time(9, 0),
            end_time=time(18, 0),
        )

    def test_get_availability_success(self):
        """GET returns available slots."""
        tomorrow = date.today() + timedelta(days=1)
        # Make sure it's a weekday
        while tomorrow.weekday() > 4:  # Friday is 4
            tomorrow += timedelta(days=1)

        resp = self.client.get(
            f'/api/v1/admin/appointments/availability?agent_id={self.agent1_profile.pk}&date={tomorrow}',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('available_slots', resp.data)
        self.assertIn('slot_duration_minutes', resp.data)
        self.assertGreater(len(resp.data['available_slots']), 0)

    def test_get_availability_missing_params(self):
        """GET without required params returns 400."""
        resp = self.client.get(
            '/api/v1/admin/appointments/availability',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_availability_invalid_date_format(self):
        """GET with invalid date format returns 400."""
        resp = self.client.get(
            f'/api/v1/admin/appointments/availability?agent_id={self.agent1_profile.pk}&date=invalid',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_availability_agent_not_found(self):
        """GET with invalid agent_id returns 404."""
        tomorrow = date.today() + timedelta(days=1)
        resp = self.client.get(
            f'/api/v1/admin/appointments/availability?agent_id=9999&date={tomorrow}',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_availability_on_unavailable_date(self):
        """GET on date with unavailability returns empty slots."""
        tomorrow = date.today() + timedelta(days=1)
        AgentUnavailability.objects.create(
            tenant=self.tenant,
            agent_membership=self.agent1_membership,
            start_date=tomorrow,
            end_date=tomorrow,
            reason=AgentUnavailability.Reason.VACATION,
        )

        resp = self.client.get(
            f'/api/v1/admin/appointments/availability?agent_id={self.agent1_profile.pk}&date={tomorrow}',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['available_slots']), 0)

    def test_get_availability_on_weekend(self):
        """GET on weekend returns empty slots."""
        # Find next Saturday
        next_saturday = date.today()
        while next_saturday.weekday() != 5:  # Saturday
            next_saturday += timedelta(days=1)

        resp = self.client.get(
            f'/api/v1/admin/appointments/availability?agent_id={self.agent1_profile.pk}&date={next_saturday}',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['available_slots']), 0)

    def test_get_availability_with_break(self):
        """GET returns slots excluding breaks."""
        tomorrow = date.today() + timedelta(days=1)
        while tomorrow.weekday() > 4:  # Must be weekday
            tomorrow += timedelta(days=1)

        # Add break during working hours
        ScheduleBreak.objects.create(
            schedule=self.schedule,
            break_type='lunch',
            start_time=time(12, 0),
            end_time=time(13, 0),
        )

        resp = self.client.get(
            f'/api/v1/admin/appointments/availability?agent_id={self.agent1_profile.pk}&date={tomorrow}',
            **_auth(self.admin_token),
        )
        self.assertEqual(resp.status_code, 200)
        # Should have slots but not in lunch break time
        slots = resp.data['available_slots']
        if slots:
            # Check that 12:00-13:00 is not in slots
            lunch_slots = [s for s in slots if s.startswith('12:')]
            self.assertEqual(len(lunch_slots), 0)

    def test_permission_denied_non_admin(self):
        """Non-admin gets 403."""
        tomorrow = date.today() + timedelta(days=1)
        resp = self.client.get(
            f'/api/v1/admin/appointments/availability?agent_id={self.agent1_profile.pk}&date={tomorrow}',
            **_auth(self.non_admin_token),
        )
        self.assertEqual(resp.status_code, 403)

    def test_unauthorized_no_token(self):
        """GET without token returns 401."""
        tomorrow = date.today() + timedelta(days=1)
        resp = self.client.get(
            f'/api/v1/admin/appointments/availability?agent_id={self.agent1_profile.pk}&date={tomorrow}',
        )
        self.assertEqual(resp.status_code, 401)
