from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    class AuthProvider(models.TextChoices):
        EMAIL = 'email', 'Email'
        GOOGLE = 'google', 'Google'
        APPLE = 'apple', 'Apple'

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    avatar = models.CharField(max_length=500, blank=True, null=True)
    city = models.CharField(max_length=150, blank=True, null=True)
    auth_provider = models.CharField(
        max_length=10,
        choices=AuthProvider.choices,
        default=AuthProvider.EMAIL
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    # last_login heredado de AbstractBaseUser

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()


class TenantMembership(models.Model):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        AGENT = 'agent', 'Agent'
        CLIENT = 'client', 'Client'

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_memberships'
        unique_together = [('user', 'tenant')]
        verbose_name = 'Tenant Membership'
        verbose_name_plural = 'Tenant Memberships'

    def __str__(self):
        return f'{self.user.email} — {self.tenant.name} ({self.role})'


class AgentProfile(models.Model):
    membership = models.OneToOneField(
        TenantMembership,
        on_delete=models.CASCADE,
        related_name='agent_profile'
    )
    zone = models.CharField(max_length=150, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    score = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agent_profiles'
        verbose_name = 'Agent Profile'
        verbose_name_plural = 'Agent Profiles'

    def __str__(self):
        return f'AgentProfile({self.membership})'


class UserNotificationPreferences(models.Model):
    membership = models.OneToOneField(
        TenantMembership,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    new_properties = models.BooleanField(default=True)
    price_updates = models.BooleanField(default=True)
    appointment_reminders = models.BooleanField(default=True)
    offers = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_notification_preferences'
        verbose_name = 'User Notification Preferences'
        verbose_name_plural = 'User Notification Preferences'

    def __str__(self):
        return f'NotifPrefs({self.membership})'


class ClientFinancialProfile(models.Model):
    """Perfil financiero del cliente para cálculo de presupuesto de compra."""
    class LoanType(models.TextChoices):
        INDIVIDUAL = 'individual', 'Individual'
        CONYUGAL = 'conyugal', 'Conyugal'
        COFINAVIT = 'cofinavit', 'Cofinavit'

    membership = models.OneToOneField(
        TenantMembership,
        on_delete=models.CASCADE,
        related_name='financial_profile'
    )
    loan_type = models.CharField(max_length=20, choices=LoanType.choices)
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2)
    partner_monthly_income = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True)
    savings_for_enganche = models.DecimalField(max_digits=12, decimal_places=2)
    has_infonavit = models.BooleanField(default=False)
    infonavit_subcuenta_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True)
    calculated_budget = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'client_financial_profiles'
        verbose_name = 'Client Financial Profile'
        verbose_name_plural = 'Client Financial Profiles'

    def __str__(self):
        return f'FinancialProfile({self.membership.user.email}, {self.loan_type})'


class OTPCode(models.Model):
    email = models.EmailField(db_index=True)
    code_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = 'otp_codes'
        verbose_name = 'OTP Code'
        verbose_name_plural = 'OTP Codes'

    def __str__(self):
        return f'OTP({self.email}, expires={self.expires_at})'
