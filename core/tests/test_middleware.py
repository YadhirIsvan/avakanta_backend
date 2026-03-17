"""
Tests para TenantMiddleware — cubre especialmente los escenarios multi-tenant
con y sin header X-Tenant-ID.
"""
from django.test import TestCase, RequestFactory
from django.http import JsonResponse
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership
from core.middleware import TenantMiddleware


def _get_middleware():
    return TenantMiddleware(get_response=lambda r: JsonResponse({'ok': True}))


class TenantMiddlewareSingleTenantTest(TestCase):
    """Usuario con una sola membresía activa."""

    def setUp(self):
        self.factory = RequestFactory()
        self.tenant = Tenant.objects.create(
            name="Único", slug="unico", email="u@t.com", is_active=True
        )
        self.user = User.objects.create(email="single@test.com", is_active=True)
        TenantMembership.objects.create(
            user=self.user, tenant=self.tenant, role="client", is_active=True
        )

    def test_single_membership_resolves_tenant_without_header(self):
        """Un único tenant activo se resuelve automáticamente."""
        middleware = _get_middleware()
        request = self.factory.get("/api/v1/client/profile")
        request.user = self.user
        middleware(request)
        self.assertEqual(request.tenant, self.tenant)

    def test_user_without_active_membership_returns_403(self):
        """Usuario sin membresía activa recibe 403."""
        user2 = User.objects.create(email="nomember@test.com", is_active=True)
        TenantMembership.objects.create(
            user=user2, tenant=self.tenant, role="client", is_active=False
        )
        middleware = _get_middleware()
        request = self.factory.get("/api/v1/client/profile")
        request.user = user2
        response = middleware(request)
        self.assertEqual(response.status_code, 403)

    def test_user_without_any_membership_returns_403(self):
        """Usuario sin ninguna membresía recibe 403."""
        user3 = User.objects.create(email="notenantever@test.com", is_active=True)
        middleware = _get_middleware()
        request = self.factory.get("/api/v1/admin/properties")
        request.user = user3
        response = middleware(request)
        self.assertEqual(response.status_code, 403)


class TenantMiddlewareMultiTenantTest(TestCase):
    """Usuario con membresías en múltiples tenants."""

    def setUp(self):
        self.factory = RequestFactory()
        self.tenant_a = Tenant.objects.create(
            name="A", slug="a", email="a@t.com", is_active=True
        )
        self.tenant_b = Tenant.objects.create(
            name="B", slug="b", email="b@t.com", is_active=True
        )
        self.user = User.objects.create(email="multi@test.com", is_active=True)
        TenantMembership.objects.create(
            user=self.user, tenant=self.tenant_a, role="admin", is_active=True
        )
        TenantMembership.objects.create(
            user=self.user, tenant=self.tenant_b, role="agent", is_active=True
        )

    def test_multi_tenant_without_header_returns_403(self):
        """Multi-tenant sin X-Tenant-ID retorna 403."""
        middleware = _get_middleware()
        request = self.factory.get("/api/v1/admin/properties")
        request.user = self.user
        response = middleware(request)
        self.assertEqual(response.status_code, 403)

    def test_multi_tenant_with_tenant_a_header_resolves(self):
        """X-Tenant-ID de tenant_a resuelve correctamente."""
        middleware = _get_middleware()
        request = self.factory.get(
            "/api/v1/admin/properties",
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )
        request.user = self.user
        middleware(request)
        self.assertEqual(request.tenant, self.tenant_a)

    def test_multi_tenant_with_tenant_b_header_resolves(self):
        """X-Tenant-ID de tenant_b resuelve correctamente."""
        middleware = _get_middleware()
        request = self.factory.get(
            "/api/v1/admin/properties",
            HTTP_X_TENANT_ID=str(self.tenant_b.id),
        )
        request.user = self.user
        middleware(request)
        self.assertEqual(request.tenant, self.tenant_b)

    def test_multi_tenant_with_foreign_tenant_header_returns_403(self):
        """X-Tenant-ID de un tenant al que no pertenece retorna 403."""
        other = Tenant.objects.create(
            name="C", slug="c", email="c@t.com", is_active=True
        )
        middleware = _get_middleware()
        request = self.factory.get(
            "/api/v1/admin/properties",
            HTTP_X_TENANT_ID=str(other.id),
        )
        request.user = self.user
        response = middleware(request)
        self.assertEqual(response.status_code, 403)

    def test_multi_tenant_with_nonexistent_tenant_id_returns_403(self):
        """X-Tenant-ID con ID que no existe retorna 403."""
        middleware = _get_middleware()
        request = self.factory.get(
            "/api/v1/admin/properties",
            HTTP_X_TENANT_ID="99999",
        )
        request.user = self.user
        response = middleware(request)
        self.assertEqual(response.status_code, 403)


class TenantMiddlewarePublicPathsTest(TestCase):
    """Rutas públicas omiten la resolución de tenant."""

    def setUp(self):
        self.factory = RequestFactory()

    def _anon_request(self, path):
        """Request sin usuario autenticado (simula AnonymousUser)."""
        from unittest.mock import Mock
        request = self.factory.get(path)
        request.user = Mock(is_authenticated=False)
        return request

    def test_auth_path_skips_tenant(self):
        """/api/v1/auth/ no requiere tenant."""
        middleware = _get_middleware()
        request = self._anon_request("/api/v1/auth/login")
        middleware(request)
        self.assertIsNone(request.tenant)

    def test_public_path_skips_tenant(self):
        """/api/v1/public/ no requiere tenant."""
        middleware = _get_middleware()
        request = self._anon_request("/api/v1/public/properties")
        middleware(request)
        self.assertIsNone(request.tenant)

    def test_catalogs_path_skips_tenant(self):
        """/api/v1/catalogs/ no requiere tenant."""
        middleware = _get_middleware()
        request = self._anon_request("/api/v1/catalogs/cities")
        middleware(request)
        self.assertIsNone(request.tenant)

    def test_schema_path_skips_tenant(self):
        """/api/schema/ no requiere tenant."""
        middleware = _get_middleware()
        request = self._anon_request("/api/schema/")
        middleware(request)
        self.assertIsNone(request.tenant)

    def test_unauthenticated_protected_path_passes_through(self):
        """Sin auth en ruta protegida: tenant=None, DRF maneja el 401."""
        middleware = _get_middleware()
        request = self._anon_request("/api/v1/admin/properties")
        middleware(request)
        self.assertIsNone(request.tenant)
