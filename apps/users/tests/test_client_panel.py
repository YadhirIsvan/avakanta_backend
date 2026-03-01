"""
Tests del panel del cliente — perfil y preferencias (T-083).

- PATCH /client/profile con email → email no cambia
- PATCH /client/profile con nombre → nombre se actualiza
- GET /client/notification-preferences → defaults
- PUT /client/notification-preferences → actualiza preferencias
"""
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership, UserNotificationPreferences


def _token(user):
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


class ClientProfilePanelSetup(APITestCase):
    """Base: tenant y un cliente con datos de perfil."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Profile Tenant', slug='profile-tenant',
            email='profile@test.com', is_active=True,
        )
        self.user = User.objects.create(
            email='client_profile@test.com',
            first_name='Juan',
            last_name='Pérez',
            is_active=True,
        )
        self.membership = TenantMembership.objects.create(
            user=self.user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT, is_active=True,
        )
        self.token = _token(self.user)


class TestClientProfile(ClientProfilePanelSetup):
    """GET y PATCH /client/profile."""

    def test_get_profile_returns_200_with_email(self):
        resp = self.client.get('/api/v1/client/profile', **_auth(self.token))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['email'], self.user.email)

    def test_get_profile_returns_name(self):
        resp = self.client.get('/api/v1/client/profile', **_auth(self.token))
        self.assertEqual(resp.data['first_name'], 'Juan')
        self.assertEqual(resp.data['last_name'], 'Pérez')

    def test_patch_profile_with_email_does_not_change_email(self):
        """Email enviado en PATCH no se actualiza (campo ignorado)."""
        original_email = self.user.email
        resp = self.client.patch(
            '/api/v1/client/profile',
            {'email': 'nuevo@email.com', 'first_name': 'Carlos'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, original_email)

    def test_patch_profile_updates_first_name(self):
        resp = self.client.patch(
            '/api/v1/client/profile',
            {'first_name': 'Carlos'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Carlos')

    def test_patch_profile_updates_last_name(self):
        resp = self.client.patch(
            '/api/v1/client/profile',
            {'last_name': 'García'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, 'García')

    def test_patch_profile_updates_phone(self):
        resp = self.client.patch(
            '/api/v1/client/profile',
            {'phone': '+52 272 999 0000'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, '+52 272 999 0000')

    def test_patch_profile_response_contains_original_email(self):
        """La respuesta siempre refleja el email original."""
        resp = self.client.patch(
            '/api/v1/client/profile',
            {'email': 'hacker@bad.com'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.data['email'], self.user.email)

    def test_patch_profile_partial_update_does_not_clear_other_fields(self):
        """Actualizar solo first_name no borra last_name."""
        resp = self.client.patch(
            '/api/v1/client/profile',
            {'first_name': 'Pedro'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, 'Pérez')   # unchanged


class TestClientNotificationPreferences(ClientProfilePanelSetup):
    """GET y PUT /client/notification-preferences."""

    def test_get_preferences_returns_200(self):
        resp = self.client.get(
            '/api/v1/client/notification-preferences',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_preferences_creates_defaults_on_first_access(self):
        """Si no existen preferencias, se crean con defaults=True."""
        self.assertFalse(
            UserNotificationPreferences.objects.filter(
                membership=self.membership
            ).exists()
        )
        resp = self.client.get(
            '/api/v1/client/notification-preferences',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['new_properties'])
        self.assertTrue(resp.data['price_updates'])
        self.assertTrue(resp.data['appointment_reminders'])
        self.assertTrue(resp.data['offers'])

    def test_put_preferences_updates_values(self):
        resp = self.client.put(
            '/api/v1/client/notification-preferences',
            {
                'new_properties': False,
                'price_updates': True,
                'appointment_reminders': False,
                'offers': True,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['new_properties'])
        self.assertFalse(resp.data['appointment_reminders'])

    def test_put_preferences_persists_in_db(self):
        self.client.put(
            '/api/v1/client/notification-preferences',
            {
                'new_properties': False,
                'price_updates': False,
                'appointment_reminders': True,
                'offers': False,
            },
            format='json',
            **_auth(self.token),
        )
        prefs = UserNotificationPreferences.objects.get(membership=self.membership)
        self.assertFalse(prefs.new_properties)
        self.assertFalse(prefs.price_updates)
        self.assertTrue(prefs.appointment_reminders)
        self.assertFalse(prefs.offers)

    def test_put_preferences_requires_all_fields(self):
        """PUT (no PATCH) requiere todos los campos."""
        resp = self.client.put(
            '/api/v1/client/notification-preferences',
            {'new_properties': False},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)
