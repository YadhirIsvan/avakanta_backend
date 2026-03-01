# CLAUDE.md — Avakanta Backend

> Instrucciones para Claude Code para implementar el backend de Avakanta.
> Metodología: Spec-Driven Development (SDD)

---

## Documentación (Fuente de Verdad)

Leer estos archivos ANTES de implementar cualquier task. Son la fuente de verdad del proyecto:

| Documento | Ruta | Propósito |
|---|---|---|
| Schema BD | `docs/schema.dbml` | Definición exacta de tablas, columnas, relaciones y enums |
| PRD | `docs/prd.md` | Reglas de negocio, flujos, roles y pantallas |
| Spec API | `docs/spec.md` | Contratos de API: endpoints, request/response, permisos |
| Tasks | `docs/tasks.md` | Lista ordenada de tareas con criterios de "done" |

**Regla:** Si algo no está en estos documentos, preguntar antes de inventar. No asumir.

---

## Stack Tecnológico

```
Django 5.1
Django REST Framework 3.15
PostgreSQL
djangorestframework-simplejwt 5.3    # JWT Auth
django-filter 24.1                   # Filtros en querysets
django-cors-headers 4.3              # CORS
drf-spectacular 0.27                 # OpenAPI / Swagger / ReDoc
Pillow 10.4                          # Procesamiento de imágenes
psycopg2-binary 2.9                  # Driver PostgreSQL
python-decouple 3.8                  # Variables de entorno (.env)
```

---

## Estructura del Proyecto

```
avakanta/                        ← raíz del backend
├── config/
│   ├── settings.py              ← configuración central
│   ├── urls.py                  ← router principal
│   └── wsgi.py
├── core/
│   ├── middleware.py            ← TenantMiddleware
│   ├── permissions.py           ← IsAdmin, IsAgent, IsClient, IsAdminOrAgent
│   ├── pagination.py            ← StandardPagination (limit/offset)
│   ├── mixins.py                ← TenantQuerySetMixin
│   ├── utils.py                 ← generate_matricula, calculate_trend, days_listed
│   └── validators.py            ← validate_file_type, validate_file_size
├── apps/
│   ├── tenants/                 ← Tenant model
│   ├── users/                   ← User, TenantMembership, AgentProfile, OTP
│   ├── locations/               ← Country, State, City, Amenity
│   ├── properties/              ← Property, PropertyImage, PropertyAssignment, etc.
│   ├── appointments/            ← Appointment, AgentSchedule, AvailabilityService
│   ├── transactions/            ← PurchaseProcess, SaleProcess, SellerLead
│   └── notifications/           ← Notification, UserNotificationPreferences
├── docs/
│   ├── prd.md
│   ├── spec.md
│   ├── tasks.md
│   └── schema.dbml
├── CLAUDE.md                    ← este archivo
├── manage.py
├── requirements.txt
└── .env                         ← nunca commitear, ver .env.example
```

---

## Reglas de Multi-Tenancy

Estas reglas son **NO NEGOCIABLES**. Violarlas es un bug de seguridad crítico.

### Regla 1 — El tenant viene del usuario autenticado, NUNCA del request

```python
# CORRECTO: el tenant se obtiene de request.tenant (puesto por TenantMiddleware)
tenant = request.tenant

# INCORRECTO: nunca tomar tenant_id del body del request
tenant_id = request.data.get('tenant_id')  # ❌ JAMÁS
```

### Regla 2 — Todo ViewSet de datos del tenant usa TenantQuerySetMixin

```python
# CORRECTO
class PropertyViewSet(TenantQuerySetMixin, ModelViewSet):
    queryset = Property.objects.all()  # el mixin filtra por tenant automáticamente

# INCORRECTO (olvidan el mixin)
class PropertyViewSet(ModelViewSet):
    queryset = Property.objects.all()  # ❌ retorna datos de TODOS los tenants
```

### Regla 3 — Catálogos globales NO tienen tenant_id

Las tablas `countries`, `states`, `cities`, `amenities` son compartidas. No filtrar por tenant en estas.

### Regla 4 — Un usuario puede tener membresías en múltiples tenants

El `User` no tiene `tenant_id`. La relación está en `TenantMembership`. Un mismo email puede ser cliente en Tenant A y agente en Tenant B.

### Regla 5 — TenantMiddleware no aplica en rutas públicas

Las rutas en `PUBLIC_PATHS` no requieren tenant (ver `core/middleware.py`).

---

## Convenciones de Código

### Estructura de cada app

```
apps/mi_app/
├── models.py           ← modelos Django
├── serializers/
│   ├── public.py       ← serializers para endpoints públicos
│   ├── admin.py        ← serializers para panel admin
│   ├── agent.py        ← serializers para panel agente
│   └── client.py       ← serializers para panel cliente
├── views/
│   ├── public.py       ← views para endpoints públicos
│   ├── admin.py        ← views para panel admin
│   ├── agent.py        ← views para panel agente
│   └── client.py       ← views para panel cliente
├── urls/
│   ├── public.py
│   ├── admin.py
│   └── ...
├── services.py         ← lógica de negocio compleja (AvailabilityService, etc.)
├── filters.py          ← FilterSet de django-filter
├── tests/
│   ├── test_models.py
│   ├── test_public.py
│   └── ...
├── apps.py
├── admin.py
└── migrations/
```

### Nombrado

- Modelos: `PascalCase` (e.g., `PurchaseProcess`)
- Serializers: `[Rol][Modelo][Acción]Serializer` (e.g., `AdminPropertyListSerializer`)
- Views: `[Modelo][Acción]View` o `[Modelo]ViewSet`
- URLs: usar kebab-case (e.g., `purchase-processes`, `seller-leads`)
- Variables y funciones: `snake_case`
- Constantes: `UPPER_SNAKE_CASE`

### Serializers

- Usar `SerializerMethodField` para campos computados (`days_listed`, `interested`, `image`, `trend`)
- Usar `annotate` en el queryset (no en el serializer) para conteos eficientes
- Nunca exponer campos que no estén en la spec
- Incluir `read_only=True` en campos que no se editan

```python
# CORRECTO: campo computado en serializer
class PublicPropertyListSerializer(serializers.ModelSerializer):
    days_listed = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    def get_days_listed(self, obj):
        return (date.today() - obj.created_at.date()).days

    def get_image(self, obj):
        cover = obj.images.filter(is_cover=True).first()
        return cover.image_url if cover else None
```

### Views

- Usar `TenantQuerySetMixin` en todos los ViewSets de datos del tenant
- Usar la permission class correcta según la matriz de spec sección 5.2
- Usar `StandardPagination` (configurado globalmente en settings)
- Para acciones custom (e.g., `/status`, `/convert`), usar `@action`

```python
# Patrón típico para un ViewSet de admin
class PurchaseProcessViewSet(TenantQuerySetMixin, ModelViewSet):
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardPagination
    queryset = PurchaseProcess.objects.select_related(
        'property', 'client_membership__user', 'agent_membership__user'
    )

    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        ...
```

### Transacciones atómicas

Usar `transaction.atomic()` cuando una operación modifica múltiples modelos:

```python
# CORRECTO para operaciones que crean múltiples objetos
@transaction.atomic
def convert_seller_lead(lead, agent_membership):
    user, created = User.objects.get_or_create(email=lead.email, ...)
    property = Property.objects.create(...)
    sale_process = SaleProcess.objects.create(...)
    lead.status = 'converted'
    lead.save()
    return property, sale_process
```

### Manejo de archivos

- Usar `upload_to` con función para organizar por `property_id` o `process_id`
- Validar mime type y tamaño en el serializer, no en el modelo
- Los archivos se sirven desde `MEDIA_URL`

```python
def property_image_upload_path(instance, filename):
    return f'properties/{instance.property_id}/images/{filename}'
```

---

## Configuración de Permisos

Tabla de referencia rápida. Consultar spec sección 5.2 para la lista completa:

| Base URL | Permission Class |
|---|---|
| `/api/v1/public/` | `AllowAny` |
| `/api/v1/auth/` | `AllowAny` (excepto logout) |
| `/api/v1/admin/` | `IsAuthenticated + IsAdmin` |
| `/api/v1/agent/` | `IsAuthenticated + IsAgent` |
| `/api/v1/client/` | `IsAuthenticated + IsClient` |
| `/api/v1/catalogs/` | `AllowAny` |
| `/api/v1/notifications/` | `IsAuthenticated` |

---

## JWT y Autenticación

```python
# En settings.py
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=2),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Cómo obtener la membresía del usuario en una view
def get_current_membership(request):
    return TenantMembership.objects.get(
        user=request.user,
        tenant=request.tenant,
        is_active=True
    )
```

---

## URLs de la API

Referencia rápida del router principal (`config/urls.py`):

```
/api/v1/auth/           → apps.users.urls.auth
/api/v1/public/         → apps.properties.urls.public + apps.appointments.urls.public + apps.transactions.urls.public
/api/v1/admin/          → apps.*.urls.admin (properties, users, appointments, transactions)
/api/v1/agent/          → apps.*.urls.agent
/api/v1/client/         → apps.*.urls.client
/api/v1/catalogs/       → apps.locations.urls
/api/v1/notifications/  → apps.notifications.urls
/api/schema/            → drf-spectacular
/api/docs/              → Swagger UI
/api/redoc/             → ReDoc
```

---

## Workflow de Ejecución Task por Task

Seguir este proceso para cada task de `docs/tasks.md`:

### 1. Leer la task

Abrir `docs/tasks.md` y leer la task completa:
- Descripción
- Archivos que toca
- Criterio de "done"

### 2. Consultar la spec

Buscar en `docs/spec.md` el endpoint o modelo relevante. Verificar el JSON exacto que debe retornar.

### 3. Consultar el schema

Abrir `docs/schema.dbml` para ver exactamente las columnas, tipos y relaciones del modelo.

### 4. Implementar

- Crear o modificar los archivos listados en la task
- Seguir las convenciones de código de este CLAUDE.md
- No crear archivos adicionales que no sean necesarios

### 5. Verificar el criterio de "done"

Antes de marcar una task como completa, verificar CADA punto del criterio de "done" de la task.

### 6. Marcar como completada

Cambiar `[ ]` a `[x]` en `docs/tasks.md` para la task completada.

### 7. Siguiente task

Tomar la siguiente task de la lista, respetando el orden de dependencias.

---

## Comandos Útiles

```bash
# Arrancar el servidor de desarrollo
python manage.py runserver

# Crear migraciones
python manage.py makemigrations <app_name>

# Aplicar migraciones
python manage.py migrate

# Cargar fixtures
python manage.py loaddata <fixture_name>

# Correr todos los tests
python manage.py test

# Correr tests de una app
python manage.py test apps.users.tests

# Correr un test específico
python manage.py test apps.users.tests.test_auth.OTPTestCase

# Shell de Django
python manage.py shell

# Crear superusuario
python manage.py createsuperuser

# Ver el schema de OpenAPI generado
python manage.py spectacular --file schema.yaml
```

---

## Variables de Entorno (.env)

```bash
# .env.example
SECRET_KEY=django-insecure-CAMBIA-ESTO-EN-PRODUCCION
DEBUG=True
DATABASE_URL=postgres://avakanta:password@localhost:5432/avakanta_db
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Para producción
# DEBUG=False
# EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# EMAIL_HOST=smtp.tuproveedor.com
# EMAIL_PORT=587
# EMAIL_HOST_USER=tu@email.com
# EMAIL_HOST_PASSWORD=tu_password
```

---

## Reglas de Negocio Críticas

Estas reglas del PRD deben respetarse siempre. Si hay duda, releer `docs/prd.md` sección 13:

1. **Progreso del pipeline de compra:** `lead=0%, visita=11%, interes=22%, pre_aprobacion=33%, avaluo=44%, credito=56%, docs_finales=67%, escrituras=78%, cerrado=100%`

2. **`allow_upload=True` solo en:** `pre_aprobacion`, `credito`, `docs_finales`

3. **Matrícula de cita:** Formato `CLI-{año}-{consecutivo}`, consecutivo por tenant y por año (reinicia en 001 cada año)

4. **Campos computados (NO son columnas):** `days_listed`, `interested`, `trend`, `image`, `progress_step`, `address`, `agent`. Se calculan en el serializer o con `annotate`.

5. **`views` se incrementa en +1** cada vez que se llama `GET /public/properties/{id}`

6. **Conversión de seller lead es atómica:** Property + SaleProcess + lead.status=converted, todo o nada

7. **Cuando `sale_process.status=publicacion`:** Actualizar `property.listing_type=sale` y `property.status=disponible` en la misma transacción

8. **Cuando `purchase_process.status=cerrado`:** Llenar `sale_price`, `payment_method`, `closed_at`

9. **Solo el agente con `is_visible=True` aparece en el frontend público** (en el detalle de propiedad)

10. **Tenant aislamiento:** `TenantQuerySetMixin` en todos los ViewSets de datos del tenant, sin excepciones

---

## Señales de Alerta (No hacer esto)

- ❌ Tomar `tenant_id` del body del request
- ❌ Olvidar `TenantQuerySetMixin` en un ViewSet
- ❌ Usar `AllowAny` en endpoints protegidos
- ❌ Hardcodear el `tenant_id = 1` en el código
- ❌ Retornar datos sin paginar (siempre usar `StandardPagination`)
- ❌ Modificar múltiples modelos sin `transaction.atomic()`
- ❌ Almacenar el OTP en texto plano (siempre hasheado)
- ❌ Aceptar archivos sin validar mime type y tamaño
- ❌ Retornar un JSON diferente al que está en `docs/spec.md`
- ❌ Crear tablas o columnas que no están en `docs/schema.dbml`
