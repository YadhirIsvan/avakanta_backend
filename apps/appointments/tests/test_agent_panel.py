"""
Tests del panel del agente — citas (T-082).

- Agente solo ve sus propias citas
- Transiciones válidas actualizan el estado
- Transiciones inválidas retornan 400
- Agente no puede ver ni modificar citas de otro agente
"""
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership, AgentProfile
from apps.properties.models import Property
from apps.appointments.models import Appointment


def _token(user):
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


def _appt_status_url(pk):
    return f'/api/v1/agent/appointments/{pk}/status'


class AgentAppointmentPanelSetup(APITestCase):
    """
    Base: un tenant con dos agentes, cada uno con su propia cita.
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='AgentAppt Tenant', slug='agentappt-tenant',
            email='agentappt@test.com',
        )

        # Agente A
        user_a = User.objects.create(email='agentappt_a@test.com')
        self.agent_m_a = TenantMembership.objects.create(
            user=user_a, tenant=self.tenant,
            role=TenantMembership.Role.AGENT,
        )
        AgentProfile.objects.create(membership=self.agent_m_a)
        self.token_a = _token(user_a)

        # Agente B
        user_b = User.objects.create(email='agentappt_b@test.com')
        self.agent_m_b = TenantMembership.objects.create(
            user=user_b, tenant=self.tenant,
            role=TenantMembership.Role.AGENT,
        )
        AgentProfile.objects.create(membership=self.agent_m_b)
        self.token_b = _token(user_b)

        # Propiedad compartida (solo necesitamos una)
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Casa citas',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
        )

        # Cita de agente A (estado inicial: programada)
        self.appt_a = Appointment.objects.create(
            tenant=self.tenant, property=self.prop,
            agent_membership=self.agent_m_a,
            matricula='CLI-2026-A01',
            scheduled_date='2026-06-02',
            scheduled_time='10:00',
            duration_minutes=60,
            status=Appointment.Status.PROGRAMADA,
        )

        # Cita de agente B (estado inicial: programada)
        self.appt_b = Appointment.objects.create(
            tenant=self.tenant, property=self.prop,
            agent_membership=self.agent_m_b,
            matricula='CLI-2026-B01',
            scheduled_date='2026-06-02',
            scheduled_time='11:00',
            duration_minutes=60,
            status=Appointment.Status.PROGRAMADA,
        )


class TestAgentSeesOnlyOwnAppointments(AgentAppointmentPanelSetup):
    """GET /agent/appointments → solo las citas del agente autenticado."""

    def test_agent_a_sees_own_appointment(self):
        resp = self.client.get('/api/v1/agent/appointments', **_auth(self.token_a))
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data['results']]
        self.assertIn(self.appt_a.pk, ids)

    def test_agent_a_does_not_see_agent_b_appointment(self):
        resp = self.client.get('/api/v1/agent/appointments', **_auth(self.token_a))
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data['results']]
        self.assertNotIn(self.appt_b.pk, ids)

    def test_agent_b_sees_only_own_appointment(self):
        resp = self.client.get('/api/v1/agent/appointments', **_auth(self.token_b))
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data['results']]
        self.assertIn(self.appt_b.pk, ids)
        self.assertNotIn(self.appt_a.pk, ids)


class TestValidAppointmentTransitions(AgentAppointmentPanelSetup):
    """Transiciones válidas actualizan el estado de la cita."""

    def test_programada_to_confirmada_returns_200(self):
        resp = self.client.patch(
            _appt_status_url(self.appt_a.pk),
            {'status': 'confirmada'},
            format='json',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'confirmada')

    def test_programada_to_cancelada_returns_200(self):
        resp = self.client.patch(
            _appt_status_url(self.appt_a.pk),
            {'status': 'cancelada'},
            format='json',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 200)

    def test_confirmada_to_en_progreso_returns_200(self):
        # Primero confirmar
        self.appt_a.status = Appointment.Status.CONFIRMADA
        self.appt_a.save()

        resp = self.client.patch(
            _appt_status_url(self.appt_a.pk),
            {'status': 'en_progreso'},
            format='json',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 200)

    def test_en_progreso_to_completada_returns_200(self):
        self.appt_a.status = Appointment.Status.EN_PROGRESO
        self.appt_a.save()

        resp = self.client.patch(
            _appt_status_url(self.appt_a.pk),
            {'status': 'completada'},
            format='json',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 200)

    def test_status_update_persists_in_db(self):
        self.client.patch(
            _appt_status_url(self.appt_a.pk),
            {'status': 'confirmada'},
            format='json',
            **_auth(self.token_a),
        )
        self.appt_a.refresh_from_db()
        self.assertEqual(self.appt_a.status, 'confirmada')


class TestInvalidAppointmentTransitions(AgentAppointmentPanelSetup):
    """Transiciones inválidas retornan 400."""

    def test_programada_to_completada_returns_400(self):
        """programada no puede saltar directo a completada."""
        resp = self.client.patch(
            _appt_status_url(self.appt_a.pk),
            {'status': 'completada'},
            format='json',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 400)

    def test_programada_to_en_progreso_returns_400(self):
        """programada no puede saltar a en_progreso."""
        resp = self.client.patch(
            _appt_status_url(self.appt_a.pk),
            {'status': 'en_progreso'},
            format='json',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 400)

    def test_completada_to_any_returns_400(self):
        """Una cita completada no tiene transiciones válidas."""
        self.appt_a.status = Appointment.Status.COMPLETADA
        self.appt_a.save()

        resp = self.client.patch(
            _appt_status_url(self.appt_a.pk),
            {'status': 'confirmada'},
            format='json',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 400)

    def test_cancelada_to_any_returns_400(self):
        """Una cita cancelada no tiene transiciones válidas."""
        self.appt_a.status = Appointment.Status.CANCELADA
        self.appt_a.save()

        resp = self.client.patch(
            _appt_status_url(self.appt_a.pk),
            {'status': 'confirmada'},
            format='json',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 400)


class TestAgentAppointmentIsolation(AgentAppointmentPanelSetup):
    """Agente no puede ver ni modificar citas de otro agente."""

    def test_agent_a_cannot_update_agent_b_appointment(self):
        """PATCH sobre cita de otro agente → 404."""
        resp = self.client.patch(
            _appt_status_url(self.appt_b.pk),
            {'status': 'confirmada'},
            format='json',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 404)

    def test_agent_b_cannot_update_agent_a_appointment(self):
        resp = self.client.patch(
            _appt_status_url(self.appt_a.pk),
            {'status': 'confirmada'},
            format='json',
            **_auth(self.token_b),
        )
        self.assertEqual(resp.status_code, 404)

    def test_nonexistent_appointment_returns_404(self):
        resp = self.client.patch(
            _appt_status_url(99999),
            {'status': 'confirmada'},
            format='json',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 404)
