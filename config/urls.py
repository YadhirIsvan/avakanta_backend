from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth
    path('api/v1/auth/', include('apps.users.urls.auth')),

    # Público
    path('api/v1/public/', include('apps.properties.urls.public')),
    path('api/v1/public/', include('apps.appointments.urls.public')),
    path('api/v1/public/', include('apps.transactions.urls.public')),

    # Admin
    path('api/v1/admin/', include('apps.properties.urls.admin')),
    path('api/v1/admin/', include('apps.users.urls.admin')),
    path('api/v1/admin/', include('apps.appointments.urls.admin')),
    path('api/v1/admin/', include('apps.transactions.urls.admin')),

    # Agent
    path('api/v1/agent/', include('apps.users.urls.agent')),
    path('api/v1/agent/', include('apps.properties.urls.agent')),
    path('api/v1/agent/', include('apps.appointments.urls.agent')),

    # Client
    path('api/v1/client/', include('apps.users.urls.client')),
    path('api/v1/client/', include('apps.transactions.urls.client')),

    # Notificaciones (todos los roles autenticados)
    path('api/v1/notifications/', include('apps.notifications.urls')),

    # Catálogos globales (público)
    path('api/v1/catalogs/', include('apps.locations.urls')),

    # OpenAPI / Swagger
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
