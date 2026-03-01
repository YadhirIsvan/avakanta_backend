from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenants.models import Tenant
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

        lead = SellerLead.objects.create(
            tenant=tenant,
            full_name=data['full_name'],
            email=data['email'],
            phone=data['phone'],
            property_type=data['property_type'],
            location=data.get('location', ''),
            square_meters=data.get('square_meters'),
            bedrooms=data.get('bedrooms'),
            bathrooms=data.get('bathrooms'),
            expected_price=data.get('expected_price'),
            status=SellerLead.Status.NEW,
        )

        return Response({
            'id': lead.pk,
            'full_name': lead.full_name,
            'status': lead.status,
            'message': 'Tu solicitud ha sido recibida. Te contactaremos pronto.',
        }, status=201)
