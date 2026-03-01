from rest_framework.permissions import BasePermission
from apps.users.models import TenantMembership


def _get_membership(request):
    if not request.tenant or not request.user or not request.user.is_authenticated:
        return None
    try:
        return TenantMembership.objects.get(
            user=request.user,
            tenant=request.tenant,
            is_active=True
        )
    except TenantMembership.DoesNotExist:
        return None


class IsAdmin(BasePermission):
    """Permite acceso solo a miembros con rol 'admin' en el tenant actual."""

    def has_permission(self, request, view):
        membership = _get_membership(request)
        return membership is not None and membership.role == 'admin'


class IsAgent(BasePermission):
    """Permite acceso solo a miembros con rol 'agent' en el tenant actual."""

    def has_permission(self, request, view):
        membership = _get_membership(request)
        return membership is not None and membership.role == 'agent'


class IsClient(BasePermission):
    """Permite acceso solo a miembros con rol 'client' en el tenant actual."""

    def has_permission(self, request, view):
        membership = _get_membership(request)
        return membership is not None and membership.role == 'client'


class IsAdminOrAgent(BasePermission):
    """Permite acceso a miembros con rol 'admin' o 'agent' en el tenant actual."""

    def has_permission(self, request, view):
        membership = _get_membership(request)
        return membership is not None and membership.role in ('admin', 'agent')
