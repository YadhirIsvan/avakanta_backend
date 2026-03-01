from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import StandardPagination
from apps.users.models import TenantMembership
from .models import Notification
from .serializers import NotificationSerializer


def _get_membership(request):
    return TenantMembership.objects.get(
        user=request.user, tenant=request.tenant, is_active=True
    )


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get(self, request):
        membership = _get_membership(request)

        qs = Notification.objects.filter(membership=membership)

        # unread_count is always across ALL notifications, regardless of filter
        unread_count = qs.filter(is_read=False).count()

        is_read = request.query_params.get('is_read')
        if is_read is not None:
            qs = qs.filter(is_read=is_read.lower() == 'true')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        paginated = paginator.get_paginated_response(
            NotificationSerializer(page, many=True).data
        )
        # Inject unread_count into the paginated response
        paginated.data['unread_count'] = unread_count
        return paginated


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        membership = _get_membership(request)

        notification = Notification.objects.filter(
            pk=pk, membership=membership
        ).first()
        if not notification:
            return Response({'error': 'Notificación no encontrada.'}, status=404)

        notification.is_read = True
        notification.save(update_fields=['is_read'])

        return Response({'is_read': True})


class NotificationReadAllView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        membership = _get_membership(request)

        count = Notification.objects.filter(
            membership=membership, is_read=False
        ).update(is_read=True)

        return Response({'marked_as_read': count})
