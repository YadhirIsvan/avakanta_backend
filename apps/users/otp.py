import secrets
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from django.core.cache import cache

OTP_EXPIRY_MINUTES = 10
OTP_RATE_LIMIT = 5        # máximo OTPs generados por email por hora
OTP_RATE_WINDOW_HOURS = 1
MAX_VERIFY_ATTEMPTS = 5   # máximo intentos fallidos de verificación por email


def generate_otp():
    """Genera un código OTP aleatorio de exactamente 6 dígitos (criptográficamente seguro)."""
    return str(secrets.randbelow(1_000_000)).zfill(6)


def hash_otp(code):
    """Retorna el hash del código OTP. Nunca almacenar el código en texto plano."""
    return make_password(code)


def verify_otp(code, code_hash):
    """Verifica si el código coincide con el hash almacenado."""
    return check_password(code, code_hash)


def is_rate_limited(email):
    """
    Retorna True si el email superó el límite de 5 OTPs generados en la última hora.
    """
    from .models import OTPCode
    window_start = timezone.now() - timedelta(hours=OTP_RATE_WINDOW_HOURS)
    count = OTPCode.objects.filter(
        email=email,
        created_at__gte=window_start
    ).count()
    return count >= OTP_RATE_LIMIT


def _get_verify_attempts_key(email):
    """Cache key para contar intentos fallidos de verificación."""
    return f'otp_verify_attempts:{email}'


def is_verify_blocked(email):
    """Retorna True si el email superó el máximo de intentos fallidos de verificación."""
    attempts = cache.get(_get_verify_attempts_key(email), 0)
    return attempts >= MAX_VERIFY_ATTEMPTS


def record_failed_verify(email):
    """Incrementa el contador de intentos fallidos. Se bloquea por 15 minutos."""
    key = _get_verify_attempts_key(email)
    attempts = cache.get(key, 0)
    cache.set(key, attempts + 1, timeout=900)  # 15 minutos de bloqueo


def clear_verify_attempts(email):
    """Limpia el contador de intentos fallidos tras verificación exitosa."""
    cache.delete(_get_verify_attempts_key(email))


def cleanup_expired_otps() -> int:
    """
    Elimina OTPs expirados de la BD.
    Retorna el número de registros eliminados.
    """
    from .models import OTPCode
    deleted_count, _ = OTPCode.objects.filter(expires_at__lte=timezone.now()).delete()
    return deleted_count


def create_otp(email):
    """
    Genera un OTP, lo hashea, lo guarda en BD y retorna el código en claro
    (solo para enviarlo por email, jamás almacenarlo).

    Raises ValueError si el email está rate-limited.
    """
    from .models import OTPCode

    if is_rate_limited(email):
        raise ValueError('Límite de intentos alcanzado. Intenta de nuevo en una hora.')

    # Cleanup proactivo de OTPs expirados antes de crear uno nuevo
    cleanup_expired_otps()

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
    Bloquea tras MAX_VERIFY_ATTEMPTS intentos fallidos.

    Retorna True si válido, False en caso contrario.
    """
    from .models import OTPCode

    if is_verify_blocked(email):
        return False

    now = timezone.now()
    candidates = OTPCode.objects.filter(
        email=email,
        expires_at__gt=now,
        is_used=False,
    ).order_by('-created_at')

    for otp in candidates:
        if verify_otp(code, otp.code_hash):
            otp.delete()
            clear_verify_attempts(email)
            return True

    record_failed_verify(email)
    return False
