from django.core.mail import send_mail
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework import status

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from ..models import User, TenantMembership
from ..serializers.auth import OTPRequestSerializer, OTPVerifySerializer, MembershipSerializer, RegisterSerializer
from ..otp import create_otp, validate_otp, is_verify_blocked


class OTPRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp_request'

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        # Crear usuario si no existe — created=True significa usuario nuevo
        _, created = User.objects.get_or_create(
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

        return Response({
            'message': 'OTP enviado al email',
            'email': email,
            'is_new_user': created,
        })


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'otp_verify'

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        token = serializer.validated_data['token']

        if is_verify_blocked(email):
            return Response(
                {'error': 'Demasiados intentos fallidos. Intenta en 15 minutos.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        if not validate_otp(email, token):
            return Response(
                {'error': 'Código inválido o expirado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.get(email=email)

        # Actualizar perfil si se enviaron campos opcionales
        update_fields = []
        for field in ('first_name', 'last_name', 'phone'):
            value = serializer.validated_data.get(field)
            if value:
                setattr(user, field, value)
                update_fields.append(field)
        if update_fields:
            user.save(update_fields=update_fields)

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
                'phone': user.phone,
                'memberships': MembershipSerializer(memberships, many=True).data,
            }
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'error': 'El campo refresh es requerido.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {'error': 'Token inválido o ya fue revocado.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response({'message': 'Sesión cerrada'})


class GoogleLoginView(APIView):
    """
    Login con Google Identity.
    Acepta { "idToken": "..." } (access_token de Google OAuth2).
    Verifica con Google userinfo, crea o recupera el usuario, y retorna JWT.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth_google'

    def post(self, request):
        import requests as http_requests

        access_token = request.data.get('idToken')
        if not access_token:
            return Response(
                {'error': 'idToken es requerido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verificar el token con Google userinfo endpoint
        try:
            google_response = http_requests.get(
                'https://www.googleapis.com/oauth2/v3/userinfo',
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10,
            )
            if google_response.status_code != 200:
                return Response(
                    {'error': 'Token de Google inválido.'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            idinfo = google_response.json()
        except Exception:
            return Response(
                {'error': 'Error al verificar con Google.'},
                status=status.HTTP_502_BAD_GATEWAY
            )

        email = idinfo.get('email')
        if not email or not idinfo.get('email_verified'):
            return Response(
                {'error': 'Email no verificado por Google.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        first_name = idinfo.get('given_name', '')
        last_name = idinfo.get('family_name', '')
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'first_name': first_name,
                'last_name': last_name,
                'auth_provider': User.AuthProvider.GOOGLE,
                'is_active': True,
            }
        )

        # Si el usuario ya existía, actualizar avatar y provider si venía de email
        if not created:
            update_fields = []
            if not user.first_name and first_name:
                user.first_name = first_name
                update_fields.append('first_name')
            if not user.last_name and last_name:
                user.last_name = last_name
                update_fields.append('last_name')
            # No sobreescribir avatar: el usuario pudo haberlo cambiado manualmente
            if user.auth_provider == User.AuthProvider.EMAIL:
                user.auth_provider = User.AuthProvider.GOOGLE
                update_fields.append('auth_provider')
            if update_fields:
                user.save(update_fields=update_fields)

        # Crear membresía client si no tiene ninguna
        if not TenantMembership.objects.filter(user=user, is_active=True).exists():
            from apps.tenants.models import Tenant
            tenant = Tenant.objects.filter(is_active=True).first()
            if tenant:
                TenantMembership.objects.create(user=user, tenant=tenant, role='client')

        memberships = TenantMembership.objects.filter(
            user=user, is_active=True
        ).select_related('tenant')

        from ..serializers.auth import MembershipSerializer
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone,
                'memberships': MembershipSerializer(memberships, many=True).data,
            }
        })


class AppleLoginView(APIView):
    """
    Login con Apple Sign In (stub — pendiente de implementación).
    Request: { "identityToken": "eyJ..." }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        return Response(
            {'error': 'Not implemented yet'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth_register'

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        email = data['email']

        if User.objects.filter(email=email).exists():
            return Response(
                {'error': 'El usuario ya existe, usa login'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.create(
            email=email,
            first_name=data['first_name'],
            last_name=data['last_name'],
            phone=data.get('phone', ''),
            is_active=True,
        )

        from apps.tenants.models import Tenant
        tenant = Tenant.objects.filter(is_active=True).first()
        if tenant:
            TenantMembership.objects.create(
                user=user,
                tenant=tenant,
                role=TenantMembership.Role.CLIENT,
                is_active=True,
            )

        try:
            code = create_otp(email)
        except ValueError:
            return Response(
                {'error': 'Demasiados intentos. Intenta en 60 segundos.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        send_mail(
            subject='Tu código de acceso a Avakanta',
            message=f'Tu código OTP es: {code}\nExpira en 10 minutos.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        return Response(
            {'message': 'Usuario creado. OTP enviado al email.', 'email': email},
            status=status.HTTP_201_CREATED,
        )
