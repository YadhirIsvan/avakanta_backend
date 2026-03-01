from datetime import date

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAgent
from apps.users.models import TenantMembership
from apps.transactions.models import PurchaseProcess
from apps.appointments.models import Appointment


class AgentDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsAgent]

    def get(self, request):
        membership = (
            TenantMembership.objects
            .select_related('user', 'agent_profile')
            .get(user=request.user, tenant=request.tenant, is_active=True)
        )
        profile = membership.agent_profile
        user = membership.user

        # Stats
        active_leads = PurchaseProcess.objects.filter(
            tenant=request.tenant,
            agent_membership=membership,
        ).exclude(status__in=['cerrado', 'cancelado']).count()

        today_appointments = Appointment.objects.filter(
            tenant=request.tenant,
            agent_membership=membership,
            scheduled_date=date.today(),
        ).count()

        today = date.today()
        month_sales = PurchaseProcess.objects.filter(
            tenant=request.tenant,
            agent_membership=membership,
            status='cerrado',
            closed_at__year=today.year,
            closed_at__month=today.month,
        ).count()

        return Response({
            'agent': {
                'id': profile.pk,
                'name': user.get_full_name() or user.email,
                'avatar': user.avatar,
                'zone': profile.zone,
                'score': str(profile.score),
            },
            'stats': {
                'active_leads': active_leads,
                'today_appointments': today_appointments,
                'month_sales': month_sales,
            },
        })
