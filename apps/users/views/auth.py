from django.core.mail import send_mail
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status

from rest_framework_simplejwt.tokens import RefreshToken

from ..models import User, TenantMembership
from ..serializers.auth import OTPRequestSerializer, OTPVerifySerializer, MembershipSerializer
from ..otp import create_otp, validate_otp


class OTPRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        # Crear usuario si no existe
        User.objects.get_or_create(
            email=email,
            defaults={'is_active': True}
        )

        # Generar OTP (lanza ValueError si rate-limited)
        try:
            code = create_otp(email)
        except ValueError:
            return Response(
                {'error': 'Demasiados intentos. Intenta en 60 segundos.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Enviar email (consola en dev)
        send_mail(
            subject='Tu código de acceso a Avakanta',
            message=f'Tu código OTP es: {code}\nExpira en 10 minutos.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        return Response({'message': 'OTP enviado al email', 'email': email})


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        token = serializer.validated_data['token']

        if not validate_otp(email, token):
            return Response(
                {'error': 'Código inválido o expirado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.get(email=email)

        # Si no tiene membresía activa, crearla como client en el tenant default
        if not TenantMembership.objects.filter(user=user, is_active=True).exists():
            from apps.tenants.models import Tenant
            tenant = Tenant.objects.filter(is_active=True).first()
            if tenant:
                TenantMembership.objects.create(user=user, tenant=tenant, role='client')

        memberships = TenantMembership.objects.filter(
            user=user, is_active=True
        ).select_related('tenant')

        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'memberships': MembershipSerializer(memberships, many=True).data,
            }
        })
