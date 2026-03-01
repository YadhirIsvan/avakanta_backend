"""
Tests de aislamiento multi-tenant.

Verifican que ningún usuario puede acceder a datos de otro tenant.
Se crean 2 tenants, 2 admins, y se valida que cada uno solo ve sus datos.
"""
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership, AgentProfile
from apps.properties.models import Property
from apps.transactions.models import PurchaseProcess, SaleProcess


def _token(user):
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


class TenantIsolationSetup(APITestCase):
    """Base class with two tenants, two admins and minimal data."""

    def setUp(self):
        # ── Tenant A ──────────────────────────────────────────────────────────
        self.tenant_a = Tenant.objects.create(
            name='Tenant A', slug='tenant-a', email='a@tenant.com', is_active=True
        )
        self.admin_a = User.objects.create(email='admin_a@test.com', is_active=True)
        self.membership_a = TenantMembership.objects.create(
            user=self.admin_a, tenant=self.tenant_a,
            role=TenantMembership.Role.ADMIN, is_active=True,
        )
        self.token_a = _token(self.admin_a)

        # Agent in Tenant A
        self.agent_user_a = User.objects.create(email='agent_a@test.com', is_active=True)
        self.agent_membership_a = TenantMembership.objects.create(
            user=self.agent_user_a, tenant=self.tenant_a,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        self.agent_profile_a = AgentProfile.objects.create(membership=self.agent_membership_a)

        # Property in Tenant A
        self.prop_a = Property.objects.create(
            tenant=self.tenant_a, title='Propiedad A',
            listing_type='sale', status='disponible',
            property_type='house', price=1000000,
        )

        # ── Tenant B ──────────────────────────────────────────────────────────
        self.tenant_b = Tenant.objects.create(
            name='Tenant B', slug='tenant-b', email='b@tenant.com', is_active=True
        )
        self.admin_b = User.objects.create(email='admin_b@test.com', is_active=True)
        self.membership_b = TenantMembership.objects.create(
            user=self.admin_b, tenant=self.tenant_b,
            role=TenantMembership.Role.ADMIN, is_active=True,
        )
        self.token_b = _token(self.admin_b)

        # Agent in Tenant B
        self.agent_user_b = User.objects.create(email='agent_b@test.com', is_active=True)
        self.agent_membership_b = TenantMembership.objects.create(
            user=self.agent_user_b, tenant=self.tenant_b,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        self.agent_profile_b = AgentProfile.objects.create(membership=self.agent_membership_b)

        # Property in Tenant B
        self.prop_b = Property.objects.create(
            tenant=self.tenant_b, title='Propiedad B',
            listing_type='sale', status='disponible',
            property_type='house', price=2000000,
        )

        # Client in Tenant A (needed for PurchaseProcess)
        self.client_user_a = User.objects.create(email='client_a@test.com', is_active=True)
        self.client_membership_a = TenantMembership.objects.create(
            user=self.client_user_a, tenant=self.tenant_a,
            role=TenantMembership.Role.CLIENT, is_active=True,
        )

        # Client in Tenant B
        self.client_user_b = User.objects.create(email='client_b@test.com', is_active=True)
        self.client_membership_b = TenantMembership.objects.create(
            user=self.client_user_b, tenant=self.tenant_b,
            role=TenantMembership.Role.CLIENT, is_active=True,
        )

        # PurchaseProcess in each tenant
        self.process_a = PurchaseProcess.objects.create(
            tenant=self.tenant_a, property=self.prop_a,
            client_membership=self.client_membership_a,
            agent_membership=self.agent_membership_a,
            status='lead',
        )
        self.process_b = PurchaseProcess.objects.create(
            tenant=self.tenant_b, property=self.prop_b,
            client_membership=self.client_membership_b,
            agent_membership=self.agent_membership_b,
            status='lead',
        )


class TestPropertyIsolation(TenantIsolationSetup):
    """Admin A only sees Tenant A's properties."""

    def test_list_only_returns_own_tenant_properties(self):
        resp = self.client.get('/api/v1/admin/properties', **_auth(self.token_a))
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data['results']]
        self.assertIn(self.prop_a.pk, ids)
        self.assertNotIn(self.prop_b.pk, ids)

    def test_detail_of_other_tenant_property_returns_404(self):
        resp = self.client.get(f'/api/v1/admin/properties/{self.prop_b.pk}', **_auth(self.token_a))
        self.assertEqual(resp.status_code, 404)

    def test_patch_other_tenant_property_returns_404(self):
        resp = self.client.patch(
            f'/api/v1/admin/properties/{self.prop_b.pk}',
            {'title': 'Hack'},
            content_type='application/json',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 404)


class TestAgentIsolation(TenantIsolationSetup):
    """Admin A only sees Tenant A's agents."""

    def test_list_only_returns_own_tenant_agents(self):
        resp = self.client.get('/api/v1/admin/agents', **_auth(self.token_a))
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data['results']]
        self.assertIn(self.agent_profile_a.pk, ids)
        self.assertNotIn(self.agent_profile_b.pk, ids)

    def test_detail_of_other_tenant_agent_returns_404(self):
        resp = self.client.get(
            f'/api/v1/admin/agents/{self.agent_profile_b.pk}',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 404)

    def test_patch_other_tenant_agent_returns_404(self):
        resp = self.client.patch(
            f'/api/v1/admin/agents/{self.agent_profile_b.pk}',
            {'zone': 'Hack'},
            content_type='application/json',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 404)


class TestPurchaseProcessIsolation(TenantIsolationSetup):
    """Admin A only sees Tenant A's purchase processes."""

    def test_list_only_returns_own_tenant_processes(self):
        resp = self.client.get('/api/v1/admin/purchase-processes', **_auth(self.token_a))
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data['results']]
        self.assertIn(self.process_a.pk, ids)
        self.assertNotIn(self.process_b.pk, ids)

    def test_status_update_of_other_tenant_process_returns_404(self):
        resp = self.client.patch(
            f'/api/v1/admin/purchase-processes/{self.process_b.pk}/status',
            {'status': 'visita', 'notes': ''},
            content_type='application/json',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 404)


class TestSaleProcessIsolation(TenantIsolationSetup):
    """Admin A only sees Tenant A's sale processes."""

    def setUp(self):
        super().setUp()
        self.sale_a = SaleProcess.objects.create(
            tenant=self.tenant_a, property=self.prop_a,
            client_membership=self.client_membership_a,
            agent_membership=self.agent_membership_a,
            status='contacto_inicial',
        )
        self.sale_b = SaleProcess.objects.create(
            tenant=self.tenant_b, property=self.prop_b,
            client_membership=self.client_membership_b,
            agent_membership=self.agent_membership_b,
            status='contacto_inicial',
        )

    def test_list_only_returns_own_tenant_sale_processes(self):
        resp = self.client.get('/api/v1/admin/sale-processes', **_auth(self.token_a))
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data['results']]
        self.assertIn(self.sale_a.pk, ids)
        self.assertNotIn(self.sale_b.pk, ids)

    def test_status_update_of_other_tenant_sale_returns_404(self):
        resp = self.client.patch(
            f'/api/v1/admin/sale-processes/{self.sale_b.pk}/status',
            {'status': 'evaluacion', 'notes': ''},
            content_type='application/json',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 404)
