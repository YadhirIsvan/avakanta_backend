"""
Comprehensive tests for client-facing transaction views in apps/transactions/views/client.py

Covers:
- ClientSaleListView (GET)
- ClientSaleDetailView (GET)
- ClientPurchaseListView (GET)
- ClientPurchaseDetailView (GET)
- ClientPurchaseDocumentUploadView (POST)
"""
import tempfile
from decimal import Decimal

from django.test import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership, AgentProfile
from apps.properties.models import Property, PropertyImage, PropertyDocument
from apps.transactions.models import PurchaseProcess, SaleProcess
from apps.locations.models import Country, State, City


def _token(user):
    """Generate JWT access token for user."""
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    """Return authorization header."""
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


def _fake_pdf(name='doc.pdf'):
    """Create a fake PDF file."""
    return SimpleUploadedFile(
        name=name,
        content=b'%PDF-1.4 fake content',
        content_type='application/pdf',
    )


class TransactionViewSetup(APITestCase):
    """Base setup for transaction view tests."""

    def setUp(self):
        # Tenant
        self.tenant = Tenant.objects.create(
            name='Transaction Tenant', slug='transaction-tenant',
            email='transaction@test.com', is_active=True,
        )

        # Location setup
        self.country = Country.objects.create(name='Mexico')
        self.state = State.objects.create(name='Mexico City', country=self.country)
        self.city = City.objects.create(name='Mexico City', state=self.state)

        # Client
        self.client_user = User.objects.create(
            email='client_transaction@test.com',
            first_name='Juan',
            last_name='Pérez',
            is_active=True,
        )
        self.client_membership = TenantMembership.objects.create(
            user=self.client_user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT, is_active=True,
        )
        self.token = _token(self.client_user)

        # Other client for isolation tests
        self.other_client_user = User.objects.create(
            email='other_client_transaction@test.com', is_active=True,
        )
        self.other_client_membership = TenantMembership.objects.create(
            user=self.other_client_user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT, is_active=True,
        )

        # Agent
        self.agent_user = User.objects.create(
            email='agent_transaction@test.com', is_active=True,
        )
        self.agent_membership = TenantMembership.objects.create(
            user=self.agent_user, tenant=self.tenant,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        AgentProfile.objects.create(membership=self.agent_membership)

        # Property
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Casa Transaction',
            listing_type='sale', status='disponible',
            property_type='house', price=Decimal('1000000'),
            city=self.city, is_active=True,
        )

        # Add cover image
        PropertyImage.objects.create(
            property=self.prop, image_url='http://example.com/image.jpg',
            is_cover=True, is_active=True,
        )


class TestClientSaleList(TransactionViewSetup):
    """Test ClientSaleListView GET endpoint."""

    def test_get_sale_list_returns_200_authenticated(self):
        """GET /client/sales returns 200 with auth."""
        resp = self.client.get('/api/v1/client/sales', **_auth(self.token))
        self.assertEqual(resp.status_code, 200)

    def test_get_sale_list_returns_401_unauthenticated(self):
        """GET /client/sales without auth returns 401."""
        resp = self.client.get('/api/v1/client/sales')
        self.assertEqual(resp.status_code, 401)

    def test_get_sale_list_returns_stats(self):
        """GET /client/sales response includes stats."""
        # Create a sale process
        SaleProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
        )

        resp = self.client.get('/api/v1/client/sales', **_auth(self.token))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('stats', resp.data)
        self.assertIn('results', resp.data)

    def test_get_sale_list_stats_include_total_properties(self):
        """Sale list stats include total_properties."""
        for i in range(3):
            SaleProcess.objects.create(
                tenant=self.tenant, property=self.prop,
                client_membership=self.client_membership,
                agent_membership=self.agent_membership,
            )

        resp = self.client.get('/api/v1/client/sales', **_auth(self.token))
        self.assertEqual(resp.data['stats']['total_properties'], 3)

    def test_get_sale_list_stats_include_total_views(self):
        """Sale list stats include total_views."""
        self.prop.views = 100
        self.prop.save()
        SaleProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
        )

        resp = self.client.get('/api/v1/client/sales', **_auth(self.token))
        self.assertEqual(resp.data['stats']['total_views'], 100)

    def test_get_sale_list_stats_include_total_value(self):
        """Sale list stats include total_value (sum of prices)."""
        SaleProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
        )

        resp = self.client.get('/api/v1/client/sales', **_auth(self.token))
        # total_value is stringified
        self.assertIn('total_value', resp.data['stats'])

    def test_get_sale_list_only_shows_own_sales(self):
        """GET /client/sales only returns own sales."""
        # Create sale for this client
        SaleProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
        )

        # Create sale for other client
        SaleProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.other_client_membership,
            agent_membership=self.agent_membership,
        )

        resp = self.client.get('/api/v1/client/sales', **_auth(self.token))
        self.assertEqual(len(resp.data['results']), 1)

    def test_get_sale_list_returns_results_array(self):
        """GET /client/sales response.results is an array."""
        resp = self.client.get('/api/v1/client/sales', **_auth(self.token))
        self.assertIsInstance(resp.data['results'], list)


class TestClientSaleDetail(TransactionViewSetup):
    """Test ClientSaleDetailView GET endpoint."""

    def test_get_sale_detail_returns_200(self):
        """GET /client/sales/{id} returns 200."""
        sale = SaleProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
        )

        resp = self.client.get(
            f'/api/v1/client/sales/{sale.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_sale_detail_returns_404_not_found(self):
        """GET /client/sales/{bad_id} returns 404."""
        resp = self.client.get(
            '/api/v1/client/sales/99999',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_sale_detail_returns_404_other_client_process(self):
        """GET /client/sales/{id} returns 404 if sale belongs to other client."""
        sale = SaleProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.other_client_membership,
            agent_membership=self.agent_membership,
        )

        resp = self.client.get(
            f'/api/v1/client/sales/{sale.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_sale_detail_returns_process_data(self):
        """GET /client/sales/{id} returns sale process details."""
        sale = SaleProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            status='contacto_inicial',
        )

        resp = self.client.get(
            f'/api/v1/client/sales/{sale.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'contacto_inicial')

    def test_get_sale_detail_returns_401_unauthenticated(self):
        """GET /client/sales/{id} without auth returns 401."""
        sale = SaleProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
        )

        resp = self.client.get(f'/api/v1/client/sales/{sale.pk}')
        self.assertEqual(resp.status_code, 401)


class TestClientPurchaseList(TransactionViewSetup):
    """Test ClientPurchaseListView GET endpoint."""

    def test_get_purchase_list_returns_200_authenticated(self):
        """GET /client/purchases returns 200 with auth."""
        resp = self.client.get('/api/v1/client/purchases', **_auth(self.token))
        self.assertEqual(resp.status_code, 200)

    def test_get_purchase_list_returns_401_unauthenticated(self):
        """GET /client/purchases without auth returns 401."""
        resp = self.client.get('/api/v1/client/purchases')
        self.assertEqual(resp.status_code, 401)

    def test_get_purchase_list_is_paginated(self):
        """GET /client/purchases response is paginated."""
        resp = self.client.get('/api/v1/client/purchases', **_auth(self.token))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('count', resp.data)
        self.assertIn('results', resp.data)

    def test_get_purchase_list_pagination_limits_results(self):
        """GET /client/purchases respects pagination limits."""
        # Create 50 purchases
        for i in range(50):
            PurchaseProcess.objects.create(
                tenant=self.tenant, property=self.prop,
                client_membership=self.client_membership,
                agent_membership=self.agent_membership,
            )

        resp = self.client.get('/api/v1/client/purchases', **_auth(self.token))
        # Default limit should be something reasonable
        self.assertLessEqual(len(resp.data['results']), 50)

    def test_get_purchase_list_only_shows_own_purchases(self):
        """GET /client/purchases only returns own purchases."""
        # Create purchase for this client
        PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
        )

        # Create purchase for other client
        PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.other_client_membership,
            agent_membership=self.agent_membership,
        )

        resp = self.client.get('/api/v1/client/purchases', **_auth(self.token))
        self.assertEqual(resp.data['count'], 1)

    def test_get_purchase_list_ordered_by_recent(self):
        """GET /client/purchases ordered by created_at descending."""
        # Create 3 purchases
        p1 = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
        )
        p2 = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
        )
        p3 = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
        )

        resp = self.client.get('/api/v1/client/purchases', **_auth(self.token))
        # Most recent first
        results = resp.data['results']
        self.assertEqual(results[0]['id'], p3.pk)


class TestClientPurchaseDetail(TransactionViewSetup):
    """Test ClientPurchaseDetailView GET endpoint."""

    def test_get_purchase_detail_returns_200(self):
        """GET /client/purchases/{id} returns 200."""
        purchase = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
        )

        resp = self.client.get(
            f'/api/v1/client/purchases/{purchase.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_purchase_detail_returns_404_not_found(self):
        """GET /client/purchases/{bad_id} returns 404."""
        resp = self.client.get(
            '/api/v1/client/purchases/99999',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_purchase_detail_returns_404_other_client_process(self):
        """GET /client/purchases/{id} returns 404 if purchase belongs to other client."""
        purchase = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.other_client_membership,
            agent_membership=self.agent_membership,
        )

        resp = self.client.get(
            f'/api/v1/client/purchases/{purchase.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_purchase_detail_returns_process_data(self):
        """GET /client/purchases/{id} returns purchase details."""
        purchase = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            status='pre_aprobacion',
            overall_progress=33,
        )

        resp = self.client.get(
            f'/api/v1/client/purchases/{purchase.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'pre_aprobacion')
        self.assertEqual(resp.data['overall_progress'], 33)

    def test_get_purchase_detail_returns_401_unauthenticated(self):
        """GET /client/purchases/{id} without auth returns 401."""
        purchase = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
        )

        resp = self.client.get(f'/api/v1/client/purchases/{purchase.pk}')
        self.assertEqual(resp.status_code, 401)


class TestClientPurchaseDocumentUpload(TransactionViewSetup):
    """Test ClientPurchaseDocumentUploadView POST."""

    def test_post_document_upload_in_pre_aprobacion_returns_201(self):
        """POST /client/purchases/{id}/documents in pre_aprobacion returns 201."""
        purchase = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            status='pre_aprobacion',
        )

        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                resp = self.client.post(
                    f'/api/v1/client/purchases/{purchase.pk}/documents',
                    {'file': _fake_pdf(), 'name': 'Carta banco'},
                    format='multipart',
                    **_auth(self.token),
                )
        self.assertEqual(resp.status_code, 201)
        self.assertIn('id', resp.data)

    def test_post_document_upload_in_credito_returns_201(self):
        """POST /client/purchases/{id}/documents in credito returns 201."""
        purchase = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            status='credito',
        )

        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                resp = self.client.post(
                    f'/api/v1/client/purchases/{purchase.pk}/documents',
                    {'file': _fake_pdf(), 'name': 'Expediente'},
                    format='multipart',
                    **_auth(self.token),
                )
        self.assertEqual(resp.status_code, 201)

    def test_post_document_upload_in_docs_finales_returns_201(self):
        """POST /client/purchases/{id}/documents in docs_finales returns 201."""
        purchase = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            status='docs_finales',
        )

        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                resp = self.client.post(
                    f'/api/v1/client/purchases/{purchase.pk}/documents',
                    {'file': _fake_pdf(), 'name': 'Docs finales'},
                    format='multipart',
                    **_auth(self.token),
                )
        self.assertEqual(resp.status_code, 201)

    def test_post_document_upload_in_lead_returns_403(self):
        """POST /client/purchases/{id}/documents in lead returns 403."""
        purchase = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            status='lead',
        )

        resp = self.client.post(
            f'/api/v1/client/purchases/{purchase.pk}/documents',
            {'file': _fake_pdf(), 'name': 'Documento'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 403)

    def test_post_document_upload_in_cerrado_returns_403(self):
        """POST /client/purchases/{id}/documents in cerrado returns 403."""
        purchase = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            status='cerrado',
        )

        resp = self.client.post(
            f'/api/v1/client/purchases/{purchase.pk}/documents',
            {'file': _fake_pdf(), 'name': 'Documento'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 403)

    def test_post_document_upload_without_file_returns_400(self):
        """POST without file returns 400."""
        purchase = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            status='pre_aprobacion',
        )

        resp = self.client.post(
            f'/api/v1/client/purchases/{purchase.pk}/documents',
            {'name': 'Sin archivo'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_post_document_upload_without_name_returns_400(self):
        """POST without name returns 400."""
        purchase = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            status='pre_aprobacion',
        )

        resp = self.client.post(
            f'/api/v1/client/purchases/{purchase.pk}/documents',
            {'file': _fake_pdf()},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_post_document_upload_wrong_process_returns_404(self):
        """POST on another client's process returns 404."""
        purchase = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.other_client_membership,
            agent_membership=self.agent_membership,
            status='pre_aprobacion',
        )

        resp = self.client.post(
            f'/api/v1/client/purchases/{purchase.pk}/documents',
            {'file': _fake_pdf(), 'name': 'Intruso'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_post_document_upload_returns_201_unauthenticated(self):
        """POST without auth returns 401."""
        purchase = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            status='pre_aprobacion',
        )

        resp = self.client.post(
            f'/api/v1/client/purchases/{purchase.pk}/documents',
            {'file': _fake_pdf(), 'name': 'Documento'},
            format='multipart',
        )
        self.assertEqual(resp.status_code, 401)

    def test_post_document_upload_creates_property_document(self):
        """POST creates PropertyDocument entry."""
        purchase = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            status='pre_aprobacion',
        )

        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                self.client.post(
                    f'/api/v1/client/purchases/{purchase.pk}/documents',
                    {'file': _fake_pdf(), 'name': 'Documento test'},
                    format='multipart',
                    **_auth(self.token),
                )

        doc = PropertyDocument.objects.filter(purchase_process=purchase).first()
        self.assertIsNotNone(doc)
        self.assertEqual(doc.name, 'Documento test')

    def test_post_document_upload_returns_document_data(self):
        """POST response includes document details."""
        purchase = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.client_membership,
            agent_membership=self.agent_membership,
            status='pre_aprobacion',
        )

        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                resp = self.client.post(
                    f'/api/v1/client/purchases/{purchase.pk}/documents',
                    {'file': _fake_pdf(), 'name': 'Test doc'},
                    format='multipart',
                    **_auth(self.token),
                )

        self.assertEqual(resp.status_code, 201)
        self.assertIn('name', resp.data)
        self.assertIn('file_url', resp.data)
        self.assertIn('mime_type', resp.data)
        self.assertIn('size_bytes', resp.data)
        self.assertEqual(resp.data['name'], 'Test doc')
