from datetime import timedelta

from django.utils import timezone
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, OTPCode
from apps.users.otp import create_otp, hash_otp, OTP_RATE_LIMIT


REGISTER_URL = '/api/v1/auth/register'
OTP_REQUEST_URL = '/api/v1/auth/email/otp'
OTP_VERIFY_URL = '/api/v1/auth/email/verify'
LOGOUT_URL = '/api/v1/auth/logout'
REFRESH_URL = '/api/v1/auth/refresh'


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class OTPAuthTestCase(APITestCase):
    """Tests for the full OTP authentication flow."""

    def setUp(self):
        # A tenant must exist so OTPVerifyView can assign a membership
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            email='test@tenant.com',
            is_active=True,
        )
        self.email = 'testuser@example.com'

    # ── OTP Request ───────────────────────────────────────────────────────────

    def test_otp_request_creates_user_and_returns_200(self):
        """Requesting an OTP creates the user if they don't exist."""
        resp = self.client.post(OTP_REQUEST_URL, {'email': self.email}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(User.objects.filter(email=self.email).exists())
        self.assertEqual(resp.data['email'], self.email)

    def test_otp_request_rate_limit_after_5_attempts(self):
        """6th OTP request within 1 hour returns 429."""
        # Create OTP_RATE_LIMIT records in the last hour (max allowed)
        for _ in range(OTP_RATE_LIMIT):
            OTPCode.objects.create(
                email=self.email,
                code_hash=hash_otp('000000'),
                expires_at=timezone.now() + timedelta(minutes=10),
            )
        # 6th request must be rate-limited
        resp = self.client.post(OTP_REQUEST_URL, {'email': self.email}, format='json')
        self.assertEqual(resp.status_code, 429)

    def test_rate_limit_resets_after_window(self):
        """OTPs created more than 1 hour ago no cuentan para el rate limit."""
        old_time = timezone.now() - timedelta(hours=2)
        for _ in range(OTP_RATE_LIMIT):
            otp = OTPCode.objects.create(
                email=self.email,
                code_hash=hash_otp('000000'),
                expires_at=timezone.now() + timedelta(minutes=10),
            )
            # Mover created_at fuera de la ventana de 1 hora
            OTPCode.objects.filter(pk=otp.pk).update(created_at=old_time)

        # Con los 5 OTPs fuera de la ventana, la siguiente solicitud debe pasar
        resp = self.client.post(OTP_REQUEST_URL, {'email': self.email}, format='json')
        self.assertEqual(resp.status_code, 200)

    # ── OTP Verify ────────────────────────────────────────────────────────────

    def test_otp_verify_correct_code_returns_jwt(self):
        """Verifying a valid OTP returns access and refresh tokens."""
        User.objects.get_or_create(email=self.email, defaults={'is_active': True})
        code = create_otp(self.email)

        resp = self.client.post(OTP_VERIFY_URL, {'email': self.email, 'token': code}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)
        self.assertEqual(resp.data['user']['email'], self.email)

    def test_otp_verify_wrong_code_returns_400(self):
        """Verifying with an incorrect OTP returns 400."""
        User.objects.get_or_create(email=self.email, defaults={'is_active': True})
        create_otp(self.email)  # Create a valid OTP in DB

        resp = self.client.post(OTP_VERIFY_URL, {'email': self.email, 'token': '000000'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_otp_verify_expired_code_returns_400(self):
        """Verifying with an expired OTP returns 400."""
        User.objects.get_or_create(email=self.email, defaults={'is_active': True})
        # Create an already-expired OTP
        OTPCode.objects.create(
            email=self.email,
            code_hash=hash_otp('123456'),
            expires_at=timezone.now() - timedelta(minutes=1),  # already expired
        )

        resp = self.client.post(OTP_VERIFY_URL, {'email': self.email, 'token': '123456'}, format='json')
        self.assertEqual(resp.status_code, 400)

    # ── Logout ────────────────────────────────────────────────────────────────

    def test_logout_blacklists_refresh_token(self):
        """After logout, the refresh token can no longer be used."""
        user, _ = User.objects.get_or_create(email=self.email, defaults={'is_active': True})
        refresh = RefreshToken.for_user(user)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        resp = self.client.post(LOGOUT_URL, {'refresh': str(refresh)}, format='json')
        self.assertEqual(resp.status_code, 200)

        # Now try to use the same refresh token — must fail
        resp2 = self.client.post(REFRESH_URL, {'refresh': str(refresh)}, format='json')
        self.assertEqual(resp2.status_code, 401)

    def test_logout_without_refresh_token_returns_400(self):
        """Logout without refresh token in body returns 400."""
        user, _ = User.objects.get_or_create(email=self.email, defaults={'is_active': True})
        refresh = RefreshToken.for_user(user)

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        resp = self.client.post(LOGOUT_URL, {}, format='json')
        self.assertEqual(resp.status_code, 400)

    # ── Register ──────────────────────────────────────────────────────────────

    def test_register_new_user_returns_201(self):
        """Registrar un usuario nuevo retorna 201 con message y email."""
        resp = self.client.post(REGISTER_URL, {
            'email': 'nuevo@test.com',
            'first_name': 'Ana',
            'last_name': 'García',
            'phone': '+52 272 100 0000',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('message', resp.data)
        self.assertEqual(resp.data['email'], 'nuevo@test.com')

    def test_register_creates_user_in_db(self):
        """El usuario queda creado en la base de datos."""
        self.client.post(REGISTER_URL, {
            'email': 'newuser@test.com',
            'first_name': 'Carlos',
            'last_name': 'López',
        }, format='json')
        self.assertTrue(User.objects.filter(email='newuser@test.com').exists())

    def test_register_saves_first_and_last_name(self):
        """first_name y last_name se persisten correctamente."""
        self.client.post(REGISTER_URL, {
            'email': 'named@test.com',
            'first_name': 'María',
            'last_name': 'Hernández',
        }, format='json')
        user = User.objects.get(email='named@test.com')
        self.assertEqual(user.first_name, 'María')
        self.assertEqual(user.last_name, 'Hernández')

    def test_register_creates_client_membership(self):
        """Se crea TenantMembership con role=client en el tenant default."""
        from apps.users.models import TenantMembership
        resp = self.client.post(REGISTER_URL, {
            'email': 'membership@test.com',
            'first_name': 'Pedro',
            'last_name': 'Ruiz',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        user = User.objects.get(email='membership@test.com')
        membership = TenantMembership.objects.filter(user=user).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.tenant, self.tenant)
        self.assertEqual(membership.role, TenantMembership.Role.CLIENT)

    def test_register_existing_user_returns_400(self):
        """Registrar un email ya existente retorna 400."""
        User.objects.create(email='existing@test.com', is_active=True)
        resp = self.client.post(REGISTER_URL, {
            'email': 'existing@test.com',
            'first_name': 'X',
            'last_name': 'Y',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('El usuario ya existe', resp.data['error'])

    def test_register_without_required_fields_returns_400(self):
        """Omitir first_name o last_name retorna 400."""
        resp = self.client.post(REGISTER_URL, {
            'email': 'incomplete@test.com',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_register_sends_otp_email(self):
        """Se envía un OTP al email tras el registro."""
        from django.core import mail
        resp = self.client.post(REGISTER_URL, {
            'email': 'otp_check@test.com',
            'first_name': 'Lucía',
            'last_name': 'Martínez',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('otp_check@test.com', mail.outbox[0].to)

    def test_register_phone_is_optional(self):
        """El campo phone no es requerido."""
        resp = self.client.post(REGISTER_URL, {
            'email': 'nophone@test.com',
            'first_name': 'Sin',
            'last_name': 'Teléfono',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
