"""
Tests del panel del agente — propiedades (T-082).

- Agente solo ve propiedades asignadas a él
- Agente no puede ver leads de propiedad de otro agente
"""
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership, AgentProfile
from apps.properties.models import Property, PropertyAssignment


def _token(user):
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


class AgentPropertiesPanelSetup(APITestCase):
    """
    Base: un tenant con dos agentes.
    Agente A tiene una propiedad asignada; agente B tiene otra.
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='AgentPanel Tenant', slug='agentpanel-tenant',
            email='agentpanel@test.com', is_active=True,
        )

        # Agente A
        user_a = User.objects.create(email='agent_panel_a@test.com', is_active=True)
        self.agent_m_a = TenantMembership.objects.create(
            user=user_a, tenant=self.tenant,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        AgentProfile.objects.create(membership=self.agent_m_a)
        self.token_a = _token(user_a)

        # Agente B
        user_b = User.objects.create(email='agent_panel_b@test.com', is_active=True)
        self.agent_m_b = TenantMembership.objects.create(
            user=user_b, tenant=self.tenant,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        AgentProfile.objects.create(membership=self.agent_m_b)
        self.token_b = _token(user_b)

        # Propiedad A → asignada a agente A
        self.prop_a = Property.objects.create(
            tenant=self.tenant, title='Casa del Agente A',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000, is_active=True,
        )
        PropertyAssignment.objects.create(
            property=self.prop_a, agent_membership=self.agent_m_a, is_visible=True,
        )

        # Propiedad B → asignada a agente B
        self.prop_b = Property.objects.create(
            tenant=self.tenant, title='Casa del Agente B',
            listing_type='sale', status='disponible',
            property_type='house', price=2_000_000, is_active=True,
        )
        PropertyAssignment.objects.create(
            property=self.prop_b, agent_membership=self.agent_m_b, is_visible=True,
        )


class TestAgentSeesOnlyOwnProperties(AgentPropertiesPanelSetup):
    """GET /agent/properties → solo las asignadas al agente autenticado."""

    def test_agent_a_sees_only_prop_a(self):
        resp = self.client.get('/api/v1/agent/properties', **_auth(self.token_a))
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data['results']]
        self.assertIn(self.prop_a.pk, ids)
        self.assertNotIn(self.prop_b.pk, ids)

    def test_agent_b_sees_only_prop_b(self):
        resp = self.client.get('/api/v1/agent/properties', **_auth(self.token_b))
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data['results']]
        self.assertIn(self.prop_b.pk, ids)
        self.assertNotIn(self.prop_a.pk, ids)

    def test_agent_a_count_matches_assigned_properties(self):
        resp = self.client.get('/api/v1/agent/properties', **_auth(self.token_a))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_agent_properties_returns_paginated_response(self):
        resp = self.client.get('/api/v1/agent/properties', **_auth(self.token_a))
        self.assertIn('results', resp.data)
        self.assertIn('count', resp.data)


class TestAgentLeadsIsolation(AgentPropertiesPanelSetup):
    """GET /agent/properties/{id}/leads → 404 si la propiedad es de otro agente."""

    def test_agent_a_gets_404_on_prop_b_leads(self):
        resp = self.client.get(
            f'/api/v1/agent/properties/{self.prop_b.pk}/leads',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 404)

    def test_agent_a_gets_200_on_prop_a_leads(self):
        resp = self.client.get(
            f'/api/v1/agent/properties/{self.prop_a.pk}/leads',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 200)

    def test_agent_b_gets_404_on_prop_a_leads(self):
        resp = self.client.get(
            f'/api/v1/agent/properties/{self.prop_a.pk}/leads',
            **_auth(self.token_b),
        )
        self.assertEqual(resp.status_code, 404)
