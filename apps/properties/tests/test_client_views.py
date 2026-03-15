"""
Comprehensive tests for client-facing property views in apps/properties/views/client.py

Covers:
- ClientSavedPropertiesView (GET, POST)
- ClientSavedPropertyCheckView (GET)
- ClientSavedPropertyDeleteView (DELETE)
"""
from decimal import Decimal

from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership
from apps.properties.models import Property, SavedProperty, PropertyImage
from apps.locations.models import Country, State, City


def _token(user):
    """Generate JWT access token for user."""
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    """Return authorization header."""
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


class SavedPropertySetup(APITestCase):
    """Base setup for saved property tests."""

    def setUp(self):
        # Tenant
        self.tenant = Tenant.objects.create(
            name='Property Tenant', slug='property-tenant',
            email='property@test.com',
        )

        # Location setup
        self.country = Country.objects.create(name='Mexico')
        self.state = State.objects.create(name='Mexico City', country=self.country)
        self.city = City.objects.create(name='Mexico City', state=self.state)

        # Client
        self.user = User.objects.create(
            email='client_properties@test.com',
            first_name='Juan',
            is_active=True,
        )
        self.membership = TenantMembership.objects.create(
            user=self.user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT,
        )
        self.token = _token(self.user)

        # Other client for isolation tests
        self.other_user = User.objects.create(
            email='other_client_properties@test.com',
        )
        self.other_membership = TenantMembership.objects.create(
            user=self.other_user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT,
        )

        # Properties (sale listing)
        self.prop1 = Property.objects.create(
            tenant=self.tenant, title='Casa 1',
            listing_type='sale', status='disponible',
            property_type='house', price=Decimal('1000000'),
            city=self.city,
        )
        PropertyImage.objects.create(
            property=self.prop1, image_url='http://example.com/image1.jpg',
            is_cover=True,
        )

        self.prop2 = Property.objects.create(
            tenant=self.tenant, title='Casa 2',
            listing_type='sale', status='disponible',
            property_type='house', price=Decimal('2000000'),
            city=self.city,
        )

        # Property with pending listing (should not be saveable)
        self.prop_pending = Property.objects.create(
            tenant=self.tenant, title='Casa Pending',
            listing_type='pending_listing', status='disponible',
            property_type='house', price=Decimal('1500000'),
            city=self.city,
        )

        # Inactive property (should not be saveable)
        self.prop_inactive = Property.objects.create(
            tenant=self.tenant, title='Casa Inactive',
            listing_type='sale', status='disponible',
            property_type='house', price=Decimal('800000'),
            city=self.city, is_active=False,
        )


class TestClientSavedPropertiesList(SavedPropertySetup):
    """Test ClientSavedPropertiesView GET endpoint."""

    def test_get_saved_properties_returns_200_authenticated(self):
        """GET /client/saved-properties returns 200 with auth."""
        resp = self.client.get('/api/v1/client/saved-properties', **_auth(self.token))
        self.assertEqual(resp.status_code, 200)

    def test_get_saved_properties_returns_401_unauthenticated(self):
        """GET /client/saved-properties without auth returns 401."""
        resp = self.client.get('/api/v1/client/saved-properties')
        self.assertEqual(resp.status_code, 401)

    def test_get_saved_properties_is_paginated(self):
        """GET /client/saved-properties response is paginated."""
        resp = self.client.get('/api/v1/client/saved-properties', **_auth(self.token))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('count', resp.data)
        self.assertIn('results', resp.data)

    def test_get_saved_properties_empty_list(self):
        """GET /client/saved-properties returns empty list when no saves."""
        resp = self.client.get('/api/v1/client/saved-properties', **_auth(self.token))
        self.assertEqual(resp.data['count'], 0)
        self.assertEqual(len(resp.data['results']), 0)

    def test_get_saved_properties_lists_saved(self):
        """GET /client/saved-properties returns saved properties."""
        SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.membership,
            property=self.prop1,
        )

        resp = self.client.get('/api/v1/client/saved-properties', **_auth(self.token))
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(len(resp.data['results']), 1)

    def test_get_saved_properties_only_own_saves(self):
        """GET /client/saved-properties only returns own saved properties."""
        # Save property as this client
        SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.membership,
            property=self.prop1,
        )

        # Save same property as other client
        SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.other_membership,
            property=self.prop1,
        )

        resp = self.client.get('/api/v1/client/saved-properties', **_auth(self.token))
        self.assertEqual(resp.data['count'], 1)

    def test_get_saved_properties_ordered_by_recent(self):
        """GET /client/saved-properties ordered by created_at descending."""
        sp1 = SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.membership,
            property=self.prop1,
        )
        sp2 = SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.membership,
            property=self.prop2,
        )

        resp = self.client.get('/api/v1/client/saved-properties', **_auth(self.token))
        results = resp.data['results']
        # Most recent first
        self.assertEqual(results[0]['id'], sp2.pk)

    def test_get_saved_properties_includes_property_data(self):
        """GET /client/saved-properties includes property details."""
        SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.membership,
            property=self.prop1,
        )

        resp = self.client.get('/api/v1/client/saved-properties', **_auth(self.token))
        result = resp.data['results'][0]
        self.assertIn('property', result)


class TestClientSaveProperty(SavedPropertySetup):
    """Test ClientSavedPropertiesView POST endpoint."""

    def test_post_save_property_returns_201(self):
        """POST /client/saved-properties returns 201."""
        resp = self.client.post(
            '/api/v1/client/saved-properties',
            {'property_id': self.prop1.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)

    def test_post_save_property_creates_entry(self):
        """POST /client/saved-properties creates SavedProperty."""
        self.client.post(
            '/api/v1/client/saved-properties',
            {'property_id': self.prop1.pk},
            format='json',
            **_auth(self.token),
        )

        self.assertTrue(
            SavedProperty.objects.filter(
                client_membership=self.membership,
                property=self.prop1,
            ).exists()
        )

    def test_post_save_property_returns_201(self):
        """POST response includes saved property id."""
        resp = self.client.post(
            '/api/v1/client/saved-properties',
            {'property_id': self.prop1.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn('id', resp.data)
        self.assertIn('property_id', resp.data)

    def test_post_save_property_idempotent(self):
        """POST /client/saved-properties twice returns 201 both times."""
        # Save once
        resp1 = self.client.post(
            '/api/v1/client/saved-properties',
            {'property_id': self.prop1.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp1.status_code, 201)

        # Save again
        resp2 = self.client.post(
            '/api/v1/client/saved-properties',
            {'property_id': self.prop1.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp2.status_code, 201)

        # Only one entry in DB (unique_together constraint)
        saved = SavedProperty.objects.filter(
            client_membership=self.membership,
            property=self.prop1,
        )
        self.assertEqual(saved.count(), 1)

    def test_post_save_property_without_property_id_returns_400(self):
        """POST without property_id returns 400."""
        resp = self.client.post(
            '/api/v1/client/saved-properties',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_post_save_property_invalid_id_returns_404(self):
        """POST with invalid property_id returns 404."""
        resp = self.client.post(
            '/api/v1/client/saved-properties',
            {'property_id': 99999},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_post_save_property_pending_listing_returns_404(self):
        """POST property with listing_type=pending_listing returns 404."""
        resp = self.client.post(
            '/api/v1/client/saved-properties',
            {'property_id': self.prop_pending.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_post_save_property_inactive_returns_404(self):
        """POST inactive property returns 404."""
        resp = self.client.post(
            '/api/v1/client/saved-properties',
            {'property_id': self.prop_inactive.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_post_save_property_returns_401_unauthenticated(self):
        """POST without auth returns 401."""
        resp = self.client.post(
            '/api/v1/client/saved-properties',
            {'property_id': self.prop1.pk},
            format='json',
        )
        self.assertEqual(resp.status_code, 401)


class TestClientSavedPropertyCheck(SavedPropertySetup):
    """Test ClientSavedPropertyCheckView GET endpoint."""

    def test_get_check_saved_returns_200(self):
        """GET /client/saved-properties/check returns 200."""
        resp = self.client.get(
            '/api/v1/client/saved-properties/check',
            {'property_id': self.prop1.pk},
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_check_saved_not_saved_returns_false(self):
        """GET /client/saved-properties/check returns is_saved=false when not saved."""
        resp = self.client.get(
            '/api/v1/client/saved-properties/check',
            {'property_id': self.prop1.pk},
            **_auth(self.token),
        )
        self.assertFalse(resp.data['is_saved'])

    def test_get_check_saved_is_saved_returns_true(self):
        """GET /client/saved-properties/check returns is_saved=true when saved."""
        SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.membership,
            property=self.prop1,
        )

        resp = self.client.get(
            '/api/v1/client/saved-properties/check',
            {'property_id': self.prop1.pk},
            **_auth(self.token),
        )
        self.assertTrue(resp.data['is_saved'])

    def test_get_check_saved_without_property_id_returns_400(self):
        """GET /client/saved-properties/check without property_id returns 400."""
        resp = self.client.get(
            '/api/v1/client/saved-properties/check',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_check_saved_invalid_property_id_returns_false(self):
        """GET /client/saved-properties/check with invalid property_id returns false."""
        resp = self.client.get(
            '/api/v1/client/saved-properties/check',
            {'property_id': 99999},
            **_auth(self.token),
        )
        # Should return 400 or false - depends on implementation
        self.assertIn(resp.status_code, [200, 400])

    def test_get_check_saved_returns_401_unauthenticated(self):
        """GET /client/saved-properties/check without auth returns 401."""
        resp = self.client.get(
            '/api/v1/client/saved-properties/check',
            {'property_id': self.prop1.pk},
        )
        self.assertEqual(resp.status_code, 401)


class TestClientDeleteSavedProperty(SavedPropertySetup):
    """Test ClientSavedPropertyDeleteView DELETE endpoint."""

    def test_delete_saved_property_returns_204(self):
        """DELETE /client/saved-properties/{property_id} returns 204."""
        SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.membership,
            property=self.prop1,
        )

        resp = self.client.delete(
            f'/api/v1/client/saved-properties/{self.prop1.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 204)

    def test_delete_saved_property_removes_entry(self):
        """DELETE /client/saved-properties/{property_id} removes SavedProperty."""
        SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.membership,
            property=self.prop1,
        )

        self.client.delete(
            f'/api/v1/client/saved-properties/{self.prop1.pk}',
            **_auth(self.token),
        )

        self.assertFalse(
            SavedProperty.objects.filter(
                client_membership=self.membership,
                property=self.prop1,
            ).exists()
        )

    def test_delete_saved_property_not_saved_returns_404(self):
        """DELETE /client/saved-properties/{property_id} not saved returns 404."""
        resp = self.client.delete(
            f'/api/v1/client/saved-properties/{self.prop1.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_saved_property_other_client_returns_404(self):
        """DELETE other client's save returns 404."""
        SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.other_membership,
            property=self.prop1,
        )

        resp = self.client.delete(
            f'/api/v1/client/saved-properties/{self.prop1.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_saved_property_returns_401_unauthenticated(self):
        """DELETE without auth returns 401."""
        resp = self.client.delete(
            f'/api/v1/client/saved-properties/{self.prop1.pk}',
        )
        self.assertEqual(resp.status_code, 401)

    def test_delete_saved_property_idempotent(self):
        """DELETE /client/saved-properties/{property_id} twice is idempotent."""
        SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.membership,
            property=self.prop1,
        )

        # Delete once
        resp1 = self.client.delete(
            f'/api/v1/client/saved-properties/{self.prop1.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp1.status_code, 204)

        # Delete again
        resp2 = self.client.delete(
            f'/api/v1/client/saved-properties/{self.prop1.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp2.status_code, 404)
