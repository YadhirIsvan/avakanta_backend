# Technical Spec — Avakanta API

> Versión: 1.0
> Fecha: 2026-02-27
> Base URL: `/api/v1`
> Auth: JWT Bearer Token (django-rest-framework-simplejwt)
> Docs: PRD → `docs/prd.md` | Schema → `docs/schema.dbml`

---

## 1. Stack Tecnológico

| Componente | Tecnología |
|---|---|
| Framework | Django 5.1 |
| API | Django REST Framework 3.15 |
| Base de datos | PostgreSQL |
| Auth | djangorestframework-simplejwt (JWT) |
| Documentación API | drf-spectacular (OpenAPI 3.0 + Swagger UI + ReDoc) |
| Filtros | django-filter |
| CORS | django-cors-headers |
| Archivos | Pillow (imágenes) + multipart/form-data |

---

## 2. Arquitectura del Proyecto

```
avakanta/
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/
│   ├── middleware.py        # TenantMiddleware
│   ├── permissions.py       # Permission classes por rol
│   ├── pagination.py        # StandardPagination
│   ├── mixins.py            # TenantQuerySetMixin
│   └── utils.py             # Helpers compartidos
├── apps/
│   ├── tenants/
│   ├── users/
│   ├── locations/
│   ├── properties/
│   ├── appointments/
│   ├── transactions/        # purchase_processes, sale_processes, seller_leads
│   └── notifications/
├── docs/
│   ├── prd.md
│   ├── spec.md
│   ├── tasks.md
│   └── schema.dbml
├── CLAUDE.md
├── manage.py
└── requirements.txt
```

---

## 3. Multi-Tenancy

### 3.1 Estrategia
Shared database con columna discriminadora (`tenant_id`).

### 3.2 TenantMiddleware
- Se ejecuta en cada request autenticado.
- Extrae el `tenant_id` del `TenantMembership` del usuario autenticado.
- Lo adjunta a `request.tenant`.
- Si el usuario no tiene membresía activa → 403.

```python
# core/middleware.py
class TenantMiddleware:
    """
    Extrae el tenant del usuario autenticado y lo adjunta al request.
    Se salta en rutas públicas (auth, propiedades públicas).
    """
    PUBLIC_PATHS = [
        '/api/v1/auth/',
        '/api/v1/public/',
        '/api/schema/',
        '/api/docs/',
        '/api/redoc/',
    ]
```

### 3.3 TenantQuerySetMixin
Mixin para ViewSets que filtra automáticamente por `tenant_id`.

```python
# core/mixins.py
class TenantQuerySetMixin:
    """
    Filtra el queryset por request.tenant automáticamente.
    Asigna tenant_id en create automáticamente.
    """
    def get_queryset(self):
        return super().get_queryset().filter(tenant=self.request.tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)
```

---

## 4. Autenticación

### 4.1 Configuración JWT

```python
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=2),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}
```

### 4.2 Endpoints de Auth

Base: `/api/v1/auth`

---

#### `POST /auth/email/otp`

Envía código OTP de 6 dígitos al email.

**Permisos:** Público (AllowAny)

**Request:**
```json
{
  "email": "usuario@ejemplo.com"
}
```

**Response 200:**
```json
{
  "message": "OTP enviado al email",
  "email": "usuario@ejemplo.com"
}
```

**Response 429:**
```json
{
  "error": "Demasiados intentos. Intenta en 60 segundos."
}
```

**Reglas:**
- Generar código aleatorio de 6 dígitos
- Guardar hash del código con expiración de 10 minutos
- Rate limit: máximo 5 intentos por email por hora
- Si el usuario no existe, se crea automáticamente con `is_active=true`

---

#### `POST /auth/email/verify`

Verifica el código OTP y retorna tokens JWT.

**Permisos:** Público (AllowAny)

**Request:**
```json
{
  "email": "usuario@ejemplo.com",
  "token": "123456"
}
```

**Response 200:**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "user": {
    "id": 1,
    "email": "usuario@ejemplo.com",
    "first_name": "Juan",
    "last_name": "Pérez",
    "memberships": [
      {
        "id": 1,
        "tenant_id": 1,
        "tenant_name": "Altas Montañas",
        "tenant_slug": "altas-montanas",
        "role": "client"
      }
    ]
  }
}
```

**Response 400:**
```json
{
  "error": "Código inválido o expirado"
}
```

**Reglas:**
- Validar código contra hash almacenado
- Si el código es correcto, eliminar el OTP
- Si el usuario no tiene membresía en ningún tenant, crear una como `client` en el tenant default
- Retornar todas las membresías activas del usuario

---

#### `POST /auth/google`

Login con Google Identity.

**Permisos:** Público (AllowAny)

**Request:**
```json
{
  "idToken": "eyJ..."
}
```

**Response 200:** Mismo formato que `/auth/email/verify`

**Reglas:**
- Verificar idToken con Google API
- Extraer email del token
- Si usuario no existe → crear con `auth_provider=google`
- Retornar JWT + datos de usuario

---

#### `POST /auth/apple`

Login con Apple Sign In.

**Permisos:** Público (AllowAny)

**Request:**
```json
{
  "identityToken": "eyJ..."
}
```

**Response 200:** Mismo formato que `/auth/email/verify`

---

#### `POST /auth/refresh`

Renueva el access token.

**Permisos:** Público (AllowAny)

**Request:**
```json
{
  "refresh": "eyJ..."
}
```

**Response 200:**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

---

#### `POST /auth/logout`

Invalida el refresh token.

**Permisos:** IsAuthenticated

**Request:**
```json
{
  "refresh": "eyJ..."
}
```

**Response 200:**
```json
{
  "message": "Sesión cerrada"
}
```

---

## 5. Permisos

### 5.1 Permission Classes

```python
# core/permissions.py

class IsAdmin(BasePermission):
    """Solo admin del tenant actual."""

class IsAgent(BasePermission):
    """Solo agente del tenant actual."""

class IsClient(BasePermission):
    """Solo cliente del tenant actual."""

class IsAdminOrAgent(BasePermission):
    """Admin o agente del tenant actual."""

class IsAdminOrReadOnly(BasePermission):
    """Admin puede todo, otros solo lectura."""
```

### 5.2 Matriz de permisos por endpoint

| Recurso | Admin | Agent | Client | Público |
|---|---|---|---|---|
| Propiedades públicas (listar/detalle) | ✅ | ✅ | ✅ | ✅ |
| CRUD propiedades (admin) | ✅ | ❌ | ❌ | ❌ |
| Asignar agentes a propiedades | ✅ | ❌ | ❌ | ❌ |
| CRUD agentes | ✅ | ❌ | ❌ | ❌ |
| Gestión de horarios | ✅ | ❌ | ❌ | ❌ |
| Citas (admin - todas) | ✅ | ❌ | ❌ | ❌ |
| Citas (agente - propias) | ❌ | ✅ | ❌ | ❌ |
| Agendar cita (desde detalle propiedad) | ✅ | ✅ | ✅ | ✅ |
| Ver clientes y pipelines | ✅ | ❌ | ❌ | ❌ |
| Mover pipeline (Kanban) | ✅ | ❌ | ❌ | ❌ |
| Propiedades del agente | ❌ | ✅ | ❌ | ❌ |
| Leads del agente | ❌ | ✅ | ❌ | ❌ |
| Mis compras/ventas | ❌ | ❌ | ✅ | ❌ |
| Subir documentos (cliente) | ❌ | ❌ | ✅ | ❌ |
| Perfil de usuario | ❌ | ❌ | ✅ | ❌ |
| Seller leads (crear) | ✅ | ✅ | ✅ | ✅ |
| Seller leads (gestionar) | ✅ | ❌ | ❌ | ❌ |
| Historial de ventas | ✅ | ❌ | ❌ | ❌ |
| Insights / Analytics | ✅ | ❌ | ❌ | ❌ |
| Notificaciones | ✅ | ✅ | ✅ | ❌ |

---

## 6. Endpoints — Públicos

Base: `/api/v1/public`

---

#### `GET /public/properties`

Listado de propiedades publicadas (para `/comprar` y home).

**Permisos:** Público (AllowAny)

**Query Params:**
| Param | Tipo | Descripción |
|---|---|---|
| `zone` | string | Filtro por zona (Norte, Sur, Centro, Oriente, Poniente) |
| `type` | string | Filtro por property_type (house, apartment, land, commercial) |
| `state` | string | Filtro por property_condition (new, semi_new, used) |
| `amenities` | string[] | Filtro por amenidades (ids) |
| `price_min` | decimal | Precio mínimo |
| `price_max` | decimal | Precio máximo |
| `featured` | boolean | Solo propiedades destacadas (para home) |
| `search` | string | Búsqueda por título o dirección |
| `limit` | int | Paginación (default: 20) |
| `offset` | int | Paginación (default: 0) |
| `ordering` | string | Ordenar por: price, -price, created_at, -created_at |

**Response 200:**
```json
{
  "count": 150,
  "next": "/api/v1/public/properties?limit=20&offset=20",
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Casa en Bosques de Orizaba",
      "address": "Calle Pino 45, Col. Bosques, Orizaba",
      "price": "2500000.00",
      "currency": "MXN",
      "property_type": "house",
      "property_condition": "semi_new",
      "bedrooms": 3,
      "bathrooms": 2,
      "construction_sqm": "180.00",
      "zone": "Norte",
      "image": "https://storage.example.com/props/1/cover.jpg",
      "is_verified": true,
      "is_featured": false,
      "days_listed": 15,
      "interested": 4,
      "views": 230
    }
  ]
}
```

**Reglas:**
- Solo mostrar propiedades con `listing_type=sale`, `status=disponible`, `is_active=true`
- `image` = la imagen de `property_images` donde `is_cover=true`
- `days_listed` = `today - created_at` (calculado en serializer)
- `interested` = count de `purchase_processes` de esa propiedad (calculado con annotate)
- `address` = concatenación de campos de dirección

---

#### `GET /public/properties/{id}`

Detalle completo de una propiedad.

**Permisos:** Público (AllowAny)

**Response 200:**
```json
{
  "id": 1,
  "title": "Casa en Bosques de Orizaba",
  "description": "Hermosa casa de 3 recámaras...",
  "price": "2500000.00",
  "currency": "MXN",
  "property_type": "house",
  "property_condition": "semi_new",
  "status": "disponible",
  "bedrooms": 3,
  "bathrooms": 2,
  "parking_spaces": 2,
  "construction_sqm": "180.00",
  "land_sqm": "250.00",
  "address": "Calle Pino 45, Col. Bosques, Orizaba, Ver.",
  "zone": "Norte",
  "latitude": "18.8500000",
  "longitude": "-97.1000000",
  "is_verified": true,
  "views": 231,
  "days_listed": 15,
  "interested": 4,
  "images": [
    {
      "id": 1,
      "image_url": "https://storage.example.com/props/1/img1.jpg",
      "is_cover": true,
      "sort_order": 0
    }
  ],
  "amenities": [
    { "id": 1, "name": "Alberca", "icon": "waves" },
    { "id": 5, "name": "Estacionamiento", "icon": "car" }
  ],
  "nearby_places": [
    { "name": "Hospital Regional", "place_type": "hospital", "distance_km": "1.20" },
    { "name": "Plaza Orizaba", "place_type": "supermercado", "distance_km": "0.50" }
  ],
  "video_id": "dQw4w9WgXcQ",
  "video_thumbnail": "https://img.youtube.com/vi/dQw4w9WgXcQ/0.jpg",
  "agent": {
    "name": "Alejandro Torres",
    "photo": "https://storage.example.com/agents/1/photo.jpg",
    "phone": "+52 272 123 4567",
    "email": "alejandro@altasmontanas.com"
  },
  "coordinates": {
    "lat": 18.85,
    "lng": -97.10
  }
}
```

**Reglas:**
- Incrementar `views` en +1 cada vez que se consulta este endpoint
- `agent` = el primer agente asignado con `is_visible=true`
- `coordinates` = objeto con lat/lng para el embed de Google Maps

---

#### `POST /public/properties/{id}/appointment`

Agendar cita desde detalle de propiedad (visitante o usuario autenticado).

**Permisos:** Público (AllowAny)

**Request:**
```json
{
  "date": "2026-03-15",
  "time": "10:00",
  "name": "María García",
  "phone": "+52 272 987 6543",
  "email": "maria@gmail.com"
}
```

**Response 201:**
```json
{
  "id": 1,
  "matricula": "CLI-2026-001",
  "scheduled_date": "2026-03-15",
  "scheduled_time": "10:00:00",
  "duration_minutes": 60,
  "status": "programada",
  "property": {
    "id": 1,
    "title": "Casa en Bosques de Orizaba"
  },
  "agent": {
    "name": "Alejandro Torres"
  }
}
```

**Response 400:**
```json
{
  "error": "El agente no tiene disponibilidad en ese horario"
}
```

**Reglas:**
- El agente se asigna automáticamente (el primer agente con `is_visible=true` asignado a la propiedad)
- Validar disponibilidad completa (schedule activo, hora en rango, sin breaks, sin indisponibilidad, sin solapamiento)
- Generar matrícula `CLI-{año}-{consecutivo}` automáticamente
- `duration_minutes` se toma de `appointment_settings.slot_duration_minutes`
- Si el usuario está autenticado, vincular `client_membership_id`
- Si no está autenticado, guardar `client_name`, `client_email`, `client_phone`

---

#### `POST /public/seller-leads`

Crear seller lead desde formulario de `/vender`.

**Permisos:** Público (AllowAny)

**Request:**
```json
{
  "full_name": "Roberto Méndez",
  "email": "roberto@gmail.com",
  "phone": "+52 272 111 2222",
  "property_type": "house",
  "location": "Orizaba, Veracruz",
  "square_meters": 200.00,
  "bedrooms": 3,
  "bathrooms": 2,
  "expected_price": 3000000.00
}
```

**Response 201:**
```json
{
  "id": 1,
  "full_name": "Roberto Méndez",
  "status": "new",
  "message": "Tu solicitud ha sido recibida. Te contactaremos pronto."
}
```

**Reglas:**
- Se crea con `status=new` y `tenant_id` del tenant default (Altas Montañas)
- No requiere autenticación

---

#### `GET /public/appointment/slots`

Consultar slots disponibles de un agente para una fecha.

**Permisos:** Público (AllowAny)

**Query Params:**
| Param | Tipo | Descripción |
|---|---|---|
| `property_id` | int | ID de la propiedad |
| `date` | date | Fecha deseada (YYYY-MM-DD) |

**Response 200:**
```json
{
  "date": "2026-03-15",
  "agent": {
    "name": "Alejandro Torres"
  },
  "available_slots": ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"],
  "slot_duration_minutes": 60
}
```

**Reglas:**
- Calcular slots disponibles según: horario del agente, breaks, indisponibilidades, citas existentes
- No mostrar slots en el pasado
- Respetar `min_advance_hours` del `appointment_settings`

---

## 7. Endpoints — Admin

Base: `/api/v1/admin`

Todos los endpoints de esta sección requieren `IsAdmin`.

---

### 7.1 Propiedades

#### `GET /admin/properties`

Listado de propiedades del tenant.

**Query Params:** `search`, `status`, `listing_type`, `property_type`, `agent_id`, `limit`, `offset`

**Response 200:**
```json
{
  "count": 25,
  "results": [
    {
      "id": 1,
      "title": "Casa en Bosques de Orizaba",
      "address": "Calle Pino 45, Col. Bosques, Orizaba",
      "price": "2500000.00",
      "currency": "MXN",
      "property_type": "house",
      "listing_type": "sale",
      "status": "disponible",
      "is_featured": false,
      "is_verified": false,
      "is_active": true,
      "image": "https://storage.example.com/props/1/cover.jpg",
      "agent": {
        "id": 1,
        "name": "Alejandro Torres"
      },
      "documents_count": 3,
      "created_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

---

#### `POST /admin/properties`

Crear nueva propiedad.

**Request:** `multipart/form-data` (para subir imagen de portada)

```json
{
  "title": "Casa en Bosques de Orizaba",
  "description": "...",
  "listing_type": "sale",
  "status": "disponible",
  "property_type": "house",
  "property_condition": "semi_new",
  "price": 2500000.00,
  "currency": "MXN",
  "bedrooms": 3,
  "bathrooms": 2,
  "parking_spaces": 2,
  "construction_sqm": 180.00,
  "land_sqm": 250.00,
  "address_street": "Calle Pino",
  "address_number": "45",
  "address_neighborhood": "Bosques",
  "address_zip": "94300",
  "city_id": 1,
  "zone": "Norte",
  "latitude": 18.85,
  "longitude": -97.10,
  "video_id": "dQw4w9WgXcQ",
  "is_featured": false,
  "amenity_ids": [1, 5]
}
```

**Response 201:** Mismo formato que el detalle.

---

#### `GET /admin/properties/{id}`

Detalle de propiedad con todos los datos de gestión.

**Response 200:**
```json
{
  "id": 1,
  "title": "...",
  "images": [...],
  "amenities": [...],
  "nearby_places": [...],
  "documents": [
    {
      "id": 1,
      "name": "Escritura",
      "file_url": "...",
      "mime_type": "application/pdf",
      "size_bytes": 204800,
      "document_stage": null,
      "uploaded_at": "2026-01-15T10:00:00Z"
    }
  ],
  "assignments": [
    {
      "id": 1,
      "agent": { "id": 1, "name": "Alejandro Torres" },
      "is_visible": true,
      "assigned_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

---

#### `PATCH /admin/properties/{id}`

Actualizar propiedad (parcial).

**Request:** Mismos campos que POST, todos opcionales.

**Response 200:** Propiedad actualizada.

---

#### `DELETE /admin/properties/{id}`

Eliminar propiedad (soft delete: `is_active=false`).

**Response 204:** No content.

---

#### `POST /admin/properties/{id}/images`

Subir imágenes a una propiedad.

**Request:** `multipart/form-data`
```
images[]: archivo de imagen
is_cover: boolean (opcional, default: false)
```

**Response 201:**
```json
[
  {
    "id": 1,
    "image_url": "https://storage.example.com/props/1/img1.jpg",
    "is_cover": true,
    "sort_order": 0
  }
]
```

---

#### `DELETE /admin/properties/{id}/images/{image_id}`

Eliminar imagen de propiedad.

**Response 204:** No content.

---

#### `POST /admin/properties/{id}/documents`

Subir documento a una propiedad (desde el admin).

**Request:** `multipart/form-data`
```
file: archivo
name: string
```

**Response 201:**
```json
{
  "id": 1,
  "name": "Escritura",
  "file_url": "...",
  "mime_type": "application/pdf",
  "size_bytes": 204800
}
```

---

#### `PATCH /admin/properties/{id}/toggle-featured`

Activar/desactivar propiedad destacada.

**Response 200:**
```json
{ "is_featured": true }
```

---

### 7.2 Agentes

#### `GET /admin/agents`

Listado de agentes del tenant.

**Response 200:**
```json
{
  "count": 5,
  "results": [
    {
      "id": 1,
      "membership_id": 3,
      "name": "Alejandro Torres",
      "email": "alejandro@altasmontanas.com",
      "phone": "+52 272 123 4567",
      "avatar": "https://...",
      "zone": "Norte",
      "bio": "...",
      "score": "4.50",
      "properties_count": 8,
      "sales_count": 12,
      "leads_count": 5,
      "active_leads": 3
    }
  ]
}
```

---

#### `POST /admin/agents`

Crear agente (invitar usuario como agente al tenant).

**Request:**
```json
{
  "email": "nuevo@agente.com",
  "first_name": "Carlos",
  "last_name": "López",
  "phone": "+52 272 555 0001",
  "zone": "Sur",
  "bio": "Especialista en zona sur"
}
```

**Response 201:** Agente creado con sus datos.

**Reglas:**
- Si el usuario ya existe (por email) → crear `TenantMembership` con `role=agent`
- Si no existe → crear `User` + `TenantMembership` + `AgentProfile`
- Enviar email de bienvenida

---

#### `GET /admin/agents/{id}`

Detalle del agente con estadísticas.

**Response 200:** Mismo formato que listado + horarios actuales.

---

#### `PATCH /admin/agents/{id}`

Actualizar datos del agente (perfil, zona, bio, score).

---

#### `DELETE /admin/agents/{id}`

Desactivar agente (`is_active=false` en la membresía).

**Response 204:** No content.

---

#### `GET /admin/agents/{id}/schedules`

Listado de horarios del agente.

**Response 200:**
```json
[
  {
    "id": 1,
    "name": "Horario normal",
    "monday": true,
    "tuesday": true,
    "wednesday": true,
    "thursday": true,
    "friday": true,
    "saturday": false,
    "sunday": false,
    "start_time": "09:00",
    "end_time": "18:00",
    "has_lunch_break": true,
    "lunch_start": "14:00",
    "lunch_end": "15:00",
    "valid_from": "2026-01-01",
    "valid_until": null,
    "is_active": true,
    "priority": 0,
    "breaks": [
      {
        "id": 1,
        "break_type": "lunch",
        "name": "Comida",
        "start_time": "14:00",
        "end_time": "15:00"
      }
    ]
  }
]
```

---

#### `POST /admin/agents/{id}/schedules`

Crear horario para un agente.

**Request:**
```json
{
  "name": "Horario normal",
  "monday": true,
  "tuesday": true,
  "wednesday": true,
  "thursday": true,
  "friday": true,
  "saturday": false,
  "sunday": false,
  "start_time": "09:00",
  "end_time": "18:00",
  "has_lunch_break": true,
  "lunch_start": "14:00",
  "lunch_end": "15:00",
  "valid_from": "2026-01-01",
  "valid_until": null,
  "priority": 0,
  "breaks": [
    {
      "break_type": "lunch",
      "name": "Comida",
      "start_time": "14:00",
      "end_time": "15:00"
    }
  ]
}
```

**Response 201:** Horario creado.

---

#### `PATCH /admin/agents/{id}/schedules/{schedule_id}`

Actualizar horario del agente.

---

#### `DELETE /admin/agents/{id}/schedules/{schedule_id}`

Eliminar horario del agente.

**Response 204:** No content.

---

#### `GET /admin/agents/{id}/unavailabilities`

Listado de indisponibilidades del agente.

**Response 200:**
```json
[
  {
    "id": 1,
    "start_date": "2026-03-10",
    "end_date": "2026-03-14",
    "reason": "vacation",
    "notes": "Semana santa"
  }
]
```

---

#### `POST /admin/agents/{id}/unavailabilities`

Registrar período de indisponibilidad.

**Request:**
```json
{
  "start_date": "2026-03-10",
  "end_date": "2026-03-14",
  "reason": "vacation",
  "notes": "Semana santa"
}
```

**Response 201:** Indisponibilidad creada.

---

#### `DELETE /admin/agents/{id}/unavailabilities/{unavailability_id}`

Eliminar indisponibilidad.

**Response 204:** No content.

---

### 7.3 Citas

#### `GET /admin/appointments`

Listado de citas del tenant.

**Query Params:** `date`, `agent_id`, `status`, `search` (matrícula o nombre cliente), `limit`, `offset`

**Response 200:**
```json
{
  "count": 30,
  "results": [
    {
      "id": 1,
      "matricula": "CLI-2026-001",
      "scheduled_date": "2026-03-15",
      "scheduled_time": "10:00:00",
      "duration_minutes": 60,
      "status": "programada",
      "client_name": "María García",
      "client_email": "maria@gmail.com",
      "client_phone": "+52 272 987 6543",
      "property": { "id": 1, "title": "Casa en Bosques de Orizaba" },
      "agent": { "id": 1, "name": "Alejandro Torres" }
    }
  ]
}
```

---

#### `POST /admin/appointments`

Crear cita desde el panel admin.

**Request:**
```json
{
  "property_id": 1,
  "agent_membership_id": 3,
  "client_membership_id": 5,
  "scheduled_date": "2026-03-15",
  "scheduled_time": "10:00",
  "duration_minutes": 60,
  "notes": "Cliente interesado en precio"
}
```

**Response 201:** Cita creada con matrícula generada.

**Reglas:**
- Validar disponibilidad completa del agente
- Generar matrícula automáticamente

---

#### `PATCH /admin/appointments/{id}`

Actualizar cita (estado, fecha, hora, notas).

**Reglas:**
- Al cambiar fecha/hora, re-validar disponibilidad
- Si `status=cancelada`, requerir `cancellation_reason`

---

#### `DELETE /admin/appointments/{id}`

Cancelar/eliminar cita.

**Response 204:** No content.

---

#### `GET /admin/appointments/availability`

Consultar disponibilidad de un agente para una fecha.

**Query Params:** `agent_id`, `date`, `exclude_appointment_id` (para edición)

**Response 200:**
```json
{
  "available_slots": ["09:00", "10:00", "11:00", "14:00"],
  "slot_duration_minutes": 60
}
```

---

### 7.4 Asignaciones

#### `GET /admin/assignments`

Mapa de asignaciones actuales.

**Response 200:**
```json
{
  "unassigned_properties": [
    { "id": 2, "title": "Departamento Centro", "property_type": "apartment" }
  ],
  "assignments": [
    {
      "property": { "id": 1, "title": "Casa en Bosques" },
      "agents": [
        { "membership_id": 3, "name": "Alejandro Torres", "is_visible": true }
      ]
    }
  ]
}
```

---

#### `POST /admin/assignments`

Asignar agente a propiedad.

**Request:**
```json
{
  "property_id": 1,
  "agent_membership_id": 3,
  "is_visible": true
}
```

**Response 201:**
```json
{
  "id": 1,
  "property_id": 1,
  "agent_membership_id": 3,
  "is_visible": true,
  "assigned_at": "2026-02-27T10:00:00Z"
}
```

---

#### `PATCH /admin/assignments/{id}`

Actualizar visibilidad de asignación.

**Request:**
```json
{ "is_visible": false }
```

---

#### `DELETE /admin/assignments/{id}`

Desasignar agente de propiedad.

**Response 204:** No content.

---

### 7.5 Clientes

#### `GET /admin/clients`

Directorio de clientes del tenant.

**Query Params:** `search`, `limit`, `offset`

**Response 200:**
```json
{
  "count": 50,
  "results": [
    {
      "id": 5,
      "membership_id": 10,
      "name": "Juan Pérez",
      "email": "juan@gmail.com",
      "phone": "+52 272 111 3333",
      "avatar": null,
      "city": "Orizaba",
      "purchase_processes_count": 2,
      "sale_processes_count": 1,
      "date_joined": "2026-01-10T08:00:00Z"
    }
  ]
}
```

---

#### `GET /admin/clients/{id}`

Detalle del cliente con todos sus procesos.

**Response 200:**
```json
{
  "id": 5,
  "membership_id": 10,
  "name": "Juan Pérez",
  "email": "juan@gmail.com",
  "phone": "+52 272 111 3333",
  "city": "Orizaba",
  "purchase_processes": [
    {
      "id": 1,
      "status": "visita",
      "overall_progress": 11,
      "property": { "id": 1, "title": "Casa en Bosques", "image": "..." },
      "agent": { "name": "Alejandro Torres" },
      "documents": [...],
      "created_at": "2026-02-01T08:00:00Z"
    }
  ],
  "sale_processes": [
    {
      "id": 1,
      "status": "marketing",
      "property": { "id": 3, "title": "Casa propia del cliente", "image": "..." },
      "agent": { "name": "Alejandro Torres" },
      "created_at": "2026-01-20T08:00:00Z"
    }
  ]
}
```

---

### 7.6 Pipeline de Compra (Kanban)

#### `GET /admin/purchase-processes`

Listado de procesos de compra para el Kanban.

**Query Params:** `status`, `agent_id`, `limit`, `offset`

**Response 200:**
```json
{
  "count": 40,
  "results": [
    {
      "id": 1,
      "status": "visita",
      "overall_progress": 11,
      "client": { "id": 5, "name": "Juan Pérez", "avatar": null },
      "property": { "id": 1, "title": "Casa en Bosques", "image": "..." },
      "agent": { "id": 1, "name": "Alejandro Torres" },
      "created_at": "2026-02-01T08:00:00Z",
      "updated_at": "2026-02-10T15:00:00Z"
    }
  ]
}
```

---

#### `POST /admin/purchase-processes`

Crear proceso de compra (convertir lead manual).

**Request:**
```json
{
  "property_id": 1,
  "client_membership_id": 10,
  "agent_membership_id": 3,
  "notes": "Cliente vino desde redes sociales"
}
```

**Response 201:** Proceso creado con `status=lead`.

---

#### `PATCH /admin/purchase-processes/{id}/status`

Mover proceso a otra etapa (acción del Kanban).

**Request:**
```json
{
  "status": "interes",
  "notes": "Cliente confirmó interés formal"
}
```

**Response 200:**
```json
{
  "id": 1,
  "status": "interes",
  "overall_progress": 22,
  "updated_at": "2026-02-27T12:00:00Z"
}
```

**Reglas:**
- Registrar en `process_status_history`
- Si `status=cerrado`, requerir `sale_price` y `payment_method`
- Actualizar `overall_progress` según la etapa

---

#### `PATCH /admin/purchase-processes/{id}`

Actualizar datos generales del proceso (agente, notas, precio de cierre).

---

### 7.7 Pipeline de Venta

#### `GET /admin/sale-processes`

Listado de procesos de venta.

**Query Params:** `status`, `agent_id`, `limit`, `offset`

**Response 200:** Similar a purchase-processes.

---

#### `POST /admin/sale-processes`

Crear proceso de venta manualmente.

**Request:**
```json
{
  "property_id": 3,
  "client_membership_id": 10,
  "agent_membership_id": 3,
  "notes": "Vendedor contactó directamente"
}
```

**Response 201:** Proceso creado con `status=contacto_inicial`.

---

#### `PATCH /admin/sale-processes/{id}/status`

Mover proceso de venta a otra etapa.

**Request:**
```json
{
  "status": "evaluacion",
  "notes": "Agente visitó la propiedad"
}
```

**Response 200:** Proceso actualizado.

**Reglas:**
- Registrar en `process_status_history`
- Si `status=publicacion`, actualizar `property.listing_type=sale` y `property.status=disponible`

---

### 7.8 Seller Leads (Gestión Admin)

#### `GET /admin/seller-leads`

Listado de seller leads del tenant.

**Query Params:** `status`, `search`, `limit`, `offset`

**Response 200:**
```json
{
  "count": 15,
  "results": [
    {
      "id": 1,
      "full_name": "Roberto Méndez",
      "email": "roberto@gmail.com",
      "phone": "+52 272 111 2222",
      "property_type": "house",
      "location": "Orizaba, Veracruz",
      "expected_price": "3000000.00",
      "status": "new",
      "assigned_agent": null,
      "created_at": "2026-02-27T08:00:00Z"
    }
  ]
}
```

---

#### `GET /admin/seller-leads/{id}`

Detalle del seller lead.

---

#### `PATCH /admin/seller-leads/{id}`

Actualizar estado del lead o asignar agente.

**Request:**
```json
{
  "status": "contacted",
  "assigned_agent_membership_id": 3,
  "notes": "Llamamos al cliente, programar visita"
}
```

---

#### `POST /admin/seller-leads/{id}/convert`

Convertir seller lead en propiedad + sale_process.

**Request:**
```json
{
  "agent_membership_id": 3,
  "notes": "Propiedad aprobada, iniciando proceso de venta"
}
```

**Response 201:**
```json
{
  "property_id": 5,
  "sale_process_id": 3,
  "message": "Lead convertido. Se creó la propiedad y el proceso de venta."
}
```

**Reglas:**
- Crear o asociar usuario con `role=client` usando el email del lead
- Crear `Property` con `listing_type=pending_listing`, `status=documentacion`
- Crear `SaleProcess` con `status=contacto_inicial`
- Actualizar `seller_lead.status=converted`

---

### 7.9 Historial de Ventas

#### `GET /admin/history`

Ventas completadas (purchase_processes con status=cerrado).

**Query Params:** `zone`, `property_type`, `payment_method`, `search`, `date_from`, `date_to`, `limit`, `offset`

**Response 200:**
```json
{
  "count": 20,
  "results": [
    {
      "id": 1,
      "property": {
        "title": "Casa en Bosques de Orizaba",
        "property_type": "house",
        "zone": "Norte"
      },
      "client": { "name": "Juan Pérez" },
      "agent": { "name": "Alejandro Torres" },
      "sale_price": "2400000.00",
      "payment_method": "Crédito hipotecario",
      "closed_at": "2026-02-20T15:00:00Z"
    }
  ]
}
```

---

### 7.10 Insights / Analytics

#### `GET /admin/insights`

Datos de analytics del tenant.

**Query Params:** `period` (month, quarter, year, all)

**Response 200:**
```json
{
  "period": "month",
  "sales_by_month": [
    { "month": "2026-01", "count": 3, "total_amount": "7200000.00" },
    { "month": "2026-02", "count": 5, "total_amount": "12500000.00" }
  ],
  "distribution_by_type": [
    { "property_type": "house", "count": 15, "percentage": 60.0 },
    { "property_type": "apartment", "count": 7, "percentage": 28.0 },
    { "property_type": "land", "count": 3, "percentage": 12.0 }
  ],
  "activity_by_zone": [
    { "zone": "Norte", "views": 1200, "leads": 15, "sales": 5 },
    { "zone": "Sur", "views": 800, "leads": 10, "sales": 3 }
  ],
  "top_agents": [
    {
      "id": 1,
      "name": "Alejandro Torres",
      "sales_count": 8,
      "leads_count": 12,
      "score": "4.50"
    }
  ],
  "summary": {
    "total_properties": 25,
    "total_sales": 20,
    "total_revenue": "48000000.00",
    "active_leads": 15
  }
}
```

---

## 8. Endpoints — Agente

Base: `/api/v1/agent`

Todos los endpoints de esta sección requieren `IsAgent`.

---

#### `GET /agent/dashboard`

Dashboard del agente con estadísticas.

**Response 200:**
```json
{
  "agent": {
    "id": 1,
    "name": "Alejandro Torres",
    "avatar": "...",
    "zone": "Norte",
    "score": "4.50"
  },
  "stats": {
    "active_leads": 3,
    "today_appointments": 2,
    "month_sales": 1
  }
}
```

---

#### `GET /agent/properties`

Propiedades asignadas al agente con conteo de leads.

**Response 200:**
```json
{
  "count": 8,
  "results": [
    {
      "id": 1,
      "title": "Casa en Bosques de Orizaba",
      "address": "Calle Pino 45, Col. Bosques",
      "price": "2500000.00",
      "property_type": "house",
      "status": "disponible",
      "image": "...",
      "leads_count": 3,
      "assigned_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

---

#### `GET /agent/properties/{id}/leads`

Prospectos (purchase_processes en etapa temprana) de una propiedad asignada.

**Response 200:**
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "status": "visita",
      "overall_progress": 11,
      "client": {
        "name": "Juan Pérez",
        "email": "juan@gmail.com",
        "phone": "+52 272 111 3333"
      },
      "created_at": "2026-02-01T08:00:00Z",
      "updated_at": "2026-02-10T15:00:00Z"
    }
  ]
}
```

---

#### `GET /agent/appointments`

Citas del agente organizadas por estado (para Kanban).

**Query Params:** `status`, `date`, `limit`, `offset`

**Response 200:**
```json
{
  "count": 12,
  "results": [
    {
      "id": 1,
      "matricula": "CLI-2026-001",
      "scheduled_date": "2026-03-15",
      "scheduled_time": "10:00:00",
      "duration_minutes": 60,
      "status": "programada",
      "client_name": "María García",
      "client_phone": "+52 272 987 6543",
      "property": { "id": 1, "title": "Casa en Bosques" }
    }
  ]
}
```

---

#### `PATCH /agent/appointments/{id}/status`

Actualizar estado de una cita.

**Request:**
```json
{
  "status": "confirmada",
  "notes": "Llamé al cliente, confirmó asistencia"
}
```

**Response 200:** Cita actualizada.

**Reglas:**
- Solo puede actualizar citas propias
- Transiciones válidas: programada → confirmada → en_progreso → completada | cancelada | no_show | reagendada

---

## 9. Endpoints — Cliente

Base: `/api/v1/client`

Todos los endpoints de esta sección requieren `IsClient`.

---

#### `GET /client/dashboard`

Resumen general del cliente.

**Response 200:**
```json
{
  "client": {
    "name": "Juan Pérez",
    "avatar": null,
    "city": "Orizaba"
  },
  "credit_score": null,
  "recent_activity": [
    {
      "type": "purchase_status_change",
      "description": "Tu proceso de compra avanzó a Visita",
      "created_at": "2026-02-10T15:00:00Z"
    }
  ],
  "sale_processes_preview": [
    {
      "id": 1,
      "property_title": "Casa propia",
      "status": "marketing",
      "image": "..."
    }
  ],
  "purchase_processes_preview": [
    {
      "id": 1,
      "property_title": "Casa en Bosques",
      "status": "visita",
      "overall_progress": 11,
      "image": "..."
    }
  ]
}
```

---

#### `GET /client/sales`

Propiedades del cliente en proceso de venta.

**Response 200:**
```json
{
  "stats": {
    "total_properties": 1,
    "total_views": 230,
    "total_interested": 4,
    "total_value": "3000000.00"
  },
  "results": [
    {
      "id": 1,
      "property": {
        "id": 3,
        "title": "Casa propia",
        "address": "...",
        "price": "3000000.00",
        "status": "documentacion",
        "image": "..."
      },
      "status": "marketing",
      "progress_step": 6,
      "views": 230,
      "interested": 4,
      "days_listed": 38,
      "trend": "up",
      "agent": { "name": "Alejandro Torres" }
    }
  ]
}
```

---

#### `GET /client/sales/{process_id}`

Detalle del proceso de venta del cliente.

**Response 200:**
```json
{
  "id": 1,
  "status": "marketing",
  "property": { "id": 3, "title": "Casa propia", "image": "..." },
  "agent": {
    "name": "Alejandro Torres",
    "phone": "+52 272 123 4567",
    "email": "alejandro@altasmontanas.com"
  },
  "stages": [
    { "name": "Contacto Inicial", "status": "completed", "completed_at": "2026-01-20T08:00:00Z" },
    { "name": "Evaluación", "status": "completed", "completed_at": "2026-01-25T10:00:00Z" },
    { "name": "Valuación", "status": "completed", "completed_at": "2026-02-01T09:00:00Z" },
    { "name": "Presentación", "status": "completed", "completed_at": "2026-02-05T14:00:00Z" },
    { "name": "Firma Contrato", "status": "completed", "completed_at": "2026-02-10T11:00:00Z" },
    { "name": "Marketing", "status": "current", "completed_at": null },
    { "name": "Publicación", "status": "pending", "completed_at": null }
  ],
  "history": [
    {
      "previous_status": "firma_contrato",
      "new_status": "marketing",
      "changed_at": "2026-02-10T11:00:00Z",
      "notes": "Firma completada, iniciando preparación de material"
    }
  ]
}
```

---

#### `GET /client/purchases`

Propiedades del cliente en proceso de compra.

**Response 200:**
```json
{
  "count": 2,
  "results": [
    {
      "id": 1,
      "status": "visita",
      "overall_progress": 11,
      "process_stage": "Visita",
      "property": {
        "id": 1,
        "title": "Casa en Bosques de Orizaba",
        "address": "Calle Pino 45, Col. Bosques",
        "price": "2500000.00",
        "image": "..."
      },
      "agent": { "name": "Alejandro Torres" },
      "documents_count": 2,
      "created_at": "2026-02-01T08:00:00Z"
    }
  ]
}
```

---

#### `GET /client/purchases/{process_id}`

Detalle del proceso de compra con timeline.

**Response 200:**
```json
{
  "id": 1,
  "status": "pre_aprobacion",
  "overall_progress": 33,
  "process_stage": "Pre-Aprobación",
  "property": {
    "id": 1,
    "title": "Casa en Bosques de Orizaba",
    "price": "2500000.00",
    "image": "..."
  },
  "agent": {
    "name": "Alejandro Torres",
    "phone": "+52 272 123 4567",
    "email": "alejandro@altasmontanas.com"
  },
  "steps": [
    { "key": "lead", "label": "Lead", "progress": 0, "status": "completed", "allow_upload": false },
    { "key": "visita", "label": "Visita", "progress": 11, "status": "completed", "allow_upload": false },
    { "key": "interes", "label": "Interés", "progress": 22, "status": "completed", "allow_upload": false },
    { "key": "pre_aprobacion", "label": "Pre-Aprobación", "progress": 33, "status": "current", "allow_upload": true },
    { "key": "avaluo", "label": "Avalúo", "progress": 44, "status": "pending", "allow_upload": false },
    { "key": "credito", "label": "Crédito", "progress": 56, "status": "pending", "allow_upload": true },
    { "key": "docs_finales", "label": "Docs Finales", "progress": 67, "status": "pending", "allow_upload": true },
    { "key": "escrituras", "label": "Escrituras", "progress": 78, "status": "pending", "allow_upload": false },
    { "key": "cerrado", "label": "Cerrado", "progress": 100, "status": "pending", "allow_upload": false }
  ],
  "documents": [
    {
      "id": 1,
      "name": "INE",
      "file_url": "...",
      "document_stage": "pre_aprobacion",
      "uploaded_at": "2026-02-12T10:00:00Z"
    }
  ]
}
```

---

#### `POST /client/purchases/{process_id}/documents`

Subir documento en una etapa que permite carga (`allow_upload=true`).

**Request:** `multipart/form-data`
```
file: archivo (pdf, imagen)
name: string (ej: "INE", "Comprobante de ingresos")
```

**Response 201:**
```json
{
  "id": 1,
  "name": "INE",
  "file_url": "...",
  "mime_type": "application/pdf",
  "size_bytes": 204800,
  "document_stage": "pre_aprobacion"
}
```

**Reglas:**
- Solo permitir si el proceso está en una etapa con `allow_upload=true`
- El documento se vincula al `purchase_process_id`

---

#### `GET /client/profile`

Perfil del cliente.

**Response 200:**
```json
{
  "id": 5,
  "email": "juan@gmail.com",
  "first_name": "Juan",
  "last_name": "Pérez",
  "phone": "+52 272 111 3333",
  "avatar": null,
  "city": "Orizaba"
}
```

---

#### `PATCH /client/profile`

Actualizar perfil del cliente.

**Request:**
```json
{
  "first_name": "Juan",
  "last_name": "Pérez",
  "phone": "+52 272 111 3333",
  "city": "Orizaba"
}
```

**Response 200:** Perfil actualizado.

**Reglas:**
- El email NO es editable
- El avatar se actualiza por separado

---

#### `GET /client/notification-preferences`

Obtener preferencias de notificación.

**Response 200:**
```json
{
  "new_properties": true,
  "price_updates": true,
  "appointment_reminders": true,
  "offers": false
}
```

---

#### `PUT /client/notification-preferences`

Actualizar preferencias de notificación.

**Request:**
```json
{
  "new_properties": true,
  "price_updates": false,
  "appointment_reminders": true,
  "offers": false
}
```

**Response 200:** Preferencias actualizadas.

---

#### `GET /client/notifications`

Listado de notificaciones del cliente.

**Query Params:** `is_read`, `limit`, `offset`

**Response 200:**
```json
{
  "count": 10,
  "unread_count": 3,
  "results": [
    {
      "id": 1,
      "title": "Tu proceso avanzó",
      "message": "Tu compra de Casa en Bosques avanzó a la etapa Visita",
      "notification_type": "purchase",
      "is_read": false,
      "reference_type": "purchase_process",
      "reference_id": 1,
      "created_at": "2026-02-10T15:00:00Z"
    }
  ]
}
```

---

#### `PATCH /client/notifications/{id}/read`

Marcar notificación como leída.

**Response 200:**
```json
{ "is_read": true }
```

---

## 10. Endpoints — Catálogos

Base: `/api/v1/catalogs`

**Permisos:** Público (AllowAny)

---

#### `GET /catalogs/countries`

```json
[
  { "id": 1, "name": "México", "code": "MX" }
]
```

---

#### `GET /catalogs/states`

**Query Params:** `country_id`

```json
[
  { "id": 1, "name": "Veracruz", "code": "VER", "country_id": 1 }
]
```

---

#### `GET /catalogs/cities`

**Query Params:** `state_id`

```json
[
  { "id": 1, "name": "Orizaba", "state_id": 1 }
]
```

---

#### `GET /catalogs/amenities`

```json
[
  { "id": 1, "name": "Alberca", "icon": "waves" },
  { "id": 2, "name": "Gimnasio", "icon": "dumbbell" },
  { "id": 3, "name": "Seguridad", "icon": "shield" },
  { "id": 4, "name": "Elevador", "icon": "arrow-up" },
  { "id": 5, "name": "Estacionamiento", "icon": "car" },
  { "id": 6, "name": "Jardín", "icon": "leaf" },
  { "id": 7, "name": "Roof Garden", "icon": "building" }
]
```

---

## 11. Notificaciones compartidas

Base: `/api/v1/notifications`

**Permisos:** IsAuthenticated (cualquier rol)

---

#### `GET /notifications`

Lista de notificaciones del usuario autenticado en el tenant actual.

**Query Params:** `is_read`, `limit`, `offset`

**Response 200:** Mismo formato que `/client/notifications`

---

#### `PATCH /notifications/{id}/read`

Marcar como leída.

---

#### `POST /notifications/read-all`

Marcar todas como leídas.

**Response 200:**
```json
{ "marked_as_read": 5 }
```

---

## 12. Configuración del Proyecto Django

### 12.1 URLs

```python
# config/urls.py
urlpatterns = [
    path('api/v1/auth/', include('apps.users.urls.auth')),
    path('api/v1/public/', include('apps.properties.urls.public')),
    path('api/v1/admin/', include('apps.admin_panel.urls')),
    path('api/v1/agent/', include('apps.agent_panel.urls')),
    path('api/v1/client/', include('apps.client_panel.urls')),
    path('api/v1/catalogs/', include('apps.locations.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
```

### 12.2 Paginación

```python
# core/pagination.py
class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'limit'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })
```

### 12.3 Dependencias (requirements.txt)

```
Django==5.1
djangorestframework==3.15
djangorestframework-simplejwt==5.3
django-filter==24.1
django-cors-headers==4.3
drf-spectacular==0.27
Pillow==10.4
psycopg2-binary==2.9
python-decouple==3.8
```
