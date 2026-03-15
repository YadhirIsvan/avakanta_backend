"""
Comprehensive tests for apps/properties/views/admin.py

Test coverage for:
- AdminPropertyListCreateView (GET/POST)
- AdminPropertyDetailView (GET/PATCH/DELETE)
- AdminPropertyImageView (POST)
- AdminPropertyImageDeleteView (DELETE)
- AdminPropertyDocumentView (POST)
- AdminPropertyToggleFeaturedView (PATCH)
- AdminAssignmentView (GET/POST)
- AdminAssignmentDetailView (PATCH/DELETE)
"""
from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership, AgentProfile
from apps.properties.models import Property, PropertyImage, PropertyAssignment, PropertyDocument


def _token(user):
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


def _create_test_image():
    """Create a simple test image file."""
    # Create a minimal valid JPEG file (magic bytes: FF D8 FF)
    image_data = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    image_data += b'\xff\xd9'  # JPEG end marker
    return SimpleUploadedFile(
        'test.jpg',
        image_data,
        content_type='image/jpeg'
    )


def _create_test_pdf():
    """Create a simple test PDF file."""
    # Create a minimal valid PDF file (magic bytes: 25 50 44 46)
    pdf_data = b'%PDF-1.4\n%EOF'
    return SimpleUploadedFile(
        'test.pdf',
        pdf_data,
        content_type='application/pdf'
    )


class AdminPropertiesTestSetup(APITestCase):
    """Base setup: Tenant with admin, agents, and properties."""

    def setUp(self):
        # Create tenant
        self.tenant = Tenant.objects.create(
            name='Properties Test', slug='prop-test',
            email='prop@test.com',
        )

        # Create admin
        self.admin = User.objects.create(email='admin@prop.com')
        self.admin_m = TenantMembership.objects.create(
            user=self.admin, tenant=self.tenant,
            role=TenantMembership.Role.ADMIN,
        )
        self.token = _token(self.admin)

        # Create agents
        self.agent1 = User.objects.create(email='agent1@prop.com', first_name='Carlos')
        self.agent1_m = TenantMembership.objects.create(
            user=self.agent1, tenant=self.tenant,
            role=TenantMembership.Role.AGENT,
        )
        self.agent1_profile = AgentProfile.objects.create(membership=self.agent1_m)

        self.agent2 = User.objects.create(email='agent2@prop.com')
        self.agent2_m = TenantMembership.objects.create(
            user=self.agent2, tenant=self.tenant,
            role=TenantMembership.Role.AGENT,
        )
        self.agent2_profile = AgentProfile.objects.create(membership=self.agent2_m)

        # Create non-admin user for permission tests
        self.non_admin = User.objects.create(email='user@prop.com')
        self.non_admin_m = TenantMembership.objects.create(
            user=self.non_admin, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT,
        )
        self.non_admin_token = _token(self.non_admin)


class TestAdminPropertyListCreate(AdminPropertiesTestSetup):
    """Tests for AdminPropertyListCreateView."""

    def test_list_empty(self):
        """GET with no properties returns empty list."""
        resp = self.client.get(
            '/api/v1/admin/properties',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)

    def test_list_with_properties(self):
        """GET returns all properties."""
        Property.objects.create(
            tenant=self.tenant, title='House 1',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
        )
        Property.objects.create(
            tenant=self.tenant, title='Apartment 1',
            listing_type='sale', status='disponible',
            property_type='apartment', price=500_000,
        )

        resp = self.client.get(
            '/api/v1/admin/properties',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 2)

    def test_list_filter_by_status(self):
        """GET with status filter returns matching properties."""
        Property.objects.create(
            tenant=self.tenant, title='Property 1',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
        )
        Property.objects.create(
            tenant=self.tenant, title='Property 2',
            listing_type='sale', status='vendida',
            property_type='house', price=1_000_000,
        )

        resp = self.client.get(
            '/api/v1/admin/properties?status=disponible',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_list_filter_by_listing_type(self):
        """GET with listing_type filter returns matching properties."""
        Property.objects.create(
            tenant=self.tenant, title='Property 1',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
        )
        Property.objects.create(
            tenant=self.tenant, title='Property 2',
            listing_type='pending_listing', status='disponible',
            property_type='house', price=1_000_000,
        )

        resp = self.client.get(
            '/api/v1/admin/properties?listing_type=sale',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_list_filter_by_property_type(self):
        """GET with property_type filter returns matching properties."""
        Property.objects.create(
            tenant=self.tenant, title='House 1',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
        )
        Property.objects.create(
            tenant=self.tenant, title='Apartment 1',
            listing_type='sale', status='disponible',
            property_type='apartment', price=500_000,
        )

        resp = self.client.get(
            '/api/v1/admin/properties?property_type=house',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_list_search_by_title(self):
        """GET with search filter finds by title."""
        Property.objects.create(
            tenant=self.tenant, title='Beautiful House on Main St',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
        )

        resp = self.client.get(
            '/api/v1/admin/properties?search=Beautiful',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_list_search_by_street(self):
        """GET with search filter finds by address."""
        Property.objects.create(
            tenant=self.tenant, title='House',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
            address_street='Main Street',
        )

        resp = self.client.get(
            '/api/v1/admin/properties?search=Main',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_create_success(self):
        """POST creates property."""
        resp = self.client.post(
            '/api/v1/admin/properties',
            {
                'title': 'New House',
                'listing_type': 'sale',
                'status': 'disponible',
                'property_type': 'house',
                'price': '1000000.00',
                'bedrooms': 3,
                'bathrooms': 2,
                'construction_sqm': '150.50',
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Property.objects.filter(title='New House').exists())
        prop = Property.objects.get(title='New House')
        self.assertEqual(prop.bedrooms, 3)
        self.assertEqual(prop.bathrooms, 2)

    def test_create_with_minimal_data(self):
        """POST with minimal required fields creates property."""
        resp = self.client.post(
            '/api/v1/admin/properties',
            {
                'title': 'Minimal Property',
                'listing_type': 'sale',
                'status': 'disponible',
                'property_type': 'house',
                'price': '500000',
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)

    def test_create_missing_required_field(self):
        """POST without required field returns 400."""
        resp = self.client.post(
            '/api/v1/admin/properties',
            {
                'title': 'Incomplete Property',
                'listing_type': 'sale',
                # Missing status, property_type, price
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_permission_denied(self):
        """Non-admin gets 403."""
        resp = self.client.post(
            '/api/v1/admin/properties',
            {
                'title': 'House',
                'listing_type': 'sale',
                'status': 'disponible',
                'property_type': 'house',
                'price': '1000000',
            },
            format='json',
            **_auth(self.non_admin_token),
        )
        self.assertEqual(resp.status_code, 403)


class TestAdminPropertyDetail(AdminPropertiesTestSetup):
    """Tests for AdminPropertyDetailView."""

    def setUp(self):
        super().setUp()
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Test House',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
            bedrooms=3, bathrooms=2,
        )

    def test_get_detail(self):
        """GET returns property details."""
        resp = self.client.get(
            f'/api/v1/admin/properties/{self.prop.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['title'], 'Test House')
        self.assertEqual(resp.data['bedrooms'], 3)

    def test_get_not_found(self):
        """GET with invalid pk returns 404."""
        resp = self.client.get(
            '/api/v1/admin/properties/9999',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_patch_title(self):
        """PATCH updates title."""
        resp = self.client.patch(
            f'/api/v1/admin/properties/{self.prop.pk}',
            {'title': 'Updated Title'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.title, 'Updated Title')

    def test_patch_price(self):
        """PATCH updates price."""
        resp = self.client.patch(
            f'/api/v1/admin/properties/{self.prop.pk}',
            {'price': '1200000.00'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.price, Decimal('1200000.00'))

    def test_patch_bedrooms_bathrooms(self):
        """PATCH updates bedrooms and bathrooms."""
        resp = self.client.patch(
            f'/api/v1/admin/properties/{self.prop.pk}',
            {'bedrooms': 4, 'bathrooms': 3},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.bedrooms, 4)
        self.assertEqual(self.prop.bathrooms, 3)

    def test_patch_address(self):
        """PATCH updates address fields."""
        resp = self.client.patch(
            f'/api/v1/admin/properties/{self.prop.pk}',
            {
                'address_street': 'Main Street',
                'address_number': '123',
                'address_neighborhood': 'Downtown',
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.address_street, 'Main Street')

    def test_patch_not_found(self):
        """PATCH with invalid pk returns 404."""
        resp = self.client.patch(
            '/api/v1/admin/properties/9999',
            {'title': 'Updated'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_success(self):
        """DELETE marks property as inactive."""
        resp = self.client.delete(
            f'/api/v1/admin/properties/{self.prop.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 204)
        self.prop.refresh_from_db()
        self.assertFalse(self.prop.is_active)

    def test_delete_not_found(self):
        """DELETE with invalid pk returns 404."""
        resp = self.client.delete(
            '/api/v1/admin/properties/9999',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)


class TestAdminPropertyImage(AdminPropertiesTestSetup):
    """Tests for AdminPropertyImageView and AdminPropertyImageDeleteView."""

    def setUp(self):
        super().setUp()
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Test House',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
        )

    @override_settings(MEDIA_ROOT='/tmp/test_media')
    def test_upload_single_image(self):
        """POST uploads single image."""
        image = _create_test_image()
        resp = self.client.post(
            f'/api/v1/admin/properties/{self.prop.pk}/images',
            {'images[]': image},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data), 1)
        self.assertTrue(PropertyImage.objects.filter(property=self.prop).exists())

    @override_settings(MEDIA_ROOT='/tmp/test_media')
    def test_upload_multiple_images(self):
        """POST uploads multiple images."""
        image1 = _create_test_image()
        image2 = _create_test_image()
        resp = self.client.post(
            f'/api/v1/admin/properties/{self.prop.pk}/images',
            {'images[]': [image1, image2]},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(resp.data), 2)

    @override_settings(MEDIA_ROOT='/tmp/test_media')
    def test_upload_with_is_cover_flag(self):
        """POST with is_cover flag sets first image as cover."""
        image = _create_test_image()
        resp = self.client.post(
            f'/api/v1/admin/properties/{self.prop.pk}/images',
            {'images[]': image, 'is_cover': 'true'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        img = PropertyImage.objects.get(property=self.prop)
        self.assertTrue(img.is_cover)

    def test_upload_no_images(self):
        """POST without images returns 400."""
        resp = self.client.post(
            f'/api/v1/admin/properties/{self.prop.pk}/images',
            {},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_property_not_found(self):
        """POST to non-existent property returns 404."""
        image = _create_test_image()
        resp = self.client.post(
            '/api/v1/admin/properties/9999/images',
            {'images[]': image},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_image_success(self):
        """DELETE removes image."""
        image = PropertyImage.objects.create(
            property=self.prop,
            image_url='/media/test.jpg',
            sort_order=0,
        )

        resp = self.client.delete(
            f'/api/v1/admin/properties/{self.prop.pk}/images/{image.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(PropertyImage.objects.filter(pk=image.pk).exists())

    def test_delete_image_not_found(self):
        """DELETE with invalid image_id returns 404."""
        resp = self.client.delete(
            f'/api/v1/admin/properties/{self.prop.pk}/images/9999',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)


class TestAdminPropertyDocument(AdminPropertiesTestSetup):
    """Tests for AdminPropertyDocumentView."""

    def setUp(self):
        super().setUp()
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Test House',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
        )

    @override_settings(MEDIA_ROOT='/tmp/test_media')
    def test_upload_document_success(self):
        """POST uploads document."""
        pdf = _create_test_pdf()
        resp = self.client.post(
            f'/api/v1/admin/properties/{self.prop.pk}/documents',
            {'file': pdf, 'name': 'Escritura'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['name'], 'Escritura')
        self.assertTrue(PropertyDocument.objects.filter(property=self.prop).exists())

    def test_upload_without_file(self):
        """POST without file returns 400."""
        resp = self.client.post(
            f'/api/v1/admin/properties/{self.prop.pk}/documents',
            {'name': 'Escritura'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('archivo', resp.data['error'])

    def test_upload_without_name(self):
        """POST without name returns 400."""
        pdf = _create_test_pdf()
        resp = self.client.post(
            f'/api/v1/admin/properties/{self.prop.pk}/documents',
            {'file': pdf},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('nombre', resp.data['error'])

    def test_upload_property_not_found(self):
        """POST to non-existent property returns 404."""
        pdf = _create_test_pdf()
        resp = self.client.post(
            '/api/v1/admin/properties/9999/documents',
            {'file': pdf, 'name': 'Escritura'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)


class TestAdminPropertyToggleFeatured(AdminPropertiesTestSetup):
    """Tests for AdminPropertyToggleFeaturedView."""

    def setUp(self):
        super().setUp()
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Test House',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
            is_featured=False,
        )

    def test_toggle_to_featured(self):
        """PATCH toggles is_featured from False to True."""
        resp = self.client.patch(
            f'/api/v1/admin/properties/{self.prop.pk}/toggle-featured',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['is_featured'])
        self.prop.refresh_from_db()
        self.assertTrue(self.prop.is_featured)

    def test_toggle_to_not_featured(self):
        """PATCH toggles is_featured from True to False."""
        self.prop.is_featured = True
        self.prop.save()

        resp = self.client.patch(
            f'/api/v1/admin/properties/{self.prop.pk}/toggle-featured',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['is_featured'])

    def test_toggle_not_found(self):
        """PATCH with invalid pk returns 404."""
        resp = self.client.patch(
            '/api/v1/admin/properties/9999/toggle-featured',
            {},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)


class TestAdminAssignment(AdminPropertiesTestSetup):
    """Tests for AdminAssignmentView."""

    def setUp(self):
        super().setUp()
        self.prop_sale = Property.objects.create(
            tenant=self.tenant, title='Sale Property',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
        )
        self.prop_pending = Property.objects.create(
            tenant=self.tenant, title='Pending Property',
            listing_type='pending_listing', status='disponible',
            property_type='house', price=1_000_000,
        )

    def test_get_assignments_empty(self):
        """GET returns empty assignments."""
        resp = self.client.get(
            '/api/v1/admin/assignments',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('unassigned_properties', resp.data)
        self.assertIn('assignments', resp.data)

    def test_get_assignments_unassigned(self):
        """GET includes unassigned sale properties."""
        resp = self.client.get(
            '/api/v1/admin/assignments',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        # prop_sale should be in unassigned, prop_pending should not be in sale listings
        unassigned_ids = [p['id'] for p in resp.data['unassigned_properties']]
        self.assertIn(self.prop_sale.pk, unassigned_ids)

    def test_get_assignments_assigned(self):
        """GET includes assigned properties."""
        PropertyAssignment.objects.create(
            property=self.prop_sale,
            agent_membership=self.agent1_m,
            is_visible=True,
        )

        resp = self.client.get(
            '/api/v1/admin/assignments',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(resp.data['assignments']), 0)

    def test_create_assignment_success(self):
        """POST creates assignment."""
        resp = self.client.post(
            '/api/v1/admin/assignments',
            {
                'property_id': self.prop_sale.pk,
                'agent_membership_id': self.agent1_m.pk,
                'is_visible': True,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(PropertyAssignment.objects.filter(
            property=self.prop_sale, agent_membership=self.agent1_m
        ).exists())

    def test_create_assignment_property_not_found(self):
        """POST with invalid property returns 400."""
        resp = self.client.post(
            '/api/v1/admin/assignments',
            {
                'property_id': 9999,
                'agent_membership_id': self.agent1_m.pk,
                'is_visible': True,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_assignment_agent_not_found(self):
        """POST with invalid agent returns 400."""
        resp = self.client.post(
            '/api/v1/admin/assignments',
            {
                'property_id': self.prop_sale.pk,
                'agent_membership_id': 9999,
                'is_visible': True,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_duplicate_assignment(self):
        """POST duplicate assignment returns 400."""
        PropertyAssignment.objects.create(
            property=self.prop_sale,
            agent_membership=self.agent1_m,
            is_visible=True,
        )

        resp = self.client.post(
            '/api/v1/admin/assignments',
            {
                'property_id': self.prop_sale.pk,
                'agent_membership_id': self.agent1_m.pk,
                'is_visible': True,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('asignado', resp.data['error'])


class TestAdminAssignmentDetail(AdminPropertiesTestSetup):
    """Tests for AdminAssignmentDetailView."""

    def setUp(self):
        super().setUp()
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Test House',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
        )
        self.assignment = PropertyAssignment.objects.create(
            property=self.prop,
            agent_membership=self.agent1_m,
            is_visible=True,
        )

    def test_patch_is_visible_false(self):
        """PATCH updates is_visible to False."""
        resp = self.client.patch(
            f'/api/v1/admin/assignments/{self.assignment.pk}',
            {'is_visible': False},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assignment.refresh_from_db()
        self.assertFalse(self.assignment.is_visible)

    def test_patch_is_visible_true(self):
        """PATCH updates is_visible to True."""
        self.assignment.is_visible = False
        self.assignment.save()

        resp = self.client.patch(
            f'/api/v1/admin/assignments/{self.assignment.pk}',
            {'is_visible': True},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assignment.refresh_from_db()
        self.assertTrue(self.assignment.is_visible)

    def test_patch_not_found(self):
        """PATCH with invalid pk returns 404."""
        resp = self.client.patch(
            '/api/v1/admin/assignments/9999',
            {'is_visible': False},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_success(self):
        """DELETE removes assignment."""
        resp = self.client.delete(
            f'/api/v1/admin/assignments/{self.assignment.pk}',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(PropertyAssignment.objects.filter(pk=self.assignment.pk).exists())

    def test_delete_not_found(self):
        """DELETE with invalid pk returns 404."""
        resp = self.client.delete(
            '/api/v1/admin/assignments/9999',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)


class TestTenantIsolation(AdminPropertiesTestSetup):
    """Tests for multi-tenant isolation in property admin views."""

    def setUp(self):
        super().setUp()

        # Create second tenant with its own data
        self.tenant2 = Tenant.objects.create(
            name='Properties Test 2', slug='prop-test-2',
            email='prop2@test.com',
        )

        admin2 = User.objects.create(email='admin2@prop.com')
        self.admin2_m = TenantMembership.objects.create(
            user=admin2, tenant=self.tenant2,
            role=TenantMembership.Role.ADMIN,
        )
        self.token2 = _token(admin2)

        # Create properties in both tenants
        self.prop_t1 = Property.objects.create(
            tenant=self.tenant, title='Property T1',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
        )

        self.prop_t2 = Property.objects.create(
            tenant=self.tenant2, title='Property T2',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
        )

    def test_admin_t1_cannot_see_t2_properties(self):
        """Admin from tenant1 doesn't see tenant2 properties."""
        resp = self.client.get(
            '/api/v1/admin/properties',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        # Should only see tenant1 property
        prop_ids = [p['id'] for p in resp.data['results']]
        self.assertIn(self.prop_t1.pk, prop_ids)
        self.assertNotIn(self.prop_t2.pk, prop_ids)

    def test_admin_t2_cannot_see_t1_properties(self):
        """Admin from tenant2 doesn't see tenant1 properties."""
        resp = self.client.get(
            '/api/v1/admin/properties',
            **_auth(self.token2),
        )
        self.assertEqual(resp.status_code, 200)
        # Should only see tenant2 property
        prop_ids = [p['id'] for p in resp.data['results']]
        self.assertIn(self.prop_t2.pk, prop_ids)
        self.assertNotIn(self.prop_t1.pk, prop_ids)

    def test_admin_t1_cannot_modify_t2_property(self):
        """Admin from tenant1 can't modify tenant2 property."""
        resp = self.client.patch(
            f'/api/v1/admin/properties/{self.prop_t2.pk}',
            {'title': 'Hacked'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)
