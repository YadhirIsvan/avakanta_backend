"""
Tests de la matriz de permisos (spec sección 5.2).

Verifica que cada grupo de endpoints:
- Rechaza visitantes no autenticados con 401.
- Rechaza roles incorrectos con 403.
- Acepta el rol correcto (al menos 200/201/204).
"""
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership, AgentProfile


def _token(user):
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


class PermissionMatrixSetup(APITestCase):
    """Base: un tenant con un admin, un agente y un cliente."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Perm Tenant', slug='perm-tenant',
            email='perm@test.com', is_active=True,
        )

        # Admin
        self.admin_user = User.objects.create(email='admin_perm@test.com', is_active=True)
        TenantMembership.objects.create(
            user=self.admin_user, tenant=self.tenant,
            role=TenantMembership.Role.ADMIN, is_active=True,
        )
        self.admin_token = _token(self.admin_user)

        # Agent
        self.agent_user = User.objects.create(email='agent_perm@test.com', is_active=True)
        agent_m = TenantMembership.objects.create(
            user=self.agent_user, tenant=self.tenant,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        AgentProfile.objects.create(membership=agent_m)
        self.agent_token = _token(self.agent_user)

        # Client
        self.client_user = User.objects.create(email='client_perm@test.com', is_active=True)
        TenantMembership.objects.create(
            user=self.client_user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT, is_active=True,
        )
        self.client_token = _token(self.client_user)


# ── Admin endpoints ────────────────────────────────────────────────────────────

class TestAdminEndpointsPermissions(PermissionMatrixSetup):
    """GET /admin/properties, /admin/agents, etc. → solo admin."""

    # /admin/properties
    def test_admin_properties_unauthenticated_returns_401(self):
        resp = self.client.get('/api/v1/admin/properties')
        self.assertEqual(resp.status_code, 401)

    def test_admin_properties_client_returns_403(self):
        resp = self.client.get('/api/v1/admin/properties', **_auth(self.client_token))
        self.assertEqual(resp.status_code, 403)

    def test_admin_properties_agent_returns_403(self):
        resp = self.client.get('/api/v1/admin/properties', **_auth(self.agent_token))
        self.assertEqual(resp.status_code, 403)

    def test_admin_properties_admin_returns_200(self):
        resp = self.client.get('/api/v1/admin/properties', **_auth(self.admin_token))
        self.assertEqual(resp.status_code, 200)

    # /admin/agents
    def test_admin_agents_unauthenticated_returns_401(self):
        resp = self.client.get('/api/v1/admin/agents', **{})
        self.assertEqual(resp.status_code, 401)

    def test_admin_agents_client_returns_403(self):
        resp = self.client.get('/api/v1/admin/agents', **_auth(self.client_token))
        self.assertEqual(resp.status_code, 403)

    def test_admin_agents_agent_returns_403(self):
        resp = self.client.get('/api/v1/admin/agents', **_auth(self.agent_token))
        self.assertEqual(resp.status_code, 403)

    def test_admin_agents_admin_returns_200(self):
        resp = self.client.get('/api/v1/admin/agents', **_auth(self.admin_token))
        self.assertEqual(resp.status_code, 200)

    # /admin/purchase-processes
    def test_admin_purchase_processes_unauthenticated_returns_401(self):
        resp = self.client.get('/api/v1/admin/purchase-processes')
        self.assertEqual(resp.status_code, 401)

    def test_admin_purchase_processes_agent_returns_403(self):
        resp = self.client.get(
            '/api/v1/admin/purchase-processes', **_auth(self.agent_token)
        )
        self.assertEqual(resp.status_code, 403)

    def test_admin_purchase_process_status_agent_returns_403(self):
        """Spec done-criteria: agente en PATCH /admin/purchase-processes/{id}/status → 403."""
        resp = self.client.patch(
            '/api/v1/admin/purchase-processes/99999/status',
            {'status': 'visita', 'notes': ''},
            content_type='application/json',
            **_auth(self.agent_token),
        )
        self.assertEqual(resp.status_code, 403)

    # /admin/sale-processes
    def test_admin_sale_processes_client_returns_403(self):
        resp = self.client.get(
            '/api/v1/admin/sale-processes', **_auth(self.client_token)
        )
        self.assertEqual(resp.status_code, 403)


# ── Agent endpoints ────────────────────────────────────────────────────────────

class TestAgentEndpointsPermissions(PermissionMatrixSetup):
    """/agent/* → solo agente."""

    def test_agent_properties_unauthenticated_returns_401(self):
        resp = self.client.get('/api/v1/agent/properties')
        self.assertEqual(resp.status_code, 401)

    def test_agent_properties_admin_returns_403(self):
        resp = self.client.get('/api/v1/agent/properties', **_auth(self.admin_token))
        self.assertEqual(resp.status_code, 403)

    def test_agent_properties_client_returns_403(self):
        resp = self.client.get('/api/v1/agent/properties', **_auth(self.client_token))
        self.assertEqual(resp.status_code, 403)

    def test_agent_properties_agent_returns_200(self):
        resp = self.client.get('/api/v1/agent/properties', **_auth(self.agent_token))
        self.assertEqual(resp.status_code, 200)

    def test_agent_dashboard_unauthenticated_returns_401(self):
        resp = self.client.get('/api/v1/agent/dashboard')
        self.assertEqual(resp.status_code, 401)

    def test_agent_dashboard_admin_returns_403(self):
        resp = self.client.get('/api/v1/agent/dashboard', **_auth(self.admin_token))
        self.assertEqual(resp.status_code, 403)

    def test_agent_appointments_client_returns_403(self):
        resp = self.client.get('/api/v1/agent/appointments', **_auth(self.client_token))
        self.assertEqual(resp.status_code, 403)


# ── Client endpoints ────────────────────────────────────────────────────────────

class TestClientEndpointsPermissions(PermissionMatrixSetup):
    """/client/* → solo cliente."""

    def test_client_purchases_unauthenticated_returns_401(self):
        resp = self.client.get('/api/v1/client/purchases')
        self.assertEqual(resp.status_code, 401)

    def test_client_purchases_admin_returns_403(self):
        resp = self.client.get('/api/v1/client/purchases', **_auth(self.admin_token))
        self.assertEqual(resp.status_code, 403)

    def test_client_purchases_agent_returns_403(self):
        resp = self.client.get('/api/v1/client/purchases', **_auth(self.agent_token))
        self.assertEqual(resp.status_code, 403)

    def test_client_dashboard_unauthenticated_returns_401(self):
        resp = self.client.get('/api/v1/client/dashboard')
        self.assertEqual(resp.status_code, 401)

    def test_client_dashboard_agent_returns_403(self):
        resp = self.client.get('/api/v1/client/dashboard', **_auth(self.agent_token))
        self.assertEqual(resp.status_code, 403)

    def test_client_profile_admin_returns_403(self):
        resp = self.client.get('/api/v1/client/profile', **_auth(self.admin_token))
        self.assertEqual(resp.status_code, 403)


# ── Notifications (IsAuthenticated — cualquier rol) ────────────────────────────

class TestNotificationsPermissions(PermissionMatrixSetup):
    """/notifications/ → cualquier usuario autenticado con membresía activa."""

    def test_notifications_unauthenticated_returns_401(self):
        resp = self.client.get('/api/v1/notifications/')
        self.assertEqual(resp.status_code, 401)

    def test_notifications_admin_returns_200(self):
        resp = self.client.get('/api/v1/notifications/', **_auth(self.admin_token))
        self.assertEqual(resp.status_code, 200)

    def test_notifications_agent_returns_200(self):
        resp = self.client.get('/api/v1/notifications/', **_auth(self.agent_token))
        self.assertEqual(resp.status_code, 200)

    def test_notifications_client_returns_200(self):
        resp = self.client.get('/api/v1/notifications/', **_auth(self.client_token))
        self.assertEqual(resp.status_code, 200)
