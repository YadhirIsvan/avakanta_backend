# Tasks — Avakanta Backend

> Fuente de verdad: `docs/prd.md` · `docs/spec.md` · `docs/schema.dbml`
> Stack: Django 5.1 + DRF 3.15 + PostgreSQL
> Convención de IDs: T-NNN

**Leyenda de estado:**
- `[ ]` Pendiente
- `[x]` Completado
- `[~]` En progreso

---

## FASE 0 — Setup del Proyecto

---

### [x] T-001 — Crear proyecto Django con estructura de carpetas

**Descripción:** Inicializar el proyecto Django 5.1 con la estructura de carpetas definida en la spec (`config/`, `core/`, `apps/`, `docs/`).

**Archivos que toca:**
- `manage.py`
- `config/__init__.py`
- `config/settings.py`
- `config/urls.py`
- `config/wsgi.py`
- `core/__init__.py`
- `apps/__init__.py`

**Done cuando:**
- `python manage.py check` pasa sin errores
- La estructura de carpetas existe y coincide con la spec (sección 2)

---

### [x] T-002 — Configurar settings.py con variables de entorno

**Descripción:** Configurar `settings.py` usando `python-decouple` para separar valores sensibles en `.env`. Incluir configuración de `INSTALLED_APPS`, `DATABASES`, `LANGUAGE_CODE=es-mx`, `TIME_ZONE=America/Mexico_City`, `USE_TZ=True`, `MEDIA_ROOT/MEDIA_URL`.

**Archivos que toca:**
- `config/settings.py`
- `.env.example`
- `requirements.txt`

**Done cuando:**
- `python manage.py check` pasa sin errores
- Variables `SECRET_KEY`, `DEBUG`, `DATABASE_URL` se leen desde `.env`
- `MEDIA_ROOT` configurado para subida de archivos

---

### [x] T-003 — Configurar base de datos PostgreSQL

**Descripción:** Crear la base de datos `avakanta_db` en PostgreSQL y conectarla al proyecto. Verificar que `python manage.py migrate` crea las tablas base de Django.

**Archivos que toca:**
- `config/settings.py` (DATABASE config)
- `.env`

**Done cuando:**
- `python manage.py migrate` ejecuta sin errores
- Tablas de Django admin, auth, sessions existen en la BD

---

### [x] T-004 — Instalar y registrar todas las dependencias

**Descripción:** Instalar el stack completo y registrar en `INSTALLED_APPS`: `rest_framework`, `rest_framework_simplejwt`, `corsheaders`, `drf_spectacular`, `django_filters`.

**Archivos que toca:**
- `requirements.txt`
- `config/settings.py`

**Done cuando:**
- `pip install -r requirements.txt` instala sin errores
- `python manage.py check` pasa con todas las apps registradas

---

### [x] T-005 — Configurar CORS y JWT en settings

**Descripción:** Configurar `django-cors-headers` para permitir requests del frontend (`CORS_ALLOWED_ORIGINS`). Configurar `SIMPLE_JWT` con access token de 2h, refresh de 7 días y rotación automática (ver spec sección 4.1).

**Archivos que toca:**
- `config/settings.py`

**Done cuando:**
- Request con `Origin: http://localhost:5173` recibe headers CORS correctos
- Configuración JWT coincide exactamente con spec sección 4.1

---

### [x] T-006 — Configurar drf-spectacular (Swagger + ReDoc)

**Descripción:** Configurar `drf-spectacular` para generar el schema OpenAPI. Añadir las rutas `/api/schema/`, `/api/docs/` y `/api/redoc/` en `urls.py`.

**Archivos que toca:**
- `config/settings.py` (SPECTACULAR_SETTINGS)
- `config/urls.py`

**Done cuando:**
- `GET /api/docs/` devuelve la UI de Swagger funcional
- `GET /api/redoc/` devuelve la UI de ReDoc funcional
- `GET /api/schema/` devuelve el YAML de OpenAPI

---

### [x] T-007 — Configurar config/urls.py base

**Descripción:** Registrar todas las rutas de la API en `urls.py` con sus prefijos correctos (ver spec sección 12.1). Las rutas de apps que aún no existen pueden registrarse con `include()` a archivos vacíos para no bloquear el arranque.

**Archivos que toca:**
- `config/urls.py`

**Done cuando:**
- El servidor arranca sin errores de importación
- Las rutas listadas en spec sección 12.1 están registradas

---

## FASE 1 — Core (Infraestructura compartida)

---

### [x] T-008 — Implementar StandardPagination

**Descripción:** Crear `StandardPagination` en `core/pagination.py` con `page_size=20`, `page_size_query_param='limit'`, `max_page_size=100`. Response con `count`, `next`, `previous`, `results`.

**Archivos que toca:**
- `core/pagination.py`
- `config/settings.py` (DEFAULT_PAGINATION_CLASS)

**Done cuando:**
- Un endpoint paginado devuelve exactamente el formato `{count, next, previous, results}`
- `?limit=5&offset=10` funciona correctamente

---

### [x] T-009 — Implementar TenantQuerySetMixin

**Descripción:** Crear `TenantQuerySetMixin` en `core/mixins.py`. El mixin filtra el queryset por `tenant=request.tenant` y asigna `tenant` automáticamente en `perform_create`.

**Archivos que toca:**
- `core/mixins.py`

**Done cuando:**
- Un ViewSet que use el mixin filtra automáticamente por tenant
- `perform_create` asigna `tenant` sin intervención del serializer
- Un usuario de Tenant A no puede ver datos del Tenant B

---

### [x] T-010 — Implementar TenantMiddleware

**Descripción:** Crear `TenantMiddleware` en `core/middleware.py`. El middleware extrae el tenant del `TenantMembership` del usuario autenticado y lo adjunta a `request.tenant`. Omitir en `PUBLIC_PATHS` (ver spec sección 3.2).

**Archivos que toca:**
- `core/middleware.py`
- `config/settings.py` (MIDDLEWARE)

**Done cuando:**
- Un request autenticado tiene `request.tenant` disponible
- Requests a rutas públicas pasan sin error aunque no haya membresía
- Un usuario sin membresía activa en ningún tenant recibe 403

---

### [x] T-011 — Implementar Permission Classes

**Descripción:** Crear las 5 clases de permisos en `core/permissions.py`: `IsAdmin`, `IsAgent`, `IsClient`, `IsAdminOrAgent`, `IsAdminOrReadOnly`. Cada una verifica el rol del usuario en `request.tenant`.

**Archivos que toca:**
- `core/permissions.py`

**Done cuando:**
- `IsAdmin` rechaza con 403 a agent y client
- `IsAgent` rechaza con 403 a admin y client
- `IsClient` rechaza con 403 a admin y agent
- `IsAdminOrAgent` permite a ambos y rechaza a client
- Todos los permisos aceptan al rol correcto del tenant activo

---

### [x] T-012 — Implementar utils.py (helpers compartidos)

**Descripción:** Crear `core/utils.py` con funciones de utilidad que se usarán en múltiples apps: generación de matrícula `CLI-YYYY-NNN`, cálculo de `days_listed`, cálculo de `trend` (vistas últimos 7 días vs anteriores 7).

**Archivos que toca:**
- `core/utils.py`

**Done cuando:**
- `generate_matricula(tenant_id)` retorna un string único en formato `CLI-2026-001`
- `calculate_days_listed(created_at)` retorna el número de días desde la creación
- `calculate_trend(property_id)` retorna `"up"`, `"down"` o `"stable"`

---

## FASE 2 — App: Locations (Catálogos Globales)

---

### [x] T-013 — Crear modelos Country, State, City

**Descripción:** Crear la app `apps/locations` con los modelos `Country`, `State` y `City` según el schema.

**Archivos que toca:**
- `apps/locations/models.py`
- `apps/locations/apps.py`
- `config/settings.py` (INSTALLED_APPS)

**Done cuando:**
- `python manage.py makemigrations locations` genera la migración sin errores
- Los 3 modelos tienen todos los campos del schema

---

### [x] T-014 — Migrations y fixtures iniciales de Locations

**Descripción:** Crear y aplicar migraciones. Crear fixture con datos iniciales: México → Veracruz → ciudades de las Altas Montañas (Orizaba, Córdoba, Fortín, Huatusco, Tehuacán).

**Archivos que toca:**
- `apps/locations/migrations/0001_initial.py`
- `apps/locations/fixtures/locations.json`

**Done cuando:**
- `python manage.py migrate` aplica la migración
- `python manage.py loaddata locations` carga los datos sin errores
- `City.objects.count()` es mayor a 0

---

### [x] T-015 — Serializers y endpoints de catálogos

**Descripción:** Crear serializers para Country, State, City y Amenity. Implementar los endpoints `GET /catalogs/countries`, `GET /catalogs/states?country_id=`, `GET /catalogs/cities?state_id=`, `GET /catalogs/amenities` (ver spec sección 10).

**Archivos que toca:**
- `apps/locations/serializers.py`
- `apps/locations/views.py`
- `apps/locations/urls.py`
- `config/urls.py`

**Done cuando:**
- `GET /api/v1/catalogs/countries` retorna lista de países
- `GET /api/v1/catalogs/states?country_id=1` filtra por país
- `GET /api/v1/catalogs/cities?state_id=1` filtra por estado
- Todos los endpoints son públicos (AllowAny)

---

## FASE 3 — App: Tenants

---

### [x] T-016 — Crear modelo Tenant y fixture inicial

**Descripción:** Crear la app `apps/tenants` con el modelo `Tenant` según el schema. Crear fixture con el tenant inicial: Altas Montañas (`slug: altas-montanas`).

**Archivos que toca:**
- `apps/tenants/models.py`
- `apps/tenants/apps.py`
- `apps/tenants/migrations/0001_initial.py`
- `apps/tenants/fixtures/tenants.json`
- `config/settings.py`

**Done cuando:**
- `python manage.py migrate` aplica la migración
- `Tenant.objects.get(slug='altas-montanas')` funciona después de cargar el fixture
- El modelo tiene todos los campos del schema (incluyendo `city_id`)

---

## FASE 4 — App: Users & Auth

---

### [x] T-017 — Crear modelo User personalizado

**Descripción:** Crear modelo `User` en `apps/users/models.py` extendiendo `AbstractBaseUser`. Campos: `email` (único), `first_name`, `last_name`, `phone`, `avatar`, `city`, `auth_provider`, `is_active`, `is_staff`, `date_joined`, `last_login`. El email es el campo de autenticación (`USERNAME_FIELD = 'email'`).

**Archivos que toca:**
- `apps/users/models.py`
- `apps/users/managers.py`
- `apps/users/apps.py`
- `config/settings.py` (AUTH_USER_MODEL)

**Done cuando:**
- `AUTH_USER_MODEL = 'users.User'` en settings
- `python manage.py createsuperuser` funciona con email como identificador
- El modelo tiene todos los campos del schema incluyendo `auth_provider` enum

---

### [x] T-018 — Crear modelo TenantMembership y AgentProfile

**Descripción:** Crear `TenantMembership` (user + tenant + role + is_active) con índice único `(user_id, tenant_id)`. Crear `AgentProfile` (membership_id + zone + bio + score) como extensión 1:1 de membresía de agente. Crear `UserNotificationPreferences`.

**Archivos que toca:**
- `apps/users/models.py` (TenantMembership, AgentProfile, UserNotificationPreferences)
- `apps/users/migrations/`

**Done cuando:**
- `python manage.py makemigrations` y `migrate` pasan sin errores
- No se pueden crear 2 membresías del mismo user en el mismo tenant (unique constraint)
- `AgentProfile` tiene FK a `TenantMembership` con `unique=True`

---

### T-019 — Configurar JWT y sistema OTP

**Descripción:** Configurar `djangorestframework-simplejwt` según spec (2h access, 7d refresh, rotación). Crear modelo `OTPCode` con campos `email`, `code_hash`, `created_at`, `expires_at` (o usar Django cache). Implementar lógica de generación/hash/validación de OTP de 6 dígitos.

**Archivos que toca:**
- `apps/users/models.py` (OTPCode)
- `apps/users/otp.py` (generate_otp, hash_otp, verify_otp)
- `config/settings.py` (SIMPLE_JWT)

**Done cuando:**
- `generate_otp()` retorna un código de exactamente 6 dígitos
- El código se almacena hasheado (nunca en texto plano)
- El código expira a los 10 minutos
- Rate limit: máximo 5 intentos por email por hora

---

### T-020 — Implementar POST /auth/email/otp

**Descripción:** Endpoint que recibe `email`, crea o recupera el usuario, genera y guarda el OTP hasheado, y envía el email (usar `django.core.mail.send_mail` en dev con consola backend).

**Archivos que toca:**
- `apps/users/views/auth.py`
- `apps/users/serializers/auth.py`
- `apps/users/urls/auth.py`
- `config/settings.py` (EMAIL_BACKEND)

**Done cuando:**
- `POST /api/v1/auth/email/otp` con email válido retorna 200
- El código OTP aparece en la consola (email backend de desarrollo)
- Crear usuario si no existe (`is_active=True`)
- Rate limit activo: el 6to intento en 1h retorna 429

---

### T-021 — Implementar POST /auth/email/verify

**Descripción:** Endpoint que recibe `email` + `token`, valida el OTP contra el hash, elimina el OTP, y retorna JWT (access + refresh) + datos del usuario con sus membresías activas.

**Archivos que toca:**
- `apps/users/views/auth.py`
- `apps/users/serializers/auth.py`

**Done cuando:**
- Código correcto → retorna 200 con `{access, refresh, user: {id, email, memberships[]}}`
- Código incorrecto → retorna 400 `{"error": "Código inválido o expirado"}`
- Código expirado → retorna 400
- El OTP se elimina después de un uso exitoso
- El formato del response coincide exactamente con spec sección 4.2

---

### T-022 — Implementar POST /auth/refresh y POST /auth/logout

**Descripción:** Endpoint `/auth/refresh` usando `TokenRefreshView` de simplejwt. Endpoint `/auth/logout` que blacklistea el refresh token (requerir `TOKEN_BLACKLIST` en `INSTALLED_APPS`).

**Archivos que toca:**
- `apps/users/views/auth.py`
- `apps/users/urls/auth.py`
- `config/settings.py` (TOKEN_BLACKLIST)

**Done cuando:**
- `POST /auth/refresh` con refresh válido retorna nuevo access + refresh
- `POST /auth/logout` con refresh válido retorna 200 y el token queda inválido
- El refresh usado en logout ya no funciona para obtener nuevos tokens

---

### T-023 — Implementar stubs POST /auth/google y POST /auth/apple

**Descripción:** Crear los endpoints para Google y Apple Sign In con la firma correcta pero retornando `{"error": "Not implemented yet"}` con status 501. Esto mantiene la spec completa sin bloquear el desarrollo del resto.

**Archivos que toca:**
- `apps/users/views/auth.py`
- `apps/users/urls/auth.py`

**Done cuando:**
- `POST /auth/google` retorna 501
- `POST /auth/apple` retorna 501
- Los endpoints aparecen en el Swagger con su documentación correcta

---

## FASE 5 — App: Properties

---

### T-024 — Crear modelos de Amenity y fixtures

**Descripción:** Crear modelo `Amenity` en la app `apps/locations` (o crear `apps/properties`). Crear fixture con las 7 amenidades: Alberca, Gimnasio, Seguridad, Elevador, Estacionamiento, Jardín, Roof Garden con sus iconos lucide-react.

**Archivos que toca:**
- `apps/properties/models.py` (Amenity) o `apps/locations/models.py`
- `apps/properties/fixtures/amenities.json`

**Done cuando:**
- `Amenity.objects.count() == 7` después de cargar el fixture
- Cada amenidad tiene `name` e `icon` correctos según spec

---

### T-025 — Crear modelos principales de Properties

**Descripción:** Crear `Property` con todos los campos del schema (incluyendo enums `listing_type`, `property_type`, `property_condition`). Crear `PropertyImage`, `PropertyAmenity` (M2M), `PropertyDocument`, `PropertyNearbyPlace`, `PropertyAssignment`.

**Archivos que toca:**
- `apps/properties/models.py`
- `apps/properties/apps.py`
- `config/settings.py`

**Done cuando:**
- `python manage.py makemigrations properties` genera la migración sin errores
- Todos los modelos tienen los campos del schema
- `PropertyAmenity` tiene índice único `(property_id, amenity_id)`
- `PropertyAssignment` tiene índice único `(property_id, agent_membership_id)`

---

### T-026 — Migrations de Properties

**Descripción:** Crear y aplicar las migraciones de la app properties. Crear fixtures de datos de ejemplo (al menos 5 propiedades para desarrollo).

**Archivos que toca:**
- `apps/properties/migrations/0001_initial.py`
- `apps/properties/fixtures/sample_properties.json`

**Done cuando:**
- `python manage.py migrate` aplica sin errores
- `python manage.py loaddata sample_properties` carga 5+ propiedades de ejemplo

---

### T-027 — Serializers públicos de Properties

**Descripción:** Crear `PublicPropertyListSerializer` (campos del listado) y `PublicPropertyDetailSerializer` (detalle completo). El list serializer debe incluir campos computados: `address` (concatenación), `image` (cover), `days_listed`, `interested` (annotate count). El detail serializer incluye: `images`, `amenities`, `nearby_places`, `agent`, `coordinates`.

**Archivos que toca:**
- `apps/properties/serializers/public.py`

**Done cuando:**
- `PublicPropertyListSerializer` genera exactamente el JSON de spec sección 6 `GET /public/properties`
- `PublicPropertyDetailSerializer` genera exactamente el JSON de spec sección 6 `GET /public/properties/{id}`
- `days_listed` es un `SerializerMethodField` calculado en tiempo real

---

### T-028 — Implementar GET /public/properties (listado con filtros)

**Descripción:** ViewSet o APIView para listar propiedades publicadas. Filtros: `zone`, `type` (property_type), `state` (property_condition), `amenities` (ids), `price_min`, `price_max`, `featured`, `search`. Paginación. Ordenamiento. Solo mostrar `listing_type=sale`, `status=disponible`, `is_active=True`.

**Archivos que toca:**
- `apps/properties/views/public.py`
- `apps/properties/filters.py`
- `apps/properties/urls/public.py`

**Done cuando:**
- `GET /api/v1/public/properties` retorna lista paginada con el formato exacto de la spec
- Todos los filtros funcionan correctamente
- `?featured=true` solo retorna propiedades con `is_featured=True`
- Propiedades inactivas o con otro status NO aparecen

---

### T-029 — Implementar GET /public/properties/{id} (detalle con incremento de views)

**Descripción:** Endpoint de detalle que incrementa `views += 1` en cada request. Retorna detalle completo con imágenes, amenidades, lugares cercanos, datos del agente visible.

**Archivos que toca:**
- `apps/properties/views/public.py`

**Done cuando:**
- `GET /api/v1/public/properties/1` retorna el JSON completo de spec sección 6
- Cada llamada incrementa `property.views` en 1
- El `agent` retornado es el primer agente con `is_visible=True` en `PropertyAssignment`
- `coordinates` es `{lat, lng}` para Google Maps

---

## FASE 6 — App: Appointments

---

### T-030 — Crear modelos de Appointments

**Descripción:** Crear `AppointmentSettings`, `AgentSchedule`, `ScheduleBreak`, `AgentUnavailability`, `Appointment` con todos los campos del schema y enums correspondientes.

**Archivos que toca:**
- `apps/appointments/models.py`
- `apps/appointments/apps.py`
- `config/settings.py`

**Done cuando:**
- `python manage.py makemigrations appointments` genera migración sin errores
- Todos los modelos tienen los campos del schema
- `AppointmentSettings` tiene `unique=True` en `tenant_id`
- `Appointment` tiene `matricula` con `unique=True`

---

### T-031 — Migrations de Appointments y fixture de configuración

**Descripción:** Crear y aplicar migraciones. Crear fixture con `AppointmentSettings` para Altas Montañas (slot_duration=60, max_advance=30, min_advance=24, day_start=09:00, day_end=18:00).

**Archivos que toca:**
- `apps/appointments/migrations/0001_initial.py`
- `apps/appointments/fixtures/appointment_settings.json`

**Done cuando:**
- `python manage.py migrate` aplica sin errores
- `AppointmentSettings.objects.get(tenant__slug='altas-montanas')` funciona

---

### T-032 — Implementar AvailabilityService

**Descripción:** Crear `apps/appointments/services.py` con la clase `AvailabilityService`. Métodos: `get_active_schedule_for_day(agent_membership_id, date)`, `check_unavailability(agent_membership_id, date)`, `get_existing_appointments(agent_membership_id, date)`, `get_available_slots(property_id, date)`. Lógica de la spec sección 9.4.

**Archivos que toca:**
- `apps/appointments/services.py`

**Done cuando:**
- `get_available_slots()` retorna solo slots que respetan: horario activo, breaks, indisponibilidades, citas existentes, `min_advance_hours`
- Slots en el pasado no se incluyen
- Si el agente no tiene horario para ese día, retorna lista vacía
- Si hay una cita de 60min en slot 10:00, el slot 10:00 no está disponible

---

### T-033 — Implementar generación de matrícula CLI-YYYY-NNN

**Descripción:** Función en `core/utils.py` que genera la siguiente matrícula disponible para un tenant. Formato: `CLI-{año}-{NNN}` donde NNN es el consecutivo del año (001, 002, ...). Debe ser thread-safe usando `select_for_update` o un enfoque atómico.

**Archivos que toca:**
- `core/utils.py`

**Done cuando:**
- La primera cita del año retorna `CLI-2026-001`
- La segunda retorna `CLI-2026-002`
- No hay colisiones si 2 citas se crean al mismo tiempo (atomicidad garantizada)

---

### T-034 — Implementar GET /public/appointment/slots

**Descripción:** Endpoint público que recibe `property_id` y `date`, y retorna los slots disponibles del agente asignado a esa propiedad usando `AvailabilityService`.

**Archivos que toca:**
- `apps/appointments/views/public.py`
- `apps/appointments/urls/public.py`

**Done cuando:**
- `GET /api/v1/public/appointment/slots?property_id=1&date=2026-03-15` retorna el JSON de spec sección 6
- Retorna 400 si la propiedad no tiene agente asignado
- Retorna 400 si la fecha es inválida o pasada

---

### T-035 — Implementar POST /public/properties/{id}/appointment

**Descripción:** Endpoint público para agendar una cita. Valida disponibilidad completa, genera matrícula, crea el `Appointment`. Si el usuario está autenticado vincula `client_membership_id`; si no, guarda nombre/email/teléfono.

**Archivos que toca:**
- `apps/appointments/views/public.py`
- `apps/appointments/serializers/public.py`
- `apps/appointments/urls/public.py`

**Done cuando:**
- `POST /api/v1/public/properties/1/appointment` crea la cita y retorna 201 con matrícula
- Retorna 400 si el slot no está disponible
- Retorna 400 si faltan campos obligatorios (nombre, email, teléfono para visitantes)
- La matrícula generada es única y tiene formato `CLI-YYYY-NNN`
- Si el usuario está autenticado, `client_membership_id` se vincula automáticamente

---

## FASE 7 — App: Transactions

---

### T-036 — Crear modelos PurchaseProcess y SaleProcess

**Descripción:** Crear `PurchaseProcess` con todos los campos del schema (incluyendo `sale_price`, `payment_method`, `closed_at`). Crear `SaleProcess`. Crear `ProcessStatusHistory` con `process_type` enum y `process_id` genérico.

**Archivos que toca:**
- `apps/transactions/models.py`
- `apps/transactions/apps.py`
- `config/settings.py`

**Done cuando:**
- `python manage.py makemigrations transactions` genera migración sin errores
- Todos los campos del schema están presentes con los tipos correctos
- Los enums `purchase_status_enum` y `sale_status_enum` tienen los valores exactos del schema

---

### T-037 — Crear modelo SellerLead

**Descripción:** Crear `SellerLead` con todos los campos del schema y el enum `seller_lead_status_enum`.

**Archivos que toca:**
- `apps/transactions/models.py`

**Done cuando:**
- El modelo tiene todos los campos del schema
- `status` tiene los 5 valores del enum (`new`, `contacted`, `in_review`, `converted`, `rejected`)

---

### T-038 — Migrations de Transactions

**Descripción:** Crear y aplicar todas las migraciones de la app transactions.

**Archivos que toca:**
- `apps/transactions/migrations/0001_initial.py`

**Done cuando:**
- `python manage.py migrate` aplica sin errores
- Las tres tablas (`purchase_processes`, `sale_processes`, `seller_leads`, `process_status_history`) existen en la BD

---

### T-039 — Implementar POST /public/seller-leads

**Descripción:** Endpoint público para captar vendedores desde `/vender`. Crea un `SellerLead` con `status=new` vinculado al tenant por defecto (Altas Montañas).

**Archivos que toca:**
- `apps/transactions/views/public.py`
- `apps/transactions/serializers/public.py`
- `apps/transactions/urls/public.py`

**Done cuando:**
- `POST /api/v1/public/seller-leads` crea el lead y retorna 201 con el JSON de spec
- No requiere autenticación
- Todos los campos del request (full_name, email, phone, property_type, etc.) se guardan correctamente

---

## FASE 8 — App: Notifications

---

### T-040 — Crear modelo Notification

**Descripción:** Crear `Notification` con todos los campos del schema: `tenant_id`, `membership_id`, `title`, `message`, `notification_type`, `is_read`, `reference_type`, `reference_id`.

**Archivos que toca:**
- `apps/notifications/models.py`
- `apps/notifications/apps.py`
- `config/settings.py`
- `apps/notifications/migrations/0001_initial.py`

**Done cuando:**
- `python manage.py migrate` aplica sin errores
- El modelo tiene todos los campos del schema

---

## FASE 9 — Admin Panel: Propiedades

---

### T-041 — Serializers admin para Properties

**Descripción:** Crear serializers para el panel admin: `AdminPropertyListSerializer` (con agent, documents_count), `AdminPropertyDetailSerializer` (con images, amenities, nearby_places, documents, assignments), `AdminPropertyCreateUpdateSerializer` (con `amenity_ids`).

**Archivos que toca:**
- `apps/properties/serializers/admin.py`

**Done cuando:**
- Los serializers generan exactamente el JSON de spec secciones 7.1
- `AdminPropertyCreateUpdateSerializer` acepta `amenity_ids` y actualiza `PropertyAmenity`
- `documents_count` es un campo computado

---

### T-042 — Implementar GET y POST /admin/properties

**Descripción:** Lista y creación de propiedades para el admin. Filtros: `search`, `status`, `listing_type`, `property_type`, `agent_id`. Solo propiedades del tenant del admin. Usar `TenantQuerySetMixin`.

**Archivos que toca:**
- `apps/properties/views/admin.py`
- `apps/properties/urls/admin.py`

**Done cuando:**
- `GET /api/v1/admin/properties` retorna lista paginada del tenant correcto
- `POST /api/v1/admin/properties` crea propiedad con `tenant` asignado automáticamente
- Un admin de Tenant A no puede ver propiedades de Tenant B
- Filtros `search`, `status`, `listing_type`, `property_type` funcionan

---

### T-043 — Implementar GET, PATCH, DELETE /admin/properties/{id}

**Descripción:** Detalle, actualización parcial y soft-delete (`is_active=False`) de propiedad individual.

**Archivos que toca:**
- `apps/properties/views/admin.py`

**Done cuando:**
- `GET /api/v1/admin/properties/1` retorna detalle completo (images, amenities, documents, assignments)
- `PATCH /api/v1/admin/properties/1` actualiza solo los campos enviados
- `DELETE /api/v1/admin/properties/1` hace soft delete (`is_active=False`), retorna 204
- Un admin no puede acceder a propiedades de otro tenant

---

### T-044 — Implementar subida y borrado de imágenes de propiedades

**Descripción:** `POST /admin/properties/{id}/images` acepta `multipart/form-data` con uno o varios archivos. Guarda las imágenes en `MEDIA_ROOT` y crea registros `PropertyImage`. `DELETE /admin/properties/{id}/images/{image_id}` elimina la imagen del disco y el registro.

**Archivos que toca:**
- `apps/properties/views/admin.py`
- `apps/properties/serializers/admin.py`

**Done cuando:**
- `POST` con una imagen retorna 201 con `{id, image_url, is_cover, sort_order}`
- El archivo físico existe en `MEDIA_ROOT/properties/{id}/`
- `DELETE` elimina el registro Y el archivo del disco
- Si se marca `is_cover=True`, las demás imágenes quedan como `is_cover=False`

---

### T-045 — Implementar subida de documentos y toggle-featured

**Descripción:** `POST /admin/properties/{id}/documents` acepta `multipart/form-data`. `PATCH /admin/properties/{id}/toggle-featured` invierte el valor de `is_featured`.

**Archivos que toca:**
- `apps/properties/views/admin.py`

**Done cuando:**
- `POST` con un PDF retorna 201 con `{id, name, file_url, mime_type, size_bytes}`
- `PATCH toggle-featured` cambia `is_featured` y retorna el nuevo valor
- Los documentos se guardan en `MEDIA_ROOT/documents/{property_id}/`

---

## FASE 10 — Admin Panel: Agentes

---

### T-046 — Serializers admin para Agents

**Descripción:** Crear `AdminAgentListSerializer` (con stats computados: properties_count, sales_count, leads_count, active_leads), `AdminAgentDetailSerializer` (con horarios), `AdminAgentCreateSerializer`.

**Archivos que toca:**
- `apps/users/serializers/admin.py`

**Done cuando:**
- Los serializers generan exactamente el JSON de spec sección 7.2
- `properties_count` usa `annotate(Count('property_assignments'))`
- `sales_count` cuenta `purchase_processes` con `status=cerrado`

---

### T-047 — Implementar GET y POST /admin/agents

**Descripción:** Listado de agentes del tenant y creación de agente nuevo. Al crear: si el usuario ya existe por email, crear solo `TenantMembership`; si no existe, crear `User` + `TenantMembership` + `AgentProfile`.

**Archivos que toca:**
- `apps/users/views/admin.py`
- `apps/users/urls/admin.py`

**Done cuando:**
- `GET /api/v1/admin/agents` retorna solo agentes del tenant del admin
- `POST` con email existente crea membresía sin duplicar el usuario
- `POST` con email nuevo crea usuario + membresía + agent profile
- El agente creado tiene `role=agent` en su membresía

---

### T-048 — Implementar GET, PATCH, DELETE /admin/agents/{id}

**Descripción:** Detalle del agente con stats, actualización de zona/bio/score, y desactivación (`is_active=False` en la membresía).

**Archivos que toca:**
- `apps/users/views/admin.py`

**Done cuando:**
- `GET` retorna datos del agente + stats computados
- `PATCH` actualiza zone, bio, score en `AgentProfile`
- `DELETE` desactiva la membresía (`is_active=False`), retorna 204
- El agente desactivado no aparece en el listado

---

### T-049 — Implementar CRUD de horarios (/admin/agents/{id}/schedules)

**Descripción:** Listado, creación, actualización y eliminación de `AgentSchedule` con sus `ScheduleBreak` anidados. Al crear/actualizar un horario, los breaks se crean/reemplazan en la misma operación.

**Archivos que toca:**
- `apps/appointments/views/admin.py`
- `apps/appointments/serializers/admin.py`
- `apps/appointments/urls/admin.py`

**Done cuando:**
- `GET /admin/agents/1/schedules` retorna lista de horarios con breaks anidados
- `POST` crea horario con breaks en una operación atómica
- `PATCH` actualiza horario y reemplaza todos los breaks
- `DELETE` elimina el horario y en cascada sus breaks

---

### T-050 — Implementar CRUD de indisponibilidades (/admin/agents/{id}/unavailabilities)

**Descripción:** Listado, creación y eliminación de períodos de indisponibilidad del agente.

**Archivos que toca:**
- `apps/appointments/views/admin.py`
- `apps/appointments/serializers/admin.py`

**Done cuando:**
- `GET` retorna lista de indisponibilidades del agente
- `POST` crea período con validación de fechas (start_date <= end_date)
- `DELETE` elimina el período, retorna 204
- Las indisponibilidades de un agente no afectan los slots de otro agente

---

## FASE 11 — Admin Panel: Citas

---

### T-051 — Serializers y endpoints GET/POST /admin/appointments

**Descripción:** Crear serializers admin para citas. Implementar listado con filtros (`date`, `agent_id`, `status`, `search` por matrícula/nombre) y creación con validación de disponibilidad y generación de matrícula.

**Archivos que toca:**
- `apps/appointments/views/admin.py`
- `apps/appointments/serializers/admin.py`
- `apps/appointments/urls/admin.py`

**Done cuando:**
- `GET /api/v1/admin/appointments` retorna lista con el formato de spec sección 7.3
- `?date=2026-03-15` filtra por fecha
- `POST` valida disponibilidad antes de crear (retorna 400 si slot ocupado)
- `POST` genera matrícula automáticamente

---

### T-052 — Implementar PATCH y DELETE /admin/appointments/{id}

**Descripción:** Actualización de cita (estado, fecha/hora, notas). Al cambiar fecha/hora, re-valida disponibilidad excluyendo la cita actual. Si `status=cancelada`, `cancellation_reason` es obligatorio.

**Archivos que toca:**
- `apps/appointments/views/admin.py`

**Done cuando:**
- `PATCH` con nuevo `status=cancelada` sin `cancellation_reason` retorna 400
- `PATCH` con nueva fecha/hora re-valida disponibilidad
- `DELETE` retorna 204

---

### T-053 — Implementar GET /admin/appointments/availability

**Descripción:** Endpoint que recibe `agent_id` y `date` y retorna slots disponibles usando `AvailabilityService`. Acepta `exclude_appointment_id` para ignorar la cita actual al editar.

**Archivos que toca:**
- `apps/appointments/views/admin.py`

**Done cuando:**
- `GET /admin/appointments/availability?agent_id=3&date=2026-03-15` retorna slots disponibles
- `?exclude_appointment_id=1` excluye esa cita del cálculo de disponibilidad

---

## FASE 12 — Admin Panel: Asignaciones

---

### T-054 — Implementar CRUD /admin/assignments

**Descripción:** Mapa de asignaciones (`GET`), asignar agente a propiedad (`POST`), actualizar visibilidad (`PATCH`), desasignar (`DELETE`).

**Archivos que toca:**
- `apps/properties/views/admin.py`
- `apps/properties/serializers/admin.py`

**Done cuando:**
- `GET /admin/assignments` retorna propiedades sin asignar y mapa de asignaciones con el JSON de spec 7.4
- `POST` crea `PropertyAssignment` (retorna 400 si ya está asignado)
- `PATCH` actualiza `is_visible`
- `DELETE` elimina la asignación, retorna 204

---

## FASE 13 — Admin Panel: Clientes

---

### T-055 — Implementar GET /admin/clients y GET /admin/clients/{id}

**Descripción:** Directorio de clientes del tenant con búsqueda. Detalle con todos sus `purchase_processes` y `sale_processes`.

**Archivos que toca:**
- `apps/users/views/admin.py`
- `apps/users/serializers/admin.py`

**Done cuando:**
- `GET /admin/clients` retorna clientes del tenant con `purchase_processes_count` y `sale_processes_count`
- `?search=juan` filtra por nombre o email
- `GET /admin/clients/5` retorna datos del cliente + lista de purchase y sale processes

---

## FASE 14 — Admin Panel: Pipeline de Compra (Kanban)

---

### T-056 — Implementar GET y POST /admin/purchase-processes

**Descripción:** Listado de procesos de compra (para el Kanban) con filtro por `status` y `agent_id`. Creación manual de proceso de compra con `status=lead`.

**Archivos que toca:**
- `apps/transactions/views/admin.py`
- `apps/transactions/serializers/admin.py`
- `apps/transactions/urls/admin.py`

**Done cuando:**
- `GET /admin/purchase-processes` retorna el JSON de spec sección 7.6
- `?status=visita` filtra por etapa
- `POST` crea proceso con `status=lead` y `overall_progress=0`

---

### T-057 — Implementar PATCH /admin/purchase-processes/{id}/status

**Descripción:** Mover proceso a otra etapa del Kanban. Calcula `overall_progress` según la etapa. Registra el cambio en `ProcessStatusHistory`. Si `status=cerrado`, requerir `sale_price` y `payment_method`.

**Archivos que toca:**
- `apps/transactions/views/admin.py`
- `apps/transactions/services.py`

**Done cuando:**
- `PATCH /admin/purchase-processes/1/status` con `{"status": "visita"}` actualiza a 11%
- Cada cambio crea un registro en `ProcessStatusHistory`
- `status=cerrado` sin `sale_price` retorna 400
- `status=cerrado` guarda `closed_at` con la fecha actual

**Mapa de progreso:**
```
lead=0%, visita=11%, interes=22%, pre_aprobacion=33%,
avaluo=44%, credito=56%, docs_finales=67%, escrituras=78%, cerrado=100%
```

---

### T-058 — Implementar PATCH /admin/purchase-processes/{id}

**Descripción:** Actualización general del proceso (cambiar agente, notas, datos de cierre).

**Archivos que toca:**
- `apps/transactions/views/admin.py`

**Done cuando:**
- `PATCH` actualiza los campos enviados sin afectar los no enviados
- El agente se puede reasignar sin perder el historial

---

## FASE 15 — Admin Panel: Pipeline de Venta

---

### T-059 — Implementar GET y POST /admin/sale-processes

**Descripción:** Listado de procesos de venta con filtros. Creación con `status=contacto_inicial`.

**Archivos que toca:**
- `apps/transactions/views/admin.py`
- `apps/transactions/serializers/admin.py`

**Done cuando:**
- `GET /admin/sale-processes` retorna lista del tenant
- `POST` crea proceso de venta con `status=contacto_inicial`

---

### T-060 — Implementar PATCH /admin/sale-processes/{id}/status

**Descripción:** Mover proceso de venta a otra etapa. Registrar en `ProcessStatusHistory`. Si `status=publicacion`, actualizar `property.listing_type=sale` y `property.status=disponible` en operación atómica.

**Archivos que toca:**
- `apps/transactions/views/admin.py`
- `apps/transactions/services.py`

**Done cuando:**
- Cambio de status registra en `ProcessStatusHistory`
- `status=publicacion` actualiza la propiedad (listing_type y status) en la misma transacción
- Si la actualización de propiedad falla, el status no cambia (atomicidad)

---

## FASE 16 — Admin Panel: Seller Leads

---

### T-061 — Implementar GET, GET/{id} y PATCH /admin/seller-leads

**Descripción:** Listado con filtros, detalle y actualización de seller leads (cambiar status, asignar agente, agregar notas).

**Archivos que toca:**
- `apps/transactions/views/admin.py`
- `apps/transactions/serializers/admin.py`

**Done cuando:**
- `GET /admin/seller-leads` retorna lista con filtro por `status`
- `GET /admin/seller-leads/1` retorna el lead completo
- `PATCH` actualiza status y agente asignado

---

### T-062 — Implementar POST /admin/seller-leads/{id}/convert

**Descripción:** Convertir seller lead en propiedad + sale_process en una transacción atómica. Flujo: crear/encontrar usuario client → crear Property (pending_listing/documentacion) → crear SaleProcess (contacto_inicial) → actualizar lead a `converted`.

**Archivos que toca:**
- `apps/transactions/views/admin.py`
- `apps/transactions/services.py`

**Done cuando:**
- La conversión es atómica: si algo falla, todo hace rollback
- Retorna `{property_id, sale_process_id, message}` con 201
- El `seller_lead.status` queda en `converted`
- Si el email del lead ya pertenece a un usuario, se reutiliza ese usuario
- Si el usuario no existe, se crea con role=client en el tenant

---

## FASE 17 — Admin Panel: Historial e Insights

---

### T-063 — Implementar GET /admin/history

**Descripción:** Listado de ventas completadas (`purchase_processes` con `status=cerrado`). Filtros: `zone`, `property_type`, `payment_method`, `search`, `date_from`, `date_to`. Paginado.

**Archivos que toca:**
- `apps/transactions/views/admin.py`
- `apps/transactions/serializers/admin.py`

**Done cuando:**
- Solo retorna procesos con `status=cerrado`
- Todos los filtros funcionan
- El JSON coincide con spec sección 7.9

---

### T-064 — Implementar GET /admin/insights

**Descripción:** Analytics del tenant. Calcular con queries de agregación: `sales_by_month`, `distribution_by_type`, `activity_by_zone`, `top_agents`, `summary`. Filtrar por `period` (month, quarter, year, all).

**Archivos que toca:**
- `apps/transactions/views/admin.py`
- `apps/transactions/services.py`

**Done cuando:**
- `GET /admin/insights?period=month` retorna datos del mes actual
- `sales_by_month` usa `annotate` + `TruncMonth`
- `distribution_by_type` usa `values('property_type').annotate(count=Count('id'))`
- `top_agents` ordena por `sales_count` descendente

---

## FASE 18 — Panel del Agente

---

### T-065 — Implementar GET /agent/dashboard

**Descripción:** Stats del agente autenticado: `active_leads` (purchase_processes activos), `today_appointments` (citas del día), `month_sales` (cerrado en el mes).

**Archivos que toca:**
- `apps/users/views/agent.py`
- `apps/users/serializers/agent.py`
- `apps/users/urls/agent.py`

**Done cuando:**
- Retorna exactamente el JSON de spec sección 8
- Los stats son calculados para el agente autenticado (no de otros agentes)

---

### T-066 — Implementar GET /agent/properties y /agent/properties/{id}/leads

**Descripción:** Propiedades asignadas al agente con `leads_count`. Leads (purchase_processes) de una propiedad específica.

**Archivos que toca:**
- `apps/properties/views/agent.py`
- `apps/properties/urls/agent.py`

**Done cuando:**
- `GET /agent/properties` retorna solo las propiedades asignadas al agente autenticado
- `leads_count` cuenta `purchase_processes` de esa propiedad
- `GET /agent/properties/1/leads` retorna los prospectos de esa propiedad

---

### T-067 — Implementar GET /agent/appointments y PATCH /agent/appointments/{id}/status

**Descripción:** Citas del agente con filtros. Actualización de estado con validación de transiciones válidas (programada → confirmada → en_progreso → completada | cancelada | no_show | reagendada).

**Archivos que toca:**
- `apps/appointments/views/agent.py`
- `apps/appointments/urls/agent.py`

**Done cuando:**
- `GET /agent/appointments` retorna solo las citas del agente autenticado
- `PATCH` con transición inválida (ej: completada → programada) retorna 400
- `PATCH` con transición válida actualiza el estado

---

## FASE 19 — Panel del Cliente

---

### T-068 — Implementar GET /client/dashboard

**Descripción:** Resumen del cliente con actividad reciente, preview de ventas y compras.

**Archivos que toca:**
- `apps/users/views/client.py`
- `apps/users/serializers/client.py`
- `apps/users/urls/client.py`

**Done cuando:**
- Retorna exactamente el JSON de spec sección 9
- `recent_activity` viene de `ProcessStatusHistory` del cliente
- `credit_score` es `null` por ahora (pendiente)

---

### T-069 — Implementar GET /client/sales y GET /client/sales/{process_id}

**Descripción:** Procesos de venta del cliente con stats globales (vistas totales, interesados, valor). Detalle con timeline de etapas completo e historial de cambios.

**Archivos que toca:**
- `apps/transactions/views/client.py`
- `apps/transactions/serializers/client.py`
- `apps/transactions/urls/client.py`

**Done cuando:**
- `GET /client/sales` incluye stats y la lista de procesos con `trend`, `days_listed`, `interested`
- `GET /client/sales/1` incluye `stages` con status completed/current/pending e historial
- Solo muestra los procesos del cliente autenticado

---

### T-070 — Implementar GET /client/purchases y GET /client/purchases/{process_id}

**Descripción:** Procesos de compra del cliente. Detalle con `steps` (timeline de 9 etapas con `allow_upload`) y documentos subidos.

**Archivos que toca:**
- `apps/transactions/views/client.py`
- `apps/transactions/serializers/client.py`

**Done cuando:**
- `GET /client/purchases/1` retorna `steps` con exactamente el JSON de spec sección 9
- `allow_upload` es `true` en etapas: `pre_aprobacion`, `credito`, `docs_finales`
- `documents` lista los archivos subidos en ese proceso

---

### T-071 — Implementar POST /client/purchases/{process_id}/documents

**Descripción:** Subida de documento por el cliente en etapas permitidas (`allow_upload=True`). Valida que la etapa actual del proceso permita carga antes de aceptar el archivo.

**Archivos que toca:**
- `apps/transactions/views/client.py`

**Done cuando:**
- `POST` en etapa que permite upload crea `PropertyDocument` con el `purchase_process_id`
- `POST` en etapa que NO permite upload retorna 403
- El archivo se guarda en `MEDIA_ROOT/documents/purchases/{process_id}/`
- Retorna `{id, name, file_url, mime_type, size_bytes, document_stage}`

---

### T-072 — Implementar GET y PATCH /client/profile

**Descripción:** Ver y editar perfil del cliente (first_name, last_name, phone, city). El email NO es editable.

**Archivos que toca:**
- `apps/users/views/client.py`
- `apps/users/serializers/client.py`

**Done cuando:**
- `GET /client/profile` retorna los datos del usuario autenticado
- `PATCH` con `email` en el body ignora el email o retorna error
- `PATCH` actualiza solo los campos enviados

---

### T-073 — Implementar GET y PUT /client/notification-preferences

**Descripción:** Leer y actualizar las preferencias de notificación del cliente. Crear el registro si no existe (usar `get_or_create`).

**Archivos que toca:**
- `apps/users/views/client.py`
- `apps/users/serializers/client.py`

**Done cuando:**
- `GET` retorna las 4 preferencias (new_properties, price_updates, appointment_reminders, offers)
- `PUT` actualiza todas las preferencias en una operación
- Si el registro no existe, `GET` lo crea con todos los defaults en `True`

---

## FASE 20 — Notificaciones

---

### T-074 — Implementar endpoints de notificaciones

**Descripción:** Endpoints compartidos entre roles: `GET /notifications` (con `is_read` filter y `unread_count`), `PATCH /notifications/{id}/read`, `POST /notifications/read-all`. Solo el dueño de la notificación puede verla/actualizarla.

**Archivos que toca:**
- `apps/notifications/views.py`
- `apps/notifications/serializers.py`
- `apps/notifications/urls.py`

**Done cuando:**
- `GET /notifications` retorna las notificaciones del usuario autenticado en el tenant actual con `unread_count`
- `PATCH /notifications/1/read` marca como leída y retorna `{is_read: true}`
- `POST /notifications/read-all` marca todas como leídas y retorna `{marked_as_read: N}`
- Un usuario no puede ver notificaciones de otro usuario

---

## FASE 21 — Tests

---

### T-075 — Tests de autenticación

**Descripción:** Suite de tests para el flujo completo de OTP: envío, verificación correcta, verificación incorrecta, expiración, rate limit. Tests de refresh y logout.

**Archivos que toca:**
- `apps/users/tests/test_auth.py`

**Done cuando:**
- `python manage.py test apps.users.tests.test_auth` pasa al 100%
- Test: OTP correcto → JWT válido
- Test: OTP incorrecto → 400
- Test: OTP expirado → 400
- Test: 6to intento en 1h → 429
- Test: logout → refresh invalido

---

### T-076 — Tests de aislamiento multi-tenant

**Descripción:** Tests que verifican que ningún usuario puede acceder a datos de otro tenant. Crear 2 tenants, 2 admins, y verificar que cada uno solo ve sus datos.

**Archivos que toca:**
- `core/tests/test_tenant_isolation.py`

**Done cuando:**
- Admin de Tenant A no puede ver propiedades de Tenant B
- Admin de Tenant A no puede modificar agentes de Tenant B
- Todos los ViewSets con `TenantQuerySetMixin` están cubiertos

---

### T-077 — Tests de endpoints públicos

**Descripción:** Tests para `GET /public/properties`, `GET /public/properties/{id}`, slots de disponibilidad, agendado de citas, seller leads.

**Archivos que toca:**
- `apps/properties/tests/test_public.py`
- `apps/appointments/tests/test_public.py`
- `apps/transactions/tests/test_public.py`

**Done cuando:**
- `python manage.py test` pasa todos los tests públicos
- Test: filtros de propiedades funcionan correctamente
- Test: `views` se incrementa en +1 al ver detalle
- Test: agendar cita valida disponibilidad
- Test: slot ocupado retorna 400

---

### T-078 — Tests de la matriz de permisos

**Descripción:** Tests que verifican que cada endpoint rechaza los roles incorrectos con 403 y acepta los correctos.

**Archivos que toca:**
- `core/tests/test_permissions.py`

**Done cuando:**
- Un cliente intentando `GET /admin/properties` recibe 403
- Un agente intentando `PATCH /admin/purchase-processes/{id}/status` recibe 403
- Un visitante no autenticado intentando `GET /admin/agents` recibe 401
- La matriz completa de spec sección 5.2 está cubierta

---

### T-079 — Tests del AvailabilityService

**Descripción:** Tests unitarios del servicio de disponibilidad. Cubrir todos los casos: sin horario, break, indisponibilidad, cita existente, hora pasada, `min_advance_hours`.

**Archivos que toca:**
- `apps/appointments/tests/test_availability.py`

**Done cuando:**
- Test: agente sin horario → slots vacíos
- Test: agente con break 14-15h → slot 14:00 no disponible
- Test: agente con indisponibilidad → todos los slots vacíos
- Test: cita de 60min en 10:00 → slot 10:00 no disponible
- Test: slot a menos de 24h del momento actual → excluido

---

### T-080 — Tests del pipeline de compra

**Descripción:** Tests de cambio de estado en el Kanban: progreso correcto, registro en historial, validaciones al cerrar.

**Archivos que toca:**
- `apps/transactions/tests/test_purchase_pipeline.py`

**Done cuando:**
- Test: cambio a `visita` → `overall_progress=11`, registro en historial
- Test: cambio a `cerrado` sin `sale_price` → 400
- Test: cambio a `cerrado` con datos completos → `closed_at` se llena
- Test: historial tiene `previous_status` y `new_status` correctos

---

### T-081 — Tests del pipeline de venta y seller leads

**Descripción:** Tests de conversión de seller lead, pipeline de venta, y el side effect de pasar a `publicacion`.

**Archivos que toca:**
- `apps/transactions/tests/test_sale_pipeline.py`

**Done cuando:**
- Test: conversión de lead crea Property + SaleProcess en una transacción
- Test: si la conversión falla, nada se crea (rollback)
- Test: `status=publicacion` actualiza la propiedad a `listing_type=sale, status=disponible`

---

### T-082 — Tests del panel del agente

**Descripción:** Tests de los endpoints del agente: solo ve sus propiedades asignadas, solo puede actualizar sus citas, transiciones válidas e inválidas.

**Archivos que toca:**
- `apps/users/tests/test_agent_panel.py`
- `apps/appointments/tests/test_agent_panel.py`

**Done cuando:**
- Test: agente solo ve propiedades asignadas a él
- Test: transición inválida de cita retorna 400
- Test: agente no puede ver citas de otro agente

---

### T-083 — Tests del panel del cliente

**Descripción:** Tests de subida de documentos en etapas correctas/incorrectas, actualización de perfil, preferencias de notificación.

**Archivos que toca:**
- `apps/transactions/tests/test_client_panel.py`
- `apps/users/tests/test_client_panel.py`

**Done cuando:**
- Test: cliente puede subir documento en `pre_aprobacion` (allow_upload=True)
- Test: cliente no puede subir documento en `lead` (allow_upload=False) → 403
- Test: `PATCH /client/profile` con email retorna el email original sin cambios

---

### T-084 — Tests de notificaciones

**Descripción:** Tests de visibilidad de notificaciones por usuario, marcado como leída, read-all.

**Archivos que toca:**
- `apps/notifications/tests/test_notifications.py`

**Done cuando:**
- Test: usuario A no puede ver notificaciones de usuario B → 404
- Test: `read-all` solo marca las notificaciones del usuario autenticado
- Test: `unread_count` decrece al marcar como leídas

---

## FASE 22 — Auditoría de Seguridad

---

### T-085 — Verificar tenant isolation en todos los ViewSets

**Descripción:** Revisar que CADA ViewSet que maneja datos con `tenant_id` usa `TenantQuerySetMixin` o filtra explícitamente por `request.tenant`. Ningún endpoint debe poder retornar datos de otro tenant.

**Archivos que toca:**
- Revisión de todos los `views/admin.py`, `views/agent.py`, `views/client.py`

**Done cuando:**
- Lista documentada de todos los ViewSets y confirmación de que cada uno filtra por tenant
- Ningún test de aislamiento (T-076) falla

---

### T-086 — Verificar permission classes en todos los endpoints

**Descripción:** Revisar que cada endpoint tiene el decorador de permiso correcto según la matriz de spec sección 5.2. Ningún endpoint debe quedar con `AllowAny` excepto los marcados como públicos.

**Archivos que toca:**
- Revisión de todos los archivos de views

**Done cuando:**
- Lista documentada de todos los endpoints con su permission class
- Los tests de permisos (T-078) pasan al 100%

---

### T-087 — Verificar inputs de archivos (mime types y tamaño)

**Descripción:** Todos los endpoints que aceptan archivos deben validar: mime types permitidos (imágenes: jpg/png/webp; documentos: pdf/jpg/png), tamaño máximo (imágenes: 10MB, documentos: 20MB). Rechazar con 400 si no cumple.

**Archivos que toca:**
- `apps/properties/serializers/admin.py` (imágenes y documentos)
- `apps/transactions/serializers/client.py` (documentos de compra)
- `core/validators.py` (validators reutilizables)

**Done cuando:**
- Subir un `.exe` retorna 400 con mensaje de error claro
- Subir un archivo mayor al límite retorna 400

---

### T-088 — Verificar rate limiting en auth y endpoints sensibles

**Descripción:** Confirmar que el rate limit de OTP (5 por hora) está activo y funcionando. Considerar añadir rate limiting a endpoints de creación públicos (`POST /public/seller-leads`).

**Archivos que toca:**
- `apps/users/views/auth.py`
- `core/throttling.py` (si se crea una clase custom)

**Done cuando:**
- El 6to intento de OTP en 1h retorna 429
- El rate limit se resetea correctamente tras el período

---

### T-089 — Revisión final y checklist de seguridad

**Descripción:** Revisión general siguiendo el checklist de OWASP Top 10: SQL injection (ORM previene, verificar raw queries si hay), XSS (DRF serializa correctamente), IDOR (verificar que IDs de otros tenants dan 404, no 403), sensitive data exposure (tokens JWT no en logs), CORS configurado correctamente.

**Archivos que toca:**
- `config/settings.py` (DEBUG=False en producción, ALLOWED_HOSTS, SECRET_KEY)
- Revisión general de todos los views

**Done cuando:**
- No hay queries raw SQL sin parametrizar
- `DEBUG=False` en `.env.example` de producción
- `ALLOWED_HOSTS` no es `['*']` en producción
- `SECRET_KEY` no está hardcodeada
- Los tokens JWT no aparecen en logs de Django

---

## Resumen de Fases

| Fase | Tasks | Descripción |
|---|---|---|
| 0 | T-001 → T-007 | Setup del proyecto |
| 1 | T-008 → T-012 | Core (middleware, permisos, mixins) |
| 2 | T-013 → T-015 | App Locations |
| 3 | T-016 | App Tenants |
| 4 | T-017 → T-023 | App Users & Auth |
| 5 | T-024 → T-029 | App Properties (modelos + endpoints públicos) |
| 6 | T-030 → T-035 | App Appointments |
| 7 | T-036 → T-039 | App Transactions (modelos + seller leads públicos) |
| 8 | T-040 | App Notifications (modelos) |
| 9 | T-041 → T-045 | Admin: Propiedades |
| 10 | T-046 → T-050 | Admin: Agentes |
| 11 | T-051 → T-053 | Admin: Citas |
| 12 | T-054 | Admin: Asignaciones |
| 13 | T-055 | Admin: Clientes |
| 14 | T-056 → T-058 | Admin: Pipeline Compra (Kanban) |
| 15 | T-059 → T-060 | Admin: Pipeline Venta |
| 16 | T-061 → T-062 | Admin: Seller Leads |
| 17 | T-063 → T-064 | Admin: Historial e Insights |
| 18 | T-065 → T-067 | Panel Agente |
| 19 | T-068 → T-073 | Panel Cliente |
| 20 | T-074 | Notificaciones |
| 21 | T-075 → T-084 | Tests |
| 22 | T-085 → T-089 | Auditoría de Seguridad |

**Total: 89 tasks**
