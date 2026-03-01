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
