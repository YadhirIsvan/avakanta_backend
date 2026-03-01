import random
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password

OTP_EXPIRY_MINUTES = 10
OTP_RATE_LIMIT = 5        # máximo intentos por email por hora
OTP_RATE_WINDOW_HOURS = 1


def generate_otp():
    """Genera un código OTP aleatorio de exactamente 6 dígitos."""
    return str(random.randint(0, 999999)).zfill(6)


def hash_otp(code):
    """Retorna el hash del código OTP. Nunca almacenar el código en texto plano."""
    return make_password(code)


def verify_otp(code, code_hash):
    """Verifica si el código coincide con el hash almacenado."""
    return check_password(code, code_hash)


def is_rate_limited(email):
    """
    Retorna True si el email superó el límite de 5 intentos en la última hora.
    """
    from .models import OTPCode
    window_start = timezone.now() - timedelta(hours=OTP_RATE_WINDOW_HOURS)
    count = OTPCode.objects.filter(
        email=email,
        created_at__gte=window_start
    ).count()
    return count >= OTP_RATE_LIMIT


def create_otp(email):
    """
    Genera un OTP, lo hashea, lo guarda en BD y retorna el código en claro
    (solo para enviarlo por email, jamás almacenarlo).

    Raises ValueError si el email está rate-limited.
    """
    from .models import OTPCode

    if is_rate_limited(email):
        raise ValueError('Límite de intentos alcanzado. Intenta de nuevo en una hora.')

    code = generate_otp()
    OTPCode.objects.create(
        email=email,
        code_hash=hash_otp(code),
        expires_at=timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES),
    )
    return code


def validate_otp(email, code):
    """
    Valida el código OTP para el email dado.
    Si es correcto, marca el OTP como usado y lo elimina.

    Retorna True si válido, False en caso contrario.
    """
    from .models import OTPCode

    now = timezone.now()
    candidates = OTPCode.objects.filter(
        email=email,
        expires_at__gt=now,
        is_used=False,
    ).order_by('-created_at')

    for otp in candidates:
        if verify_otp(code, otp.code_hash):
            otp.delete()
            return True

    return False
