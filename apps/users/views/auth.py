from django.core.mail import send_mail
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status

from ..models import User
from ..serializers.auth import OTPRequestSerializer
from ..otp import create_otp


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
