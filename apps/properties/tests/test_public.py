from rest_framework.test import APITestCase

from apps.tenants.models import Tenant
from apps.properties.models import Property


LIST_URL = '/api/v1/public/properties'


def _detail(pk):
    return f'/api/v1/public/properties/{pk}'


class PublicPropertyListTestCase(APITestCase):
    """Tests for GET /public/properties."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Test Tenant', slug='test-tenant',
            email='t@test.com',
        )
        # Visible property (listing_type=sale, status=disponible)
        self.prop_visible = Property.objects.create(
            tenant=self.tenant, title='Casa visible',
            listing_type='sale', status='disponible',
            property_type='house', price=1_500_000,
        )
        # Not visible — pending listing
        self.prop_pending = Property.objects.create(
            tenant=self.tenant, title='Propiedad pendiente',
            listing_type='pending_listing', status='disponible',
            property_type='apartment', price=800_000,
        )
        # Not visible — inactive
        self.prop_inactive = Property.objects.create(
            tenant=self.tenant, title='Casa inactiva',
            listing_type='sale', status='disponible',
            property_type='house', price=2_000_000, is_active=False,
        )
        # Another visible property (apartment)
        self.prop_apt = Property.objects.create(
            tenant=self.tenant, title='Departamento visible',
            listing_type='sale', status='disponible',
            property_type='apartment', price=900_000,
        )

    def test_list_returns_only_sale_disponible_active(self):
        resp = self.client.get(LIST_URL)
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data['results']]
        self.assertIn(self.prop_visible.pk, ids)
        self.assertIn(self.prop_apt.pk, ids)
        self.assertNotIn(self.prop_pending.pk, ids)
        self.assertNotIn(self.prop_inactive.pk, ids)

    def test_filter_by_property_type(self):
        resp = self.client.get(LIST_URL, {'type': 'house'})
        self.assertEqual(resp.status_code, 200)
        types = [r['property_type'] for r in resp.data['results']]
        self.assertTrue(all(t == 'house' for t in types))
        self.assertNotIn('apartment', types)

    def test_filter_by_price_min(self):
        resp = self.client.get(LIST_URL, {'price_min': 1_000_000})
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data['results']]
        self.assertIn(self.prop_visible.pk, ids)
        self.assertNotIn(self.prop_apt.pk, ids)

    def test_filter_by_price_max(self):
        resp = self.client.get(LIST_URL, {'price_max': 1_000_000})
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data['results']]
        self.assertIn(self.prop_apt.pk, ids)
        self.assertNotIn(self.prop_visible.pk, ids)

    def test_list_response_has_pagination(self):
        resp = self.client.get(LIST_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('count', resp.data)
        self.assertIn('results', resp.data)


class PublicPropertyDetailTestCase(APITestCase):
    """Tests for GET /public/properties/{id} — views counter."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Test Tenant', slug='test-tenant2',
            email='t2@test.com',
        )
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Casa detalle',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
            is_active=True, views=0,
        )

    def test_detail_returns_property_data(self):
        resp = self.client.get(_detail(self.prop.pk))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['id'], self.prop.pk)
        self.assertEqual(resp.data['title'], 'Casa detalle')

    def test_detail_increments_views(self):
        initial_views = self.prop.views  # 0
        self.client.get(_detail(self.prop.pk))
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.views, initial_views + 1)

    def test_detail_increments_views_on_each_request(self):
        self.client.get(_detail(self.prop.pk))
        self.client.get(_detail(self.prop.pk))
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.views, 2)

    def test_detail_non_sale_property_returns_404(self):
        pending = Property.objects.create(
            tenant=self.tenant, title='Pendiente',
            listing_type='pending_listing', status='disponible',
            property_type='house', price=500_000,
        )
        resp = self.client.get(_detail(pending.pk))
        self.assertEqual(resp.status_code, 404)

    def test_detail_inactive_property_returns_404(self):
        inactive = Property.objects.create(
            tenant=self.tenant, title='Inactiva',
            listing_type='sale', status='disponible',
            property_type='house', price=500_000, is_active=False,
        )
        resp = self.client.get(_detail(inactive.pk))
        self.assertEqual(resp.status_code, 404)
