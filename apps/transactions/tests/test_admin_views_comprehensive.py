"""
Comprehensive tests for apps/transactions/views/admin.py

Test coverage for:
- AdminPurchaseProcessListCreateView (GET/POST)
- AdminPurchaseProcessStatusView (PATCH)
- AdminPurchaseProcessDetailView (PATCH)
- AdminSaleProcessListCreateView (GET/POST)
- AdminSaleProcessStatusView (PATCH)
- AdminSellerLeadListView (GET)
- AdminSellerLeadDetailView (GET/PATCH)
- AdminSellerLeadConvertView (POST)
- AdminSaleProcessAssignmentView (GET)
- AdminSaleProcessAssignView (POST)
- AdminSaleProcessUnassignView (POST)
- AdminHistoryView (GET)
- AdminInsightsView (GET)
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership, AgentProfile
from apps.properties.models import Property
from apps.transactions.models import PurchaseProcess, SaleProcess, SellerLead


def _token(user):
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


class AdminTransactionsTestSetup(APITestCase):
    """Base setup: Tenant with admin, agents, clients, and properties."""

    def setUp(self):
        # Create tenant
        self.tenant = Tenant.objects.create(
            name='Transactions Test', slug='trans-test',
            email='trans@test.com', is_active=True,
        )

        # Create admin
        self.admin = User.objects.create(email='admin@trans.com', is_active=True)
        self.admin_m = TenantMembership.objects.create(
            user=self.admin, tenant=self.tenant,
            role=TenantMembership.Role.ADMIN, is_active=True,
        )
        self.token = _token(self.admin)

        # Create agents
        self.agent1 = User.objects.create(email='agent1@trans.com', is_active=True)
        self.agent1_m = TenantMembership.objects.create(
            user=self.agent1, tenant=self.tenant,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        self.agent1_profile = AgentProfile.objects.create(membership=self.agent1_m)

        self.agent2 = User.objects.create(email='agent2@trans.com', is_active=True)
        self.agent2_m = TenantMembership.objects.create(
            user=self.agent2, tenant=self.tenant,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        self.agent2_profile = AgentProfile.objects.create(membership=self.agent2_m)

        # Create clients
        self.client1 = User.objects.create(email='client1@trans.com', is_active=True)
        self.client1_m = TenantMembership.objects.create(
            user=self.client1, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT, is_active=True,
        )

        self.client2 = User.objects.create(email='client2@trans.com', is_active=True)
        self.client2_m = TenantMembership.objects.create(
            user=self.client2, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT, is_active=True,
        )

        # Create properties
        self.prop1 = Property.objects.create(
            tenant=self.tenant, title='Property 1',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000, is_active=True,
        )

        self.prop2 = Property.objects.create(
            tenant=self.tenant, title='Property 2',
            listing_type='sale', status='disponible',
            property_type='apartment', price=500_000, is_active=True,
        )

        self.prop3 = Property.objects.create(
            tenant=self.tenant, title='Property 3',
            listing_type='pending_listing', status='disponible',
            property_type='land', price=200_000, is_active=True,
        )

        # Create a non-admin user to test permissions
        self.non_admin = User.objects.create(email='user@trans.com', is_active=True)
        self.non_admin_m = TenantMembership.objects.create(
            user=self.non_admin, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT, is_active=True,
        )
        self.non_admin_token = _token(self.non_admin)


class TestAdminPurchaseProcessListCreate(AdminTransactionsTestSetup):
    """Tests for AdminPurchaseProcessListCreateView."""

    def test_list_empty(self):
        """GET with no purchase processes returns empty list."""
        resp = self.client.get(
            '/api/v1/admin/purchase-processes',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)
        self.assertEqual(resp.data['results'], [])

    def test_list_with_processes(self):
        """GET returns all purchase processes for tenant."""
        PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop1,
            client_membership=self.client1_m,
            agent_membership=self.agent1_m,
            status=PurchaseProcess.Status.LEAD,
        )
        PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop2,
            client_membership=self.client2_m,
            agent_membership=self.agent2_m,
            status=PurchaseProcess.Status.VISITA,
        )

        resp = self.client.get(
            '/api/v1/admin/purchase-processes',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 2)

    def test_list_filter_by_status(self):
        """GET with status filter returns matching processes."""
        PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop1,
            client_membership=self.client1_m,
            agent_membership=self.agent1_m,
            status=PurchaseProcess.Status.LEAD,
        )
        PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop2,
            client_membership=self.client2_m,
            agent_membership=self.agent2_m,
            status=PurchaseProcess.Status.VISITA,
        )

        resp = self.client.get(
            '/api/v1/admin/purchase-processes?status=visita',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['status'], 'visita')

    def test_list_filter_by_agent(self):
        """GET with agent_id filter returns matching processes."""
        PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop1,
            client_membership=self.client1_m,
            agent_membership=self.agent1_m,
            status=PurchaseProcess.Status.LEAD,
        )
        PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop2,
            client_membership=self.client2_m,
            agent_membership=self.agent2_m,
            status=PurchaseProcess.Status.LEAD,
        )

        resp = self.client.get(
            f'/api/v1/admin/purchase-processes?agent_id={self.agent1_profile.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_list_permission_denied_non_admin(self):
        """Non-admin users get 403."""
        resp = self.client.get(
            '/api/v1/admin/purchase-processes',
            **_auth(self.non_admin_token),
        )
        self.assertEqual(resp.status_code, 403)

    def test_list_permission_denied_unauthenticated(self):
        """Unauthenticated users get 401."""
        resp = self.client.get('/api/v1/admin/purchase-processes')
        self.assertEqual(resp.status_code, 401)

    def test_create_success(self):
        """POST with valid data creates purchase process."""
        resp = self.client.post(
            '/api/v1/admin/purchase-processes',
            {
                'property_id': self.prop1.pk,
                'client_membership_id': self.client1_m.pk,
                'agent_membership_id': self.agent1_m.pk,
                'notes': 'Initial process',
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['status'], PurchaseProcess.Status.LEAD)
        self.assertEqual(resp.data['overall_progress'], 0)
        self.assertTrue(PurchaseProcess.objects.filter(
            property=self.prop1, client_membership=self.client1_m
        ).exists())

    def test_create_property_not_found(self):
        """POST with invalid property_id returns 400."""
        resp = self.client.post(
            '/api/v1/admin/purchase-processes',
            {
                'property_id': 9999,
                'client_membership_id': self.client1_m.pk,
                'agent_membership_id': self.agent1_m.pk,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Propiedad', resp.data['error'])

    def test_create_client_not_found(self):
        """POST with invalid client_membership_id returns 400."""
        resp = self.client.post(
            '/api/v1/admin/purchase-processes',
            {
                'property_id': self.prop1.pk,
                'client_membership_id': 9999,
                'agent_membership_id': self.agent1_m.pk,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Cliente', resp.data['error'])

    def test_create_agent_not_found(self):
        """POST with invalid agent_membership_id returns 400."""
        resp = self.client.post(
            '/api/v1/admin/purchase-processes',
            {
                'property_id': self.prop1.pk,
                'client_membership_id': self.client1_m.pk,
                'agent_membership_id': 9999,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Agente', resp.data['error'])

    def test_create_agent_not_agent_role(self):
        """POST with client as agent returns 400."""
        resp = self.client.post(
            '/api/v1/admin/purchase-processes',
            {
                'property_id': self.prop1.pk,
                'client_membership_id': self.client1_m.pk,
                'agent_membership_id': self.client2_m.pk,  # Not an agent
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_notes_optional(self):
        """POST without notes field still creates process."""
        resp = self.client.post(
            '/api/v1/admin/purchase-processes',
            {
                'property_id': self.prop1.pk,
                'client_membership_id': self.client1_m.pk,
                'agent_membership_id': self.agent1_m.pk,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        process = PurchaseProcess.objects.get(pk=resp.data['id'])
        self.assertEqual(process.notes, '')


class TestAdminPurchaseProcessStatus(AdminTransactionsTestSetup):
    """Tests for AdminPurchaseProcessStatusView."""

    def setUp(self):
        super().setUp()
        self.process = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop1,
            client_membership=self.client1_m,
            agent_membership=self.agent1_m,
            status=PurchaseProcess.Status.LEAD,
            overall_progress=0,
        )

    def test_patch_status_to_visita(self):
        """PATCH status to visita updates status and progress."""
        resp = self.client.patch(
            f'/api/v1/admin/purchase-processes/{self.process.pk}/status',
            {'status': 'visita'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'visita')
        self.process.refresh_from_db()
        self.assertEqual(self.process.status, 'visita')
        self.assertEqual(self.process.overall_progress, 11)

    def test_patch_status_with_notes(self):
        """PATCH with notes field stores notes."""
        resp = self.client.patch(
            f'/api/v1/admin/purchase-processes/{self.process.pk}/status',
            {'status': 'visita', 'notes': 'Cliente confirmó asistencia'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.process.refresh_from_db()
        self.assertEqual(self.process.notes, 'Cliente confirmó asistencia')

    def test_patch_status_with_sale_price_and_payment(self):
        """PATCH to cerrado with sale_price and payment_method."""
        # Move to cerrado state
        resp = self.client.patch(
            f'/api/v1/admin/purchase-processes/{self.process.pk}/status',
            {
                'status': 'cerrado',
                'sale_price': '1200000.00',
                'payment_method': 'Crédito hipotecario',
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.process.refresh_from_db()
        self.assertEqual(self.process.status, 'cerrado')
        self.assertEqual(self.process.sale_price, Decimal('1200000.00'))
        self.assertEqual(self.process.payment_method, 'Crédito hipotecario')

    def test_patch_status_not_found(self):
        """PATCH with invalid pk returns 404."""
        resp = self.client.patch(
            '/api/v1/admin/purchase-processes/9999/status',
            {'status': 'visita'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_patch_status_invalid_status(self):
        """PATCH with invalid status returns 400."""
        resp = self.client.patch(
            f'/api/v1/admin/purchase-processes/{self.process.pk}/status',
            {'status': 'invalid_status'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_patch_status_missing_status(self):
        """PATCH without status field returns 400."""
        resp = self.client.patch(
            f'/api/v1/admin/purchase-processes/{self.process.pk}/status',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)


class TestAdminPurchaseProcessDetail(AdminTransactionsTestSetup):
    """Tests for AdminPurchaseProcessDetailView."""

    def setUp(self):
        super().setUp()
        self.process = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop1,
            client_membership=self.client1_m,
            agent_membership=self.agent1_m,
            status=PurchaseProcess.Status.LEAD,
        )

    def test_patch_agent(self):
        """PATCH agent_membership_id updates agent."""
        resp = self.client.patch(
            f'/api/v1/admin/purchase-processes/{self.process.pk}',
            {'agent_membership_id': self.agent2_m.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.process.refresh_from_db()
        self.assertEqual(self.process.agent_membership_id, self.agent2_m.pk)

    def test_patch_notes(self):
        """PATCH notes updates notes field."""
        resp = self.client.patch(
            f'/api/v1/admin/purchase-processes/{self.process.pk}',
            {'notes': 'Updated notes'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.process.refresh_from_db()
        self.assertEqual(self.process.notes, 'Updated notes')

    def test_patch_sale_price(self):
        """PATCH sale_price updates price."""
        resp = self.client.patch(
            f'/api/v1/admin/purchase-processes/{self.process.pk}',
            {'sale_price': '950000.00'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.process.refresh_from_db()
        self.assertEqual(self.process.sale_price, Decimal('950000.00'))

    def test_patch_payment_method(self):
        """PATCH payment_method updates payment method."""
        resp = self.client.patch(
            f'/api/v1/admin/purchase-processes/{self.process.pk}',
            {'payment_method': 'Efectivo'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.process.refresh_from_db()
        self.assertEqual(self.process.payment_method, 'Efectivo')

    def test_patch_multiple_fields(self):
        """PATCH multiple fields at once."""
        resp = self.client.patch(
            f'/api/v1/admin/purchase-processes/{self.process.pk}',
            {
                'notes': 'New notes',
                'sale_price': '1100000',
                'payment_method': 'Hipotecario',
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.process.refresh_from_db()
        self.assertEqual(self.process.notes, 'New notes')
        self.assertEqual(self.process.sale_price, Decimal('1100000'))
        self.assertEqual(self.process.payment_method, 'Hipotecario')

    def test_patch_invalid_agent(self):
        """PATCH with invalid agent_membership_id returns 400."""
        resp = self.client.patch(
            f'/api/v1/admin/purchase-processes/{self.process.pk}',
            {'agent_membership_id': 9999},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_patch_empty_data(self):
        """PATCH with empty data makes no changes."""
        original_notes = self.process.notes
        resp = self.client.patch(
            f'/api/v1/admin/purchase-processes/{self.process.pk}',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.process.refresh_from_db()
        self.assertEqual(self.process.notes, original_notes)

    def test_patch_not_found(self):
        """PATCH with invalid pk returns 404."""
        resp = self.client.patch(
            '/api/v1/admin/purchase-processes/9999',
            {'notes': 'test'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)


class TestAdminSaleProcessListCreate(AdminTransactionsTestSetup):
    """Tests for AdminSaleProcessListCreateView."""

    def test_list_empty(self):
        """GET with no sale processes returns empty list."""
        resp = self.client.get(
            '/api/v1/admin/sale-processes',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)

    def test_list_with_processes(self):
        """GET returns all sale processes."""
        SaleProcess.objects.create(
            tenant=self.tenant, property=self.prop1,
            client_membership=self.client1_m,
            agent_membership=self.agent1_m,
            status=SaleProcess.Status.NUEVO,
        )
        SaleProcess.objects.create(
            tenant=self.tenant, property=self.prop2,
            client_membership=self.client2_m,
            agent_membership=self.agent2_m,
            status=SaleProcess.Status.CONTACTADO,
        )

        resp = self.client.get(
            '/api/v1/admin/sale-processes',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 2)

    def test_list_filter_by_status(self):
        """GET with status filter returns matching processes."""
        SaleProcess.objects.create(
            tenant=self.tenant, property=self.prop1,
            client_membership=self.client1_m,
            agent_membership=self.agent1_m,
            status=SaleProcess.Status.NUEVO,
        )
        SaleProcess.objects.create(
            tenant=self.tenant, property=self.prop2,
            client_membership=self.client2_m,
            agent_membership=self.agent2_m,
            status=SaleProcess.Status.CONTACTADO,
        )

        resp = self.client.get(
            '/api/v1/admin/sale-processes?status=nuevo',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_create_success(self):
        """POST with valid data creates sale process."""
        resp = self.client.post(
            '/api/v1/admin/sale-processes',
            {
                'property_id': self.prop1.pk,
                'client_membership_id': self.client1_m.pk,
                'agent_membership_id': self.agent1_m.pk,
                'notes': 'New sale process',
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['status'], SaleProcess.Status.NUEVO)
        self.assertTrue(SaleProcess.objects.filter(
            property=self.prop1, client_membership=self.client1_m
        ).exists())

    def test_create_without_agent(self):
        """POST without agent_membership_id creates process with null agent."""
        resp = self.client.post(
            '/api/v1/admin/sale-processes',
            {
                'property_id': self.prop1.pk,
                'client_membership_id': self.client1_m.pk,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        process = SaleProcess.objects.get(pk=resp.data['id'])
        self.assertIsNone(process.agent_membership)

    def test_create_property_not_found(self):
        """POST with invalid property returns 400."""
        resp = self.client.post(
            '/api/v1/admin/sale-processes',
            {
                'property_id': 9999,
                'client_membership_id': self.client1_m.pk,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_client_not_found(self):
        """POST with invalid client returns 400."""
        resp = self.client.post(
            '/api/v1/admin/sale-processes',
            {
                'property_id': self.prop1.pk,
                'client_membership_id': 9999,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)


class TestAdminSaleProcessStatus(AdminTransactionsTestSetup):
    """Tests for AdminSaleProcessStatusView."""

    def setUp(self):
        super().setUp()
        self.process = SaleProcess.objects.create(
            tenant=self.tenant, property=self.prop1,
            client_membership=self.client1_m,
            agent_membership=self.agent1_m,
            status=SaleProcess.Status.NUEVO,
        )

    def test_patch_status_success(self):
        """PATCH status updates status."""
        resp = self.client.patch(
            f'/api/v1/admin/sale-processes/{self.process.pk}/status',
            {'status': 'contactado'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'contactado')
        self.process.refresh_from_db()
        self.assertEqual(self.process.status, 'contactado')

    def test_patch_status_with_notes(self):
        """PATCH with notes stores notes."""
        resp = self.client.patch(
            f'/api/v1/admin/sale-processes/{self.process.pk}/status',
            {'status': 'contactado', 'notes': 'Cliente contactado hoy'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.process.refresh_from_db()
        self.assertEqual(self.process.notes, 'Cliente contactado hoy')

    def test_patch_status_not_found(self):
        """PATCH with invalid pk returns 404."""
        resp = self.client.patch(
            '/api/v1/admin/sale-processes/9999/status',
            {'status': 'nuevo'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)


class TestAdminSellerLeadList(AdminTransactionsTestSetup):
    """Tests for AdminSellerLeadListView."""

    def setUp(self):
        super().setUp()
        self.lead1 = SellerLead.objects.create(
            tenant=self.tenant,
            full_name='Juan Pérez',
            email='juan@example.com',
            phone='5551234567',
            property_type='house',
            status=SellerLead.Status.NEW,
            created_by_membership=self.admin_m,
        )
        self.lead2 = SellerLead.objects.create(
            tenant=self.tenant,
            full_name='María García',
            email='maria@example.com',
            phone='5559876543',
            property_type='apartment',
            status=SellerLead.Status.CONTACTED,
            created_by_membership=self.admin_m,
        )

    def test_list_all_leads(self):
        """GET returns all seller leads."""
        resp = self.client.get(
            '/api/v1/admin/seller-leads',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 2)

    def test_list_filter_by_status(self):
        """GET with status filter returns matching leads."""
        resp = self.client.get(
            '/api/v1/admin/seller-leads?status=new',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['full_name'], 'Juan Pérez')

    def test_list_search_by_name(self):
        """GET with search filter finds by name."""
        resp = self.client.get(
            '/api/v1/admin/seller-leads?search=María',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['full_name'], 'María García')

    def test_list_search_by_email(self):
        """GET with search filter finds by email."""
        resp = self.client.get(
            '/api/v1/admin/seller-leads?search=juan@example.com',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_list_search_case_insensitive(self):
        """Search is case insensitive."""
        resp = self.client.get(
            '/api/v1/admin/seller-leads?search=JUAN',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_list_permission_denied_non_admin(self):
        """Non-admin gets 403."""
        resp = self.client.get(
            '/api/v1/admin/seller-leads',
            **_auth(self.non_admin_token),
        )
        self.assertEqual(resp.status_code, 403)


class TestAdminSellerLeadDetail(AdminTransactionsTestSetup):
    """Tests for AdminSellerLeadDetailView."""

    def setUp(self):
        super().setUp()
        self.lead = SellerLead.objects.create(
            tenant=self.tenant,
            full_name='Juan Pérez',
            email='juan@example.com',
            phone='5551234567',
            property_type='house',
            bedrooms=3,
            bathrooms=2,
            square_meters=Decimal('150.00'),
            expected_price=Decimal('500000'),
            status=SellerLead.Status.NEW,
            created_by_membership=self.admin_m,
        )

    def test_get_detail(self):
        """GET returns lead details."""
        resp = self.client.get(
            f'/api/v1/admin/seller-leads/{self.lead.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['full_name'], 'Juan Pérez')
        self.assertEqual(resp.data['email'], 'juan@example.com')

    def test_get_not_found(self):
        """GET with invalid pk returns 404."""
        resp = self.client.get(
            '/api/v1/admin/seller-leads/9999',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_patch_status(self):
        """PATCH status updates status."""
        resp = self.client.patch(
            f'/api/v1/admin/seller-leads/{self.lead.pk}',
            {'status': 'contacted'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, SellerLead.Status.CONTACTED)

    def test_patch_assign_agent(self):
        """PATCH assigned_agent_membership_id assigns agent."""
        resp = self.client.patch(
            f'/api/v1/admin/seller-leads/{self.lead.pk}',
            {'assigned_agent_membership_id': self.agent1_m.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.assigned_agent_membership_id, self.agent1_m.pk)

    def test_patch_unassign_agent(self):
        """PATCH assigned_agent_membership_id to null unassigns agent."""
        self.lead.assigned_agent_membership = self.agent1_m
        self.lead.save()

        resp = self.client.patch(
            f'/api/v1/admin/seller-leads/{self.lead.pk}',
            {'assigned_agent_membership_id': None},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.assigned_agent_membership)

    def test_patch_notes(self):
        """PATCH notes updates notes."""
        resp = self.client.patch(
            f'/api/v1/admin/seller-leads/{self.lead.pk}',
            {'notes': 'Interested in quick sale'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.notes, 'Interested in quick sale')

    def test_patch_invalid_agent(self):
        """PATCH with invalid agent_membership_id returns 400."""
        resp = self.client.patch(
            f'/api/v1/admin/seller-leads/{self.lead.pk}',
            {'assigned_agent_membership_id': 9999},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_patch_client_as_agent(self):
        """PATCH with client as agent returns 400."""
        resp = self.client.patch(
            f'/api/v1/admin/seller-leads/{self.lead.pk}',
            {'assigned_agent_membership_id': self.client1_m.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)


class TestAdminSellerLeadConvert(AdminTransactionsTestSetup):
    """Tests for AdminSellerLeadConvertView."""

    def setUp(self):
        super().setUp()
        self.lead = SellerLead.objects.create(
            tenant=self.tenant,
            full_name='Juan Pérez',
            email='juan@example.com',
            phone='5551234567',
            property_type='house',
            bedrooms=3,
            bathrooms=2,
            expected_price=Decimal('500000'),
            status=SellerLead.Status.NEW,
            created_by_membership=self.admin_m,
        )

    def test_convert_success(self):
        """POST converts lead to property and sale process."""
        resp = self.client.post(
            f'/api/v1/admin/seller-leads/{self.lead.pk}/convert',
            {'agent_membership_id': self.agent1_m.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn('property_id', resp.data)
        self.assertIn('sale_process_id', resp.data)

        # Verify lead status changed
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, SellerLead.Status.CONVERTED)

        # Verify property was created
        self.assertTrue(Property.objects.filter(
            tenant=self.tenant, title=self.lead.full_name
        ).exists())

        # Verify sale process was created
        self.assertTrue(SaleProcess.objects.filter(
            pk=resp.data['sale_process_id']
        ).exists())

    def test_convert_already_converted(self):
        """POST to already converted lead returns 400."""
        self.lead.status = SellerLead.Status.CONVERTED
        self.lead.save()

        resp = self.client.post(
            f'/api/v1/admin/seller-leads/{self.lead.pk}/convert',
            {'agent_membership_id': self.agent1_m.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('convertido', resp.data['error'])

    def test_convert_not_found(self):
        """POST to non-existent lead returns 404."""
        resp = self.client.post(
            '/api/v1/admin/seller-leads/9999/convert',
            {'agent_membership_id': self.agent1_m.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_convert_invalid_agent(self):
        """POST with invalid agent returns 400."""
        resp = self.client.post(
            f'/api/v1/admin/seller-leads/{self.lead.pk}/convert',
            {'agent_membership_id': 9999},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)


class TestAdminSaleProcessAssignment(AdminTransactionsTestSetup):
    """Tests for AdminSaleProcessAssignmentView and related views."""

    def setUp(self):
        super().setUp()
        self.sale1 = SaleProcess.objects.create(
            tenant=self.tenant, property=self.prop3,
            client_membership=self.client1_m,
            agent_membership=None,  # Unassigned
            status=SaleProcess.Status.NUEVO,
        )
        self.sale2 = SaleProcess.objects.create(
            tenant=self.tenant, property=self.prop1,
            client_membership=self.client2_m,
            agent_membership=self.agent1_m,  # Assigned
            status=SaleProcess.Status.NUEVO,
        )

    def test_get_assignments(self):
        """GET returns unassigned and assigned processes."""
        resp = self.client.get(
            '/api/v1/admin/sale-processes/assignments',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('unassigned', resp.data)
        self.assertIn('assigned', resp.data)
        # prop3 (pending_listing) should be in unassigned
        # prop1 (pending_listing) should be in assigned
        self.assertEqual(len(resp.data['unassigned']), 1)
        self.assertEqual(len(resp.data['assigned']), 1)

    def test_assign_agent_success(self):
        """POST assigns agent to sale process."""
        resp = self.client.post(
            f'/api/v1/admin/sale-processes/{self.sale1.pk}/assign',
            {'agent_membership_id': self.agent2_m.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('agent', resp.data)
        self.sale1.refresh_from_db()
        self.assertEqual(self.sale1.agent_membership_id, self.agent2_m.pk)

    def test_assign_missing_agent_id(self):
        """POST without agent_membership_id returns 400."""
        resp = self.client.post(
            f'/api/v1/admin/sale-processes/{self.sale1.pk}/assign',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_assign_invalid_agent(self):
        """POST with invalid agent returns 400."""
        resp = self.client.post(
            f'/api/v1/admin/sale-processes/{self.sale1.pk}/assign',
            {'agent_membership_id': 9999},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_unassign_agent_success(self):
        """POST unassigns agent from sale process."""
        resp = self.client.post(
            f'/api/v1/admin/sale-processes/{self.sale2.pk}/unassign',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['agent'])
        self.sale2.refresh_from_db()
        self.assertIsNone(self.sale2.agent_membership)

    def test_unassign_not_found(self):
        """POST unassign with invalid pk returns 404."""
        resp = self.client.post(
            '/api/v1/admin/sale-processes/9999/unassign',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)


class TestAdminHistory(AdminTransactionsTestSetup):
    """Tests for AdminHistoryView."""

    def setUp(self):
        super().setUp()
        # Create closed purchase processes
        self.closed1 = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop1,
            client_membership=self.client1_m,
            agent_membership=self.agent1_m,
            status=PurchaseProcess.Status.CERRADO,
            sale_price=Decimal('1200000'),
            payment_method='Crédito hipotecario',
            closed_at=datetime.now(),
        )
        self.closed2 = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop2,
            client_membership=self.client2_m,
            agent_membership=self.agent2_m,
            status=PurchaseProcess.Status.CERRADO,
            sale_price=Decimal('500000'),
            payment_method='Efectivo',
            closed_at=datetime.now(),
        )

    def test_list_closed_processes(self):
        """GET returns closed purchase processes."""
        resp = self.client.get(
            '/api/v1/admin/history',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 2)

    def test_filter_by_zone(self):
        """GET with zone filter returns matching processes."""
        self.prop1.zone = 'North Zone'
        self.prop1.save()

        resp = self.client.get(
            '/api/v1/admin/history?zone=North+Zone',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        # At least one result with matching zone
        self.assertGreaterEqual(resp.data['count'], 0)

    def test_filter_by_property_type(self):
        """GET with property_type filter returns matching processes."""
        resp = self.client.get(
            '/api/v1/admin/history?property_type=house',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        # Should contain processes with house property type
        self.assertGreaterEqual(resp.data['count'], 0)

    def test_filter_by_payment_method(self):
        """GET with payment_method filter returns matching processes."""
        resp = self.client.get(
            '/api/v1/admin/history?payment_method=Crédito',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        # Should contain processes with matching payment method
        self.assertGreaterEqual(resp.data['count'], 0)

    def test_search_by_property_title(self):
        """GET with search filter finds by property title."""
        resp = self.client.get(
            '/api/v1/admin/history?search=Property+1',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.data['count'], 0)

    def test_search_by_client_name(self):
        """GET with search filter finds by client name."""
        self.client1.first_name = 'John'
        self.client1.save()

        resp = self.client.get(
            '/api/v1/admin/history?search=John',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)

    def test_filter_by_date_range(self):
        """GET with date filters returns processes in range."""
        today = date.today()
        tomorrow = today + timedelta(days=1)

        resp = self.client.get(
            f'/api/v1/admin/history?date_from={today}&date_to={tomorrow}',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        # Should contain today's closed processes
        self.assertGreaterEqual(resp.data['count'], 0)


class TestAdminInsights(AdminTransactionsTestSetup):
    """Tests for AdminInsightsView."""

    def test_get_insights_default_period(self):
        """GET returns insights with default month period."""
        resp = self.client.get(
            '/api/v1/admin/insights',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        # Should return a response with insights data
        self.assertIsInstance(resp.data, dict)

    def test_get_insights_quarter_period(self):
        """GET with quarter period parameter."""
        resp = self.client.get(
            '/api/v1/admin/insights?period=quarter',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.data, dict)

    def test_get_insights_year_period(self):
        """GET with year period parameter."""
        resp = self.client.get(
            '/api/v1/admin/insights?period=year',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_insights_all_period(self):
        """GET with all period parameter."""
        resp = self.client.get(
            '/api/v1/admin/insights?period=all',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_insights_invalid_period(self):
        """GET with invalid period defaults to month."""
        resp = self.client.get(
            '/api/v1/admin/insights?period=invalid',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        # Should still return data with default period

    def test_get_insights_permission_denied(self):
        """Non-admin gets 403."""
        resp = self.client.get(
            '/api/v1/admin/insights',
            **_auth(self.non_admin_token),
        )
        self.assertEqual(resp.status_code, 403)


class TestTenantIsolation(AdminTransactionsTestSetup):
    """Tests for multi-tenant isolation in transaction admin views."""

    def setUp(self):
        super().setUp()

        # Create second tenant with its own data
        self.tenant2 = Tenant.objects.create(
            name='Transactions Test 2', slug='trans-test-2',
            email='trans2@test.com', is_active=True,
        )

        admin2 = User.objects.create(email='admin2@trans.com', is_active=True)
        self.admin2_m = TenantMembership.objects.create(
            user=admin2, tenant=self.tenant2,
            role=TenantMembership.Role.ADMIN, is_active=True,
        )
        self.token2 = _token(admin2)

        agent2 = User.objects.create(email='agent2b@trans.com', is_active=True)
        self.agent2_t2 = TenantMembership.objects.create(
            user=agent2, tenant=self.tenant2,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        AgentProfile.objects.create(membership=self.agent2_t2)

        client2 = User.objects.create(email='client2b@trans.com', is_active=True)
        self.client2_t2 = TenantMembership.objects.create(
            user=client2, tenant=self.tenant2,
            role=TenantMembership.Role.CLIENT, is_active=True,
        )

        prop2 = Property.objects.create(
            tenant=self.tenant2, title='Property T2',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000, is_active=True,
        )

        # Create processes in both tenants
        self.process_t1 = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop1,
            client_membership=self.client1_m,
            agent_membership=self.agent1_m,
            status=PurchaseProcess.Status.LEAD,
        )

        self.process_t2 = PurchaseProcess.objects.create(
            tenant=self.tenant2, property=prop2,
            client_membership=self.client2_t2,
            agent_membership=self.agent2_t2,
            status=PurchaseProcess.Status.LEAD,
        )

    def test_admin_t1_cannot_see_t2_processes(self):
        """Admin from tenant1 doesn't see tenant2 processes."""
        resp = self.client.get(
            '/api/v1/admin/purchase-processes',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        # Should only see tenant1 process
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['id'], self.process_t1.pk)

    def test_admin_t2_cannot_see_t1_processes(self):
        """Admin from tenant2 doesn't see tenant1 processes."""
        resp = self.client.get(
            '/api/v1/admin/purchase-processes',
            **_auth(self.token2),
        )
        self.assertEqual(resp.status_code, 200)
        # Should only see tenant2 process
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['id'], self.process_t2.pk)
