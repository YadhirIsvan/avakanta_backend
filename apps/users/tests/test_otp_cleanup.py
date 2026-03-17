"""
Tests para la limpieza de OTPs expirados.

Cubre:
- cleanup_expired_otps() — elimina solo expirados, respeta vigentes
- Integración con create_otp() — el cleanup corre antes de crear
- Management command cleanup_expired_otps
"""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.users.models import OTPCode, User
from apps.users.otp import cleanup_expired_otps, create_otp, hash_otp


class CleanupExpiredOTPsTest(TestCase):

    def setUp(self):
        self.user = User.objects.create(email="otp_cleanup@test.com", is_active=True)

    def _make_otp(self, email: str, expired: bool) -> OTPCode:
        delta = timedelta(minutes=-1) if expired else timedelta(minutes=9)
        return OTPCode.objects.create(
            email=email,
            code_hash=hash_otp("000000"),
            expires_at=timezone.now() + delta,
        )

    # ── cleanup_expired_otps() ────────────────────────────────────────────────

    def test_cleanup_removes_only_expired(self):
        """Solo elimina OTPs vencidos, respeta los vigentes."""
        expired = self._make_otp("a@test.com", expired=True)
        valid = self._make_otp("b@test.com", expired=False)

        deleted = cleanup_expired_otps()

        self.assertEqual(deleted, 1)
        self.assertFalse(OTPCode.objects.filter(pk=expired.pk).exists())
        self.assertTrue(OTPCode.objects.filter(pk=valid.pk).exists())

    def test_cleanup_returns_zero_when_nothing_expired(self):
        """Retorna 0 cuando no hay OTPs expirados."""
        self._make_otp("c@test.com", expired=False)
        deleted = cleanup_expired_otps()
        self.assertEqual(deleted, 0)

    def test_cleanup_returns_zero_on_empty_table(self):
        """Retorna 0 cuando la tabla está vacía."""
        deleted = cleanup_expired_otps()
        self.assertEqual(deleted, 0)

    def test_cleanup_removes_multiple_expired(self):
        """Elimina múltiples OTPs expirados en una sola llamada."""
        for i in range(5):
            self._make_otp(f"user{i}@test.com", expired=True)

        deleted = cleanup_expired_otps()

        self.assertEqual(deleted, 5)
        self.assertEqual(OTPCode.objects.count(), 0)

    def test_cleanup_removes_expired_at_exact_boundary(self):
        """Un OTP con expires_at exactamente en el pasado también se elimina."""
        otp = OTPCode.objects.create(
            email="boundary@test.com",
            code_hash=hash_otp("111111"),
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        deleted = cleanup_expired_otps()
        self.assertEqual(deleted, 1)
        self.assertFalse(OTPCode.objects.filter(pk=otp.pk).exists())

    def test_cleanup_leaves_future_otps_intact(self):
        """OTPs con expires_at en el futuro no se tocan."""
        valid = self._make_otp("future@test.com", expired=False)
        deleted = cleanup_expired_otps()
        self.assertEqual(deleted, 0)
        self.assertTrue(OTPCode.objects.filter(pk=valid.pk).exists())

    # ── Integración con create_otp() ──────────────────────────────────────────

    def test_create_otp_triggers_cleanup(self):
        """create_otp limpia expirados antes de crear el nuevo."""
        for i in range(3):
            self._make_otp(f"old{i}@test.com", expired=True)

        create_otp("otp_cleanup@test.com")

        # Los 3 expirados se eliminaron, solo queda el recién creado
        self.assertEqual(OTPCode.objects.count(), 1)
        self.assertTrue(
            OTPCode.objects.filter(email="otp_cleanup@test.com").exists()
        )

    def test_create_otp_does_not_delete_valid_otps(self):
        """create_otp no elimina OTPs vigentes de otros emails."""
        valid = self._make_otp("another@test.com", expired=False)

        create_otp("otp_cleanup@test.com")

        self.assertTrue(OTPCode.objects.filter(pk=valid.pk).exists())

    # ── Management command ────────────────────────────────────────────────────

    def test_management_command_reports_count(self):
        """El management command reporta cuántos OTPs se eliminaron."""
        self._make_otp("cmd1@test.com", expired=True)
        self._make_otp("cmd2@test.com", expired=True)

        out = StringIO()
        call_command("cleanup_expired_otps", stdout=out)

        output = out.getvalue()
        self.assertIn("2", output)

    def test_management_command_zero_when_nothing_to_clean(self):
        """El management command reporta 0 cuando no hay expirados."""
        out = StringIO()
        call_command("cleanup_expired_otps", stdout=out)
        self.assertIn("0", out.getvalue())
