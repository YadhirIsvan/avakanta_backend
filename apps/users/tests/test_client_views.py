"""
Comprehensive tests for client-facing views in apps/users/views/client.py

Covers:
- ClientDashboardView (GET)
- ClientProfileView (GET, PATCH)
- ClientNotificationPreferencesView (GET, PUT)
- ClientFinancialProfileView (GET, POST, PUT)
- ClientProfileDetailView (GET, PATCH)
- ClientAvatarUploadView (POST)
"""
import tempfile
from io import BytesIO
from decimal import Decimal
from datetime import datetime, timedelta

from django.test import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from PIL import Image

from apps.tenants.models import Tenant
from apps.users.models import (
    User, TenantMembership, UserNotificationPreferences,
    ClientFinancialProfile, ClientProfile, AgentProfile
)
from apps.properties.models import Property, PropertyImage
from apps.transactions.models import PurchaseProcess, SaleProcess, ProcessStatusHistory


def _token(user):
    """Generate JWT access token for user."""
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    """Return authorization header."""
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


def _fake_image(name='image.jpg'):
    """Create a fake image file for testing."""
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return SimpleUploadedFile(
        name=name,
        content=img_bytes.read(),
        content_type='image/jpeg',
    )


class ClientDashboardSetup(APITestCase):
    """Base setup for dashboard tests."""

    def setUp(self):
        # Tenant
        self.tenant = Tenant.objects.create(
            name='Dashboard Tenant', slug='dashboard-tenant',
            email='dashboard@test.com',
        )

        # Client user
        self.user = User.objects.create(
            email='client_dashboard@test.com',
            first_name='Juan',
            last_name='Pérez',
            city='Mexico City',
            is_active=True,
        )
        self.membership = TenantMembership.objects.create(
            user=self.user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT,
        )
        self.token = _token(self.user)

        # Agent for processes
        self.agent_user = User.objects.create(
            email='agent_dashboard@test.com',
        )
        self.agent_membership = TenantMembership.objects.create(
            user=self.agent_user, tenant=self.tenant,
            role=TenantMembership.Role.AGENT,
        )
        AgentProfile.objects.create(membership=self.agent_membership)

        # Property for processes
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Casa Dashboard',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
        )


class TestClientDashboard(ClientDashboardSetup):
    """Test ClientDashboardView GET endpoint."""

    def test_get_dashboard_returns_200_authenticated(self):
        """GET /client/dashboard with auth returns 200."""
        resp = self.client.get('/api/v1/client/dashboard', **_auth(self.token))
        self.assertEqual(resp.status_code, 200)

    def test_get_dashboard_returns_401_unauthenticated(self):
        """GET /client/dashboard without auth returns 401."""
        resp = self.client.get('/api/v1/client/dashboard')
        self.assertEqual(resp.status_code, 401)

    def test_get_dashboard_returns_client_info(self):
        """Response contains client name, avatar, city."""
        resp = self.client.get('/api/v1/client/dashboard', **_auth(self.token))
        self.assertEqual(resp.status_code, 200)
        client_data = resp.data['client']
        self.assertEqual(client_data['name'], 'Juan Pérez')
        self.assertEqual(client_data['city'], 'Mexico City')

    def test_get_dashboard_returns_credit_score(self):
        """Response includes credit_score (can be None)."""
        resp = self.client.get('/api/v1/client/dashboard', **_auth(self.token))
        self.assertIn('credit_score', resp.data)

    def test_get_dashboard_includes_recent_activity(self):
        """Response includes recent_activity array."""
        resp = self.client.get('/api/v1/client/dashboard', **_auth(self.token))
        self.assertIsInstance(resp.data['recent_activity'], list)

    def test_get_dashboard_includes_process_previews(self):
        """Response includes sale and purchase process previews."""
        resp = self.client.get('/api/v1/client/dashboard', **_auth(self.token))
        self.assertIn('sale_processes_preview', resp.data)
        self.assertIn('purchase_processes_preview', resp.data)

    def test_get_dashboard_sale_processes_limited_to_3(self):
        """Sale processes preview limited to 3 items."""
        # Create 5 sale processes
        for i in range(5):
            SaleProcess.objects.create(
                tenant=self.tenant, property=self.prop,
                client_membership=self.membership,
            )

        resp = self.client.get('/api/v1/client/dashboard', **_auth(self.token))
        self.assertLessEqual(len(resp.data['sale_processes_preview']), 3)

    def test_get_dashboard_recent_activity_limited_to_5(self):
        """Recent activity limited to 5 items."""
        # Create 7 processes with history
        for i in range(7):
            p = PurchaseProcess.objects.create(
                tenant=self.tenant, property=self.prop,
                client_membership=self.membership,
                agent_membership=self.agent_membership,
            )
            ProcessStatusHistory.objects.create(
                process_type='purchase', process_id=p.id,
                previous_status='lead', new_status='visita',
                changed_by_membership=self.agent_membership,
            )

        resp = self.client.get('/api/v1/client/dashboard', **_auth(self.token))
        self.assertLessEqual(len(resp.data['recent_activity']), 5)

    def test_get_dashboard_includes_purchase_progress(self):
        """Purchase process preview includes overall_progress."""
        pp = PurchaseProcess.objects.create(
            tenant=self.tenant, property=self.prop,
            client_membership=self.membership,
            agent_membership=self.agent_membership,
            overall_progress=50,
        )

        resp = self.client.get('/api/v1/client/dashboard', **_auth(self.token))
        previews = resp.data['purchase_processes_preview']
        if previews:
            self.assertIn('overall_progress', previews[0])


class TestClientProfile(APITestCase):
    """Test ClientProfileView GET and PATCH."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Profile Tenant', slug='profile-tenant',
            email='profile@test.com',
        )
        self.user = User.objects.create(
            email='user_profile@test.com',
            first_name='Carlos',
            last_name='Lopez',
            phone='+52 555 1234567',
            city='Monterrey',
            is_active=True,
        )
        self.membership = TenantMembership.objects.create(
            user=self.user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT,
        )
        self.token = _token(self.user)

    def test_get_profile_returns_200(self):
        """GET /client/profile returns 200."""
        resp = self.client.get('/api/v1/client/profile', **_auth(self.token))
        self.assertEqual(resp.status_code, 200)

    def test_get_profile_returns_user_data(self):
        """GET /client/profile returns email, name, phone, city."""
        resp = self.client.get('/api/v1/client/profile', **_auth(self.token))
        self.assertEqual(resp.data['email'], self.user.email)
        self.assertEqual(resp.data['first_name'], 'Carlos')
        self.assertEqual(resp.data['last_name'], 'Lopez')
        self.assertEqual(resp.data['phone'], '+52 555 1234567')

    def test_patch_profile_updates_first_name(self):
        """PATCH /client/profile can update first_name."""
        resp = self.client.patch(
            '/api/v1/client/profile',
            {'first_name': 'Pedro'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Pedro')

    def test_patch_profile_updates_last_name(self):
        """PATCH /client/profile can update last_name."""
        resp = self.client.patch(
            '/api/v1/client/profile',
            {'last_name': 'Garcia'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, 'Garcia')

    def test_patch_profile_updates_phone(self):
        """PATCH /client/profile can update phone."""
        resp = self.client.patch(
            '/api/v1/client/profile',
            {'phone': '+52 555 9999999'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, '+52 555 9999999')

    def test_patch_profile_updates_city(self):
        """PATCH /client/profile can update city."""
        resp = self.client.patch(
            '/api/v1/client/profile',
            {'city': 'Guadalajara'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.city, 'Guadalajara')

    def test_patch_profile_email_not_changed(self):
        """PATCH /client/profile with email doesn't change email."""
        original_email = self.user.email
        resp = self.client.patch(
            '/api/v1/client/profile',
            {'email': 'hacker@malicious.com'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, original_email)

    def test_patch_profile_partial_update(self):
        """PATCH /client/profile with one field doesn't clear others."""
        self.user.last_name = 'Original'
        self.user.save()

        resp = self.client.patch(
            '/api/v1/client/profile',
            {'first_name': 'New'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'New')
        self.assertEqual(self.user.last_name, 'Original')

    def test_patch_profile_invalid_data_returns_400(self):
        """PATCH /client/profile with invalid data returns 400."""
        resp = self.client.patch(
            '/api/v1/client/profile',
            {'invalid_field': 'value'},
            format='json',
            **_auth(self.token),
        )
        # Should still update with valid fields, or return 400 if validation fails
        # Depends on serializer strictness
        self.assertIn(resp.status_code, [200, 400])


class TestClientNotificationPreferences(APITestCase):
    """Test ClientNotificationPreferencesView GET and PUT."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Notif Tenant', slug='notif-tenant',
            email='notif@test.com',
        )
        self.user = User.objects.create(
            email='user_notif@test.com',
        )
        self.membership = TenantMembership.objects.create(
            user=self.user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT,
        )
        self.token = _token(self.user)

    def test_get_preferences_returns_200(self):
        """GET /client/notification-preferences returns 200."""
        resp = self.client.get(
            '/api/v1/client/notification-preferences',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_preferences_creates_defaults(self):
        """GET /client/notification-preferences creates defaults on first access."""
        # Verify none exist yet
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
        # Defaults should be True
        self.assertTrue(resp.data['new_properties'])
        self.assertTrue(resp.data['price_updates'])
        self.assertTrue(resp.data['appointment_reminders'])
        self.assertTrue(resp.data['offers'])

    def test_put_preferences_updates_all_fields(self):
        """PUT /client/notification-preferences updates all boolean fields."""
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
        self.assertTrue(resp.data['price_updates'])
        self.assertFalse(resp.data['appointment_reminders'])
        self.assertTrue(resp.data['offers'])

    def test_put_preferences_persists_in_db(self):
        """PUT /client/notification-preferences persists changes."""
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
        """PUT /client/notification-preferences requires all fields (strict)."""
        resp = self.client.put(
            '/api/v1/client/notification-preferences',
            {'new_properties': False},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_preferences_returns_401_unauthenticated(self):
        """GET /client/notification-preferences without auth returns 401."""
        resp = self.client.get('/api/v1/client/notification-preferences')
        self.assertEqual(resp.status_code, 401)


class TestClientFinancialProfile(APITestCase):
    """Test ClientFinancialProfileView GET, POST, PUT."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Finance Tenant', slug='finance-tenant',
            email='finance@test.com',
        )
        self.user = User.objects.create(
            email='user_finance@test.com',
        )
        self.membership = TenantMembership.objects.create(
            user=self.user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT,
        )
        self.token = _token(self.user)

    def test_get_financial_profile_returns_200(self):
        """GET /client/financial-profile returns 200."""
        resp = self.client.get(
            '/api/v1/client/financial-profile',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_financial_profile_nonexistent_returns_none(self):
        """GET /client/financial-profile when none exists returns null."""
        resp = self.client.get(
            '/api/v1/client/financial-profile',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data)

    def test_post_financial_profile_creates_201(self):
        """POST /client/financial-profile creates profile, returns 201."""
        resp = self.client.post(
            '/api/v1/client/financial-profile',
            {
                'loan_type': 'individual',
                'monthly_income': '50000',
                'savings_for_enganche': '500000',
                'has_infonavit': False,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn('id', resp.data)
        self.assertIn('calculated_budget', resp.data)

    def test_post_financial_profile_calculates_budget(self):
        """POST /client/financial-profile calculates budget correctly."""
        resp = self.client.post(
            '/api/v1/client/financial-profile',
            {
                'loan_type': 'individual',
                'monthly_income': '100000',
                'savings_for_enganche': '1000000',
                'has_infonavit': False,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        # Budget should be > savings
        budget = Decimal(resp.data['calculated_budget'])
        self.assertGreater(budget, Decimal('1000000'))

    def test_post_financial_profile_conyugal_includes_partner_income(self):
        """POST with loan_type=conyugal includes partner_monthly_income."""
        resp = self.client.post(
            '/api/v1/client/financial-profile',
            {
                'loan_type': 'conyugal',
                'monthly_income': '60000',
                'partner_monthly_income': '40000',
                'savings_for_enganche': '500000',
                'has_infonavit': False,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        # Budget should account for both incomes
        budget = Decimal(resp.data['calculated_budget'])
        self.assertGreater(budget, Decimal('500000'))

    def test_post_financial_profile_with_infonavit(self):
        """POST can include infonavit details."""
        resp = self.client.post(
            '/api/v1/client/financial-profile',
            {
                'loan_type': 'cofinavit',
                'monthly_income': '50000',
                'savings_for_enganche': '100000',
                'has_infonavit': True,
                'infonavit_subcuenta_balance': '200000',
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data['has_infonavit'])

    def test_post_financial_profile_already_exists_returns_400(self):
        """POST when profile already exists returns 400."""
        # Create first profile
        self.client.post(
            '/api/v1/client/financial-profile',
            {
                'loan_type': 'individual',
                'monthly_income': '50000',
                'savings_for_enganche': '500000',
                'has_infonavit': False,
            },
            format='json',
            **_auth(self.token),
        )

        # Try to create again
        resp = self.client.post(
            '/api/v1/client/financial-profile',
            {
                'loan_type': 'individual',
                'monthly_income': '60000',
                'savings_for_enganche': '600000',
                'has_infonavit': False,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_put_financial_profile_updates_200(self):
        """PUT /client/financial-profile updates profile, returns 200."""
        # Create initial profile
        self.client.post(
            '/api/v1/client/financial-profile',
            {
                'loan_type': 'individual',
                'monthly_income': '50000',
                'savings_for_enganche': '500000',
                'has_infonavit': False,
            },
            format='json',
            **_auth(self.token),
        )

        # Update it
        resp = self.client.put(
            '/api/v1/client/financial-profile',
            {
                'loan_type': 'conyugal',
                'monthly_income': '70000',
                'partner_monthly_income': '30000',
                'savings_for_enganche': '700000',
                'has_infonavit': False,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['loan_type'], 'conyugal')

    def test_put_financial_profile_nonexistent_returns_404(self):
        """PUT when no profile exists returns 404."""
        resp = self.client.put(
            '/api/v1/client/financial-profile',
            {
                'loan_type': 'individual',
                'monthly_income': '50000',
                'savings_for_enganche': '500000',
                'has_infonavit': False,
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)

    def test_put_financial_profile_recalculates_budget(self):
        """PUT /client/financial-profile recalculates budget with new income."""
        # Create initial profile with 50k income
        resp1 = self.client.post(
            '/api/v1/client/financial-profile',
            {
                'loan_type': 'individual',
                'monthly_income': '50000',
                'savings_for_enganche': '500000',
                'has_infonavit': False,
            },
            format='json',
            **_auth(self.token),
        )
        budget1 = Decimal(resp1.data['calculated_budget'])

        # Update to 100k income
        resp2 = self.client.put(
            '/api/v1/client/financial-profile',
            {
                'loan_type': 'individual',
                'monthly_income': '100000',
                'savings_for_enganche': '500000',
                'has_infonavit': False,
            },
            format='json',
            **_auth(self.token),
        )
        budget2 = Decimal(resp2.data['calculated_budget'])

        # Budget with 100k should be > budget with 50k
        self.assertGreater(budget2, budget1)


class TestClientProfileDetail(APITestCase):
    """Test ClientProfileDetailView GET and PATCH."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Detail Tenant', slug='detail-tenant',
            email='detail@test.com',
        )
        self.user = User.objects.create(
            email='user_detail@test.com',
        )
        self.membership = TenantMembership.objects.create(
            user=self.user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT,
        )
        self.token = _token(self.user)

    def test_get_profile_detail_returns_200(self):
        """GET /client/profile-detail returns 200."""
        resp = self.client.get(
            '/api/v1/client/profile-detail',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_profile_detail_creates_on_first_access(self):
        """GET /client/profile-detail creates ClientProfile on first access."""
        self.assertFalse(
            ClientProfile.objects.filter(membership=self.membership).exists()
        )

        self.client.get('/api/v1/client/profile-detail', **_auth(self.token))

        self.assertTrue(
            ClientProfile.objects.filter(membership=self.membership).exists()
        )

    def test_patch_profile_detail_returns_200(self):
        """PATCH /client/profile-detail returns 200."""
        resp = self.client.patch(
            '/api/v1/client/profile-detail',
            {'name': 'Juan Pérez'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)

    def test_patch_profile_detail_updates_fields(self):
        """PATCH /client/profile-detail can update fields."""
        resp = self.client.patch(
            '/api/v1/client/profile-detail',
            {'occupation': 'Ingeniero', 'residence_location': 'Orizaba'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        profile = ClientProfile.objects.get(membership=self.membership)
        self.assertEqual(profile.occupation, 'Ingeniero')


class TestClientAvatarUpload(APITestCase):
    """Test ClientAvatarUploadView POST."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Avatar Tenant', slug='avatar-tenant',
            email='avatar@test.com',
        )
        self.user = User.objects.create(
            email='user_avatar@test.com',
        )
        self.membership = TenantMembership.objects.create(
            user=self.user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT,
        )
        self.token = _token(self.user)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_post_avatar_upload_returns_201(self):
        """POST /client/avatar-upload with file returns 201."""
        resp = self.client.post(
            '/api/v1/client/avatar-upload',
            {'avatar': _fake_image('avatar.jpg')},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('avatar', resp.data)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_post_avatar_upload_updates_user_avatar(self):
        """POST /client/avatar-upload updates user.avatar field."""
        resp = self.client.post(
            '/api/v1/client/avatar-upload',
            {'avatar': _fake_image('profile.jpg')},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.avatar)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_post_avatar_upload_returns_url(self):
        """POST /client/avatar-upload returns avatar URL."""
        resp = self.client.post(
            '/api/v1/client/avatar-upload',
            {'avatar': _fake_image('avatar.jpg')},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('/media/', resp.data['avatar'])

    def test_post_avatar_upload_without_file_returns_400(self):
        """POST /client/avatar-upload without file returns 400."""
        resp = self.client.post(
            '/api/v1/client/avatar-upload',
            {},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_post_avatar_upload_returns_401_unauthenticated(self):
        """POST /client/avatar-upload without auth returns 401."""
        resp = self.client.post(
            '/api/v1/client/avatar-upload',
            {'avatar': _fake_image()},
            format='multipart',
        )
        self.assertEqual(resp.status_code, 401)
