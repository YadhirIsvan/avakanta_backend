from django.http import JsonResponse
from apps.tenants.models import Tenant
from apps.users.models import TenantMembership

PUBLIC_PATHS = [
    '/api/v1/auth/',
    '/api/v1/public/',
    '/api/v1/catalogs/',
    '/api/schema/',
    '/api/docs/',
    '/api/redoc/',
    '/admin/',
]


class TenantMiddleware:
    """
    Extracts the tenant from the authenticated user's membership.
    Sets request.tenant for use in views and mixins.

    Public paths bypass tenant resolution.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None

        if self._is_public_path(request.path):
            return self.get_response(request)

        if request.user and request.user.is_authenticated:
            tenant = self._resolve_tenant(request)
            if tenant is None:
                return JsonResponse(
                    {'detail': 'No se encontró una membresía activa para este usuario.'},
                    status=403
                )
            request.tenant = tenant

        return self.get_response(request)

    def _is_public_path(self, path):
        return any(path.startswith(public) for public in PUBLIC_PATHS)

    def _resolve_tenant(self, request):
        try:
            membership = TenantMembership.objects.select_related('tenant').get(
                user=request.user,
                is_active=True
            )
            return membership.tenant
        except TenantMembership.DoesNotExist:
            return None
        except TenantMembership.MultipleObjectsReturned:
            # User belongs to multiple tenants — tenant must come from header
            tenant_id = request.headers.get('X-Tenant-ID')
            if tenant_id:
                try:
                    membership = TenantMembership.objects.select_related('tenant').get(
                        user=request.user,
                        tenant_id=tenant_id,
                        is_active=True
                    )
                    return membership.tenant
                except TenantMembership.DoesNotExist:
                    return None
            return None
