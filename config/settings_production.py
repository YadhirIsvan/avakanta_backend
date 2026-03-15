"""
Configuración de producción para Avakanta.
Cargado cuando DJANGO_SETTINGS_MODULE=config.settings_production.

Hereda todo de config.settings y sobreescribe únicamente lo necesario
para el entorno VPS con Nginx como reverse proxy externo (sin SSL en Django).
"""
from config.settings import *  # noqa: F401, F403
from pathlib import Path
from decouple import config

# ---------------------------------------------------------------------------
# Seguridad base
# ---------------------------------------------------------------------------
DEBUG = config('DEBUG', default=False, cast=bool)

# ---------------------------------------------------------------------------
# SSL / HTTPS — CRÍTICO para entorno detrás de Nginx
#
# settings.py activa SECURE_SSL_REDIRECT=True cuando DEBUG=False.
# Con Nginx como proxy: Nginx recibe HTTPS del cliente → habla HTTP con
# Gunicorn → Django ve HTTP → intenta redirigir a HTTPS → loop → 503.
#
# Solución: Nginx termina SSL. Django confía en el header X-Forwarded-Proto
# que Nginx inyecta para saber que la conexión original era HTTPS.
# ---------------------------------------------------------------------------
SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ---------------------------------------------------------------------------
# Media files — volumen Docker persistente
# BASE_DIR / 'media' quedaría dentro del contenedor y se perdería al rebuild.
# ---------------------------------------------------------------------------
MEDIA_ROOT = Path('/app/media')
MEDIA_URL = '/media/'

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_ROOT = Path('/app/staticfiles')
STATIC_URL = '/static/'

# ---------------------------------------------------------------------------
# Logging — stdout/stderr para que docker compose logs los capture
# ---------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': config('DJANGO_LOG_LEVEL', default='WARNING'),
            'propagate': False,
        },
    },
}
