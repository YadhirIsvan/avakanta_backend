from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenants.models import Tenant
from apps.users.models import TenantMembership
from ..models import SellerLead
from ..serializers.public import SellerLeadSerializer, SaleProcessPublicCreateSerializer
from ..services import create_sale_process_from_form


def _get_default_tenant():
    """Returns the default tenant for public endpoints."""
    return Tenant.objects.filter(is_active=True).order_by('pk').first()


def _resolve_membership(request):
    """
    Resolve client membership from JWT auth.
    Returns the user's first active membership, regardless of tenant.
    """
    try:
        user = request.user
        if user and user.is_authenticated:
            return TenantMembership.objects.filter(
                user=user, is_active=True
            ).select_related('tenant').first()
    except Exception:
        pass
    return None


class SellerLeadCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SellerLeadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = serializer.validated_data

        membership = _resolve_membership(request)
        tenant = membership.tenant if membership else _get_default_tenant()

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

        if membership:
            lead_data['created_by_membership'] = membership

        lead = SellerLead.objects.create(**lead_data)

        return Response({
            'id': lead.pk,
            'full_name': lead.full_name,
            'status': lead.status,
            'message': 'Tu solicitud ha sido recibida. Te contactaremos pronto.',
        }, status=201)


class SaleProcessCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SaleProcessPublicCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = serializer.validated_data

        membership = _resolve_membership(request)
        tenant = membership.tenant if membership else _get_default_tenant()

        prop, sale_process = create_sale_process_from_form(
            tenant=tenant,
            name_form=data['name_form'],
            phone_form=data['phone_form'],
            property_type=data['property_type'],
            location=data.get('location', ''),
            square_meters=data.get('square_meters'),
            bedrooms=data.get('bedrooms'),
            bathrooms=data.get('bathrooms'),
            expected_price=data.get('expected_price'),
            client_membership=membership,
        )

        return Response({
            'id': sale_process.pk,
            'property_id': prop.pk,
            'status': sale_process.status,
            'message': 'Tu solicitud ha sido recibida. Te contactaremos pronto.',
        }, status=201)
