from rest_framework.test import APITestCase

from apps.tenants.models import Tenant


SELLER_LEADS_URL = '/api/v1/public/seller-leads'


class SellerLeadCreateTestCase(APITestCase):
    """Tests for POST /public/seller-leads."""

    def setUp(self):
        # The view hardcodes slug='altas-montanas'
        self.tenant = Tenant.objects.create(
            name='Altas Montañas', slug='altas-montanas',
            email='info@altasmontanas.com', is_active=True,
        )
        self.valid_payload = {
            'full_name': 'María López',
            'email': 'maria@example.com',
            'phone': '+52 272 100 0000',
            'property_type': 'house',
            'location': 'Orizaba, Veracruz',
            'square_meters': '120.00',
            'bedrooms': 3,
            'bathrooms': 2,
            'expected_price': '1500000.00',
        }

    def test_create_seller_lead_returns_201(self):
        resp = self.client.post(SELLER_LEADS_URL, self.valid_payload, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('id', resp.data)
        self.assertEqual(resp.data['full_name'], 'María López')
        self.assertEqual(resp.data['status'], 'new')

    def test_create_seller_lead_minimal_fields_returns_201(self):
        """Only required fields: full_name, email, phone, property_type."""
        resp = self.client.post(SELLER_LEADS_URL, {
            'full_name': 'Carlos Ruiz',
            'email': 'carlos@example.com',
            'phone': '+52 272 100 0001',
            'property_type': 'apartment',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('id', resp.data)

    def test_create_seller_lead_missing_required_field_returns_400(self):
        payload = dict(self.valid_payload)
        del payload['email']
        resp = self.client.post(SELLER_LEADS_URL, payload, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_seller_lead_invalid_email_returns_400(self):
        payload = dict(self.valid_payload)
        payload['email'] = 'not-an-email'
        resp = self.client.post(SELLER_LEADS_URL, payload, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_seller_lead_response_has_message(self):
        resp = self.client.post(SELLER_LEADS_URL, self.valid_payload, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('message', resp.data)
