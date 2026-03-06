from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenants.models import Tenant
from apps.users.models import TenantMembership
from ..models import SellerLead
from ..serializers.public import SellerLeadSerializer


class SellerLeadCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SellerLeadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = serializer.validated_data

        tenant = Tenant.objects.get(slug='altas-montanas')

        # Get created_by_membership from request
        created_by_membership = None
        if request.user and request.user.is_authenticated:
            # Get the user's membership in the tenant
            try:
                created_by_membership = TenantMembership.objects.get(
                    user=request.user,
                    tenant=tenant
                )
            except TenantMembership.DoesNotExist:
                pass
        elif data.get('created_by_membership'):
            # Fallback to membership_id from request data
            try:
                created_by_membership = TenantMembership.objects.get(
                    id=data.get('created_by_membership'),
                    tenant=tenant
                )
            except TenantMembership.DoesNotExist:
                pass

        lead_data = {
            'tenant': tenant,
            'full_name': data['full_name'],
            'email': data['email'],
            'phone': data['phone'],
            'property_type': data['property_type'],
            'location': data.get('location', ''),
            'square_meters': data.get('square_meters'),
            'bedrooms': data.get('bedrooms'),
            'bathrooms': data.get('bathrooms'),
            'expected_price': data.get('expected_price'),
            'status': SellerLead.Status.NEW,
        }

        # Add created_by_membership if available
        if created_by_membership:
            lead_data['created_by_membership'] = created_by_membership

        lead = SellerLead.objects.create(**lead_data)

        return Response({
            'id': lead.pk,
            'full_name': lead.full_name,
            'status': lead.status,
            'message': 'Tu solicitud ha sido recibida. Te contactaremos pronto.',
        }, status=201)
