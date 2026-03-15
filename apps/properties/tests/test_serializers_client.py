"""
Comprehensive tests for properties/serializers/client.py

Tests cover:
- ClientSavedPropertySerializer serialization and deserialization
- _address() helper function with various address combinations
- _cover_image() helper function with relative/absolute URLs
- Nested property data serialization
- Edge cases: null/empty fields, missing relationships
- Field types, required vs optional
"""
from decimal import Decimal
from unittest.mock import Mock

from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase, RequestFactory
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership
from apps.properties.models import Property, SavedProperty, PropertyImage
from apps.locations.models import Country, State, City, Amenity
from apps.properties.serializers.client import ClientSavedPropertySerializer, _address, _cover_image


def _token(user):
    """Generate JWT access token for user."""
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    """Return authorization header."""
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


class AddressHelperFunctionTests(TestCase):
    """Test the _address() helper function with various combinations."""

    def setUp(self):
        self.country = Country.objects.create(name='Mexico')
        self.state = State.objects.create(name='Mexico City', country=self.country)
        self.city = City.objects.create(name='Mexico City', state=self.state)
        self.state_no_code = State.objects.create(name='Jalisco', country=self.country, code=None)
        self.city_no_state = City.objects.create(name='Guadalajara', state=self.state_no_code)

    def test_address_with_all_fields(self):
        """Test address formatting with street, number, neighborhood, city, and state."""
        prop = Mock(
            address_street='Reforma',
            address_number='505',
            address_neighborhood='Cuauhtémoc',
            city=self.city,
        )
        result = _address(prop)
        self.assertEqual(result, 'Reforma 505, Col. Cuauhtémoc, Mexico City, Mexico City')

    def test_address_with_street_and_number_only(self):
        """Test address with just street and number."""
        prop = Mock(
            address_street='Reforma',
            address_number='505',
            address_neighborhood=None,
            city_id=None,
        )
        result = _address(prop)
        self.assertEqual(result, 'Reforma 505')

    def test_address_with_street_only(self):
        """Test address with just street (no number)."""
        prop = Mock(
            address_street='Reforma',
            address_number=None,
            address_neighborhood=None,
            city_id=None,
        )
        result = _address(prop)
        self.assertEqual(result, 'Reforma')

    def test_address_with_all_none(self):
        """Test address with all null values."""
        prop = Mock(
            address_street=None,
            address_number=None,
            address_neighborhood=None,
            city_id=None,
        )
        result = _address(prop)
        self.assertEqual(result, '')

    def test_address_with_neighborhood_and_city(self):
        """Test address with neighborhood and city but no street."""
        prop = Mock(
            address_street=None,
            address_number=None,
            address_neighborhood='Cuauhtémoc',
            city=self.city,
        )
        result = _address(prop)
        self.assertEqual(result, 'Col. Cuauhtémoc, Mexico City, Mexico City')

    def test_address_with_state_code_none(self):
        """Test address when state.code is None, falls back to state.name."""
        prop = Mock(
            address_street='Avenida Principal',
            address_number='123',
            address_neighborhood=None,
            city=self.city_no_state,
        )
        result = _address(prop)
        self.assertEqual(result, 'Avenida Principal 123, Guadalajara, Jalisco')

    def test_address_with_empty_strings(self):
        """Test address with empty strings instead of None."""
        prop = Mock(
            address_street='',
            address_number='',
            address_neighborhood='',
            city_id=None,
        )
        result = _address(prop)
        # Empty strings are falsy, so they should be treated like None
        self.assertEqual(result, '')


class CoverImageHelperFunctionTests(TestCase):
    """Test the _cover_image() helper function with various URL scenarios."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Image Tenant', slug='image-tenant',
            email='image@test.com',
        )
        self.country = Country.objects.create(name='Mexico')
        self.state = State.objects.create(name='Mexico City', country=self.country)
        self.city = City.objects.create(name='Mexico City', state=self.state)

        self.prop_with_cover = Property.objects.create(
            tenant=self.tenant, title='Property with Cover',
            listing_type='sale', status='disponible',
            property_type='house', price=Decimal('1000000'),
            city=self.city,
        )

        self.prop_no_images = Property.objects.create(
            tenant=self.tenant, title='Property No Images',
            listing_type='sale', status='disponible',
            property_type='house', price=Decimal('1000000'),
            city=self.city,
        )

        self.factory = RequestFactory()

    def test_cover_image_with_absolute_url(self):
        """Test that absolute URLs are returned as-is."""
        image = PropertyImage.objects.create(
            property=self.prop_with_cover,
            image_url='https://example.com/image.jpg',
            is_cover=True,
        )
        result = _cover_image(self.prop_with_cover)
        self.assertEqual(result, 'https://example.com/image.jpg')

    def test_cover_image_with_relative_url_and_request(self):
        """Test that relative URLs are converted to absolute with request context."""
        PropertyImage.objects.create(
            property=self.prop_with_cover,
            image_url='/media/properties/123/image.jpg',
            is_cover=True,
        )
        request = self.factory.get('/')
        result = _cover_image(self.prop_with_cover, request)
        self.assertTrue(result.startswith('http'))
        self.assertIn('/media/properties/123/image.jpg', result)

    def test_cover_image_with_relative_url_no_request(self):
        """Test that relative URLs use BACKEND_URL fallback without request."""
        PropertyImage.objects.create(
            property=self.prop_with_cover,
            image_url='/media/properties/123/image.jpg',
            is_cover=True,
        )
        result = _cover_image(self.prop_with_cover, request=None)
        # Should use the fallback BACKEND_URL
        self.assertTrue(result.startswith('http'))
        self.assertIn('/media/properties/123/image.jpg', result)

    def test_cover_image_marked_as_cover(self):
        """Test that is_cover=True image is selected first."""
        # Create non-cover image
        PropertyImage.objects.create(
            property=self.prop_with_cover,
            image_url='https://example.com/first.jpg',
            is_cover=False, sort_order=1,
        )
        # Create cover image
        PropertyImage.objects.create(
            property=self.prop_with_cover,
            image_url='https://example.com/cover.jpg',
            is_cover=True,
        )
        result = _cover_image(self.prop_with_cover)
        self.assertEqual(result, 'https://example.com/cover.jpg')

    def test_cover_image_no_cover_uses_sort_order(self):
        """Test that first non-cover image by sort_order is used if no cover."""
        PropertyImage.objects.create(
            property=self.prop_with_cover,
            image_url='https://example.com/second.jpg',
            is_cover=False, sort_order=2,
        )
        PropertyImage.objects.create(
            property=self.prop_with_cover,
            image_url='https://example.com/first.jpg',
            is_cover=False, sort_order=1,
        )
        result = _cover_image(self.prop_with_cover)
        self.assertEqual(result, 'https://example.com/first.jpg')

    def test_cover_image_no_images_returns_none(self):
        """Test that None is returned when property has no images."""
        result = _cover_image(self.prop_no_images)
        self.assertIsNone(result)

    def test_cover_image_empty_image_url_returns_none(self):
        """Test that None is returned when image_url is empty."""
        PropertyImage.objects.create(
            property=self.prop_with_cover,
            image_url='', is_cover=True,
        )
        result = _cover_image(self.prop_with_cover)
        self.assertIsNone(result)


class ClientSavedPropertySerializerTests(APITestCase):
    """Test ClientSavedPropertySerializer serialization and deserialization."""

    def setUp(self):
        # Tenant
        self.tenant = Tenant.objects.create(
            name='Serializer Test Tenant', slug='ser-test-tenant',
            email='serializer@test.com',
        )

        # Location
        self.country = Country.objects.create(name='Mexico')
        self.state = State.objects.create(name='Mexico City', country=self.country)
        self.city = City.objects.create(name='Mexico City', state=self.state)

        # Client
        self.user = User.objects.create(
            email='client_ser@test.com',
        )
        self.membership = TenantMembership.objects.create(
            user=self.user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT,
        )
        self.token = _token(self.user)

        # Property with full details
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Casa Bonita',
            listing_type='sale', status='disponible',
            property_type='house', price=Decimal('1500000.00'),
            bedrooms=3, bathrooms=2,
            construction_sqm=Decimal('150.50'),
            address_street='Calle Principal',
            address_number='123',
            address_neighborhood='Polanco',
            city=self.city, is_verified=True,
            is_active=True,
        )

        # Cover image
        PropertyImage.objects.create(
            property=self.prop,
            image_url='https://example.com/cover.jpg',
            is_cover=True,
        )

        # SavedProperty
        self.saved = SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.membership,
            property=self.prop,
        )

        self.factory = RequestFactory()

    def test_serializer_includes_required_fields(self):
        """Test that serializer includes id, property, and saved_at fields."""
        serializer = ClientSavedPropertySerializer(
            self.saved, context={'request': self.factory.get('/')}
        )
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('property', data)
        self.assertIn('saved_at', data)

    def test_serializer_saved_at_is_readonly(self):
        """Test that saved_at is read-only and maps from created_at."""
        serializer = ClientSavedPropertySerializer(
            self.saved, context={'request': self.factory.get('/')}
        )
        # saved_at should match created_at
        self.assertEqual(serializer.data['saved_at'], self.saved.created_at.isoformat())

    def test_serializer_property_field_structure(self):
        """Test that property field contains all expected subfields."""
        serializer = ClientSavedPropertySerializer(
            self.saved, context={'request': self.factory.get('/')}
        )
        prop_data = serializer.data['property']

        expected_keys = ['id', 'title', 'address', 'price', 'property_type',
                        'bedrooms', 'bathrooms', 'construction_sqm', 'image', 'is_verified']
        for key in expected_keys:
            self.assertIn(key, prop_data)

    def test_serializer_property_id(self):
        """Test that property.id matches the actual property."""
        serializer = ClientSavedPropertySerializer(
            self.saved, context={'request': self.factory.get('/')}
        )
        self.assertEqual(serializer.data['property']['id'], self.prop.id)

    def test_serializer_property_title(self):
        """Test that property.title is serialized correctly."""
        serializer = ClientSavedPropertySerializer(
            self.saved, context={'request': self.factory.get('/')}
        )
        self.assertEqual(serializer.data['property']['title'], 'Casa Bonita')

    def test_serializer_property_address_formatted(self):
        """Test that property.address is formatted correctly."""
        serializer = ClientSavedPropertySerializer(
            self.saved, context={'request': self.factory.get('/')}
        )
        expected_address = 'Calle Principal 123, Col. Polanco, Mexico City, Mexico City'
        self.assertEqual(serializer.data['property']['address'], expected_address)

    def test_serializer_property_price_as_string(self):
        """Test that price is serialized as string."""
        serializer = ClientSavedPropertySerializer(
            self.saved, context={'request': self.factory.get('/')}
        )
        self.assertEqual(serializer.data['property']['price'], '1500000.00')
        self.assertIsInstance(serializer.data['property']['price'], str)

    def test_serializer_property_type(self):
        """Test that property_type is serialized correctly."""
        serializer = ClientSavedPropertySerializer(
            self.saved, context={'request': self.factory.get('/')}
        )
        self.assertEqual(serializer.data['property']['property_type'], 'house')

    def test_serializer_bedrooms_bathrooms(self):
        """Test that bedrooms and bathrooms are serialized correctly."""
        serializer = ClientSavedPropertySerializer(
            self.saved, context={'request': self.factory.get('/')}
        )
        self.assertEqual(serializer.data['property']['bedrooms'], 3)
        self.assertEqual(serializer.data['property']['bathrooms'], 2)

    def test_serializer_construction_sqm_as_string(self):
        """Test that construction_sqm is serialized as string."""
        serializer = ClientSavedPropertySerializer(
            self.saved, context={'request': self.factory.get('/')}
        )
        self.assertEqual(serializer.data['property']['construction_sqm'], '150.50')

    def test_serializer_construction_sqm_null(self):
        """Test that null construction_sqm serializes as None."""
        self.prop.construction_sqm = None
        self.prop.save()

        serializer = ClientSavedPropertySerializer(
            self.saved, context={'request': self.factory.get('/')}
        )
        self.assertIsNone(serializer.data['property']['construction_sqm'])

    def test_serializer_image_url(self):
        """Test that image URL is included."""
        serializer = ClientSavedPropertySerializer(
            self.saved, context={'request': self.factory.get('/')}
        )
        self.assertEqual(serializer.data['property']['image'], 'https://example.com/cover.jpg')

    def test_serializer_is_verified(self):
        """Test that is_verified is serialized correctly."""
        serializer = ClientSavedPropertySerializer(
            self.saved, context={'request': self.factory.get('/')}
        )
        self.assertTrue(serializer.data['property']['is_verified'])

    def test_serializer_is_verified_false(self):
        """Test that is_verified=False is serialized correctly."""
        self.prop.is_verified = False
        self.prop.save()

        serializer = ClientSavedPropertySerializer(
            self.saved, context={'request': self.factory.get('/')}
        )
        self.assertFalse(serializer.data['property']['is_verified'])

    def test_serializer_without_request_context(self):
        """Test that serializer works without request context."""
        serializer = ClientSavedPropertySerializer(self.saved)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('property', data)
        # Image should still be populated, just without absolute URL conversion
        self.assertIsNotNone(data['property']['image'])

    def test_serializer_property_no_address_fields(self):
        """Test property serialization when address fields are empty."""
        prop = Property.objects.create(
            tenant=self.tenant, title='Casa Sin Direccion',
            listing_type='sale', status='disponible',
            property_type='house', price=Decimal('1000000'),
            address_street=None, address_number=None,
            address_neighborhood=None, city=None,
            is_active=True,
        )
        saved = SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.membership,
            property=prop,
        )

        serializer = ClientSavedPropertySerializer(
            saved, context={'request': self.factory.get('/')}
        )
        self.assertEqual(serializer.data['property']['address'], '')

    def test_serializer_property_no_images(self):
        """Test property serialization when no images exist."""
        prop = Property.objects.create(
            tenant=self.tenant, title='Casa Sin Imagenes',
            listing_type='sale', status='disponible',
            property_type='house', price=Decimal('1000000'),
            city=self.city,
        )
        saved = SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.membership,
            property=prop,
        )

        serializer = ClientSavedPropertySerializer(
            saved, context={'request': self.factory.get('/')}
        )
        self.assertIsNone(serializer.data['property']['image'])

    def test_serializer_multiple_saved_properties(self):
        """Test that multiple SavedProperty objects serialize independently."""
        prop2 = Property.objects.create(
            tenant=self.tenant, title='Casa Segunda',
            listing_type='sale', status='disponible',
            property_type='apartment', price=Decimal('2000000'),
            city=self.city,
        )
        PropertyImage.objects.create(
            property=prop2,
            image_url='https://example.com/prop2.jpg',
            is_cover=True,
        )
        saved2 = SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.membership,
            property=prop2,
        )

        serializer1 = ClientSavedPropertySerializer(self.saved)
        serializer2 = ClientSavedPropertySerializer(saved2)

        self.assertEqual(serializer1.data['property']['title'], 'Casa Bonita')
        self.assertEqual(serializer2.data['property']['title'], 'Casa Segunda')
        self.assertNotEqual(serializer1.data['id'], serializer2.data['id'])

    def test_serializer_is_readonly(self):
        """Test that serializer is read-only (no deserialization expected)."""
        # All fields should be read-only
        for field_name, field in ClientSavedPropertySerializer().fields.items():
            self.assertTrue(field.read_only, f'{field_name} should be read-only')

    def test_serializer_with_zero_bedrooms_bathrooms(self):
        """Test serialization when bedrooms/bathrooms are 0."""
        prop = Property.objects.create(
            tenant=self.tenant, title='Estudio',
            listing_type='sale', status='disponible',
            property_type='house', price=Decimal('500000'),
            bedrooms=0, bathrooms=0,
            city=self.city,
        )
        saved = SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.membership,
            property=prop,
        )

        serializer = ClientSavedPropertySerializer(saved)
        self.assertEqual(serializer.data['property']['bedrooms'], 0)
        self.assertEqual(serializer.data['property']['bathrooms'], 0)

    def test_serializer_with_high_price_values(self):
        """Test serialization with very large price values."""
        prop = Property.objects.create(
            tenant=self.tenant, title='Casa Cara',
            listing_type='sale', status='disponible',
            property_type='house', price=Decimal('999999999999.99'),
            city=self.city,
        )
        saved = SavedProperty.objects.create(
            tenant=self.tenant,
            client_membership=self.membership,
            property=prop,
        )

        serializer = ClientSavedPropertySerializer(saved)
        self.assertEqual(serializer.data['property']['price'], '999999999999.99')
