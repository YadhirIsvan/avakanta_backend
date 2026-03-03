# Connection Audit — Avakanta Frontend ↔ Backend

> Fecha: 2026-03-02
> Fuentes: spec.md, prd.md, schema.dbml, frontend src/, backend apps/
> Propósito: auditoría completa antes de tocar código

---

## Metodología

Para cada dominio se verificaron:
- Rutas exactas (frontend vs config/urls.py del backend)
- Formato de request/response (frontend types/actions vs spec.md)
- Campos que se mapean (camelCase frontend ↔ snake_case backend)
- Estado real: conectado, mock, roto, o faltante

---

## RESUMEN EJECUTIVO

| Dominio | Estado general | Bloqueantes |
|---|---|---|
| Auth | ✅ Funciona | Ninguno |
| Home / Propiedades públicas | ✅ Funciona | Ninguno |
| Buy / Detalle propiedad | ✅ Funciona | Ninguno |
| Sell / Seller leads | ✅ Funciona | Ninguno |
| Admin | ⚠️ Mayormente funciona | PATCH seller-leads no verificado en backend |
| Agente | ✅ Funciona | Ninguno |
| Cliente | 🔴 Documentos rotos | GET documents endpoint no existe |

---

## 1. AUTH

### Estado actual
Completamente conectado. El flujo OTP (send → verify → refresh → logout) está bien integrado.

### Endpoints usados por el frontend

| Frontend call | Backend URL | Método | Estado |
|---|---|---|---|
| `authApi.sendEmailOtp(email)` | `POST /api/v1/auth/email/otp` | POST | ✅ |
| `authApi.verifyOtp(email, token, extra?)` | `POST /api/v1/auth/email/verify` | POST | ✅ |
| `authApi.refreshToken()` | `POST /api/v1/auth/refresh` | POST | ✅ |
| `authApi.logout()` | `POST /api/v1/auth/logout` | POST | ✅ |
| `authApi.loginWithGoogle(idToken)` | `POST /api/v1/auth/google` | POST | ⚠️ 501 (stub) |
| `authApi.loginWithApple(identityToken)` | `POST /api/v1/auth/apple` | POST | ⚠️ 501 (stub) |
| `authApi.register(data)` | `POST /api/v1/auth/register` | POST | ✅ (no usado en flujo principal) |

### Verificación de campos

**Request `POST /auth/email/otp`**
Frontend envía: `{ email }` → Spec: `{ email }` ✅

**Response `POST /auth/email/otp`**
Spec retorna: `{ message, email, is_new_user }`
Frontend parsea: `data.is_new_user` → `SendOtpResponse.is_new_user` ✅

**Request `POST /auth/email/verify`**
Frontend envía: `{ email, token, first_name?, last_name?, phone? }` → Spec: ✅ campos exactos

**Response `POST /auth/email/verify`**
Spec retorna:
```json
{
  "access": "...",
  "refresh": "...",
  "user": {
    "id": 1,
    "email": "...",
    "first_name": "...",
    "last_name": "...",
    "phone": "...",
    "memberships": [{ "id", "tenant_id", "tenant_name", "tenant_slug", "role" }]
  }
}
```
Frontend type `AuthTokens`: `{ access, refresh, user: AuthUser }` ✅
Frontend type `AuthUser`: `{ id, email, first_name, last_name, phone, memberships }` ✅
Frontend type `AuthMembership`: `{ id, tenant_id, tenant_name, tenant_slug, role }` ✅

### Diferencias encontradas
Ninguna.

### Cambios necesarios en el frontend
Ninguno.

### Cambios necesarios en el backend
Ninguno (Google/Apple son stubs intencionales).

---

## 2. HOME — PROPIEDADES DESTACADAS

### Estado actual
Conectado. La home llama a `/public/properties?featured=true` y mapea correctamente.

### Endpoints usados

| Frontend call | Backend URL | Estado |
|---|---|---|
| `GET /public/properties?featured=true&...` | `GET /api/v1/public/properties` | ✅ |

### Verificación de campos

**Query params que envía el frontend:**
```
featured=true
zone=<string>
type=<house|apartment|land|commercial>    ← mapeado del español al inglés
state=<new|semi_new|used>                 ← mapeado del español al inglés
amenities[]=<id>
limit=<int>
offset=<int>
```

**Spec confirma estos parámetros exactos:** `featured`, `type`, `state`, `zone`, `amenities`, `limit`, `offset` ✅

**Response backend:**
```json
{
  "count": 150,
  "results": [{
    "id", "title", "address", "price", "currency",
    "property_type", "property_condition",
    "bedrooms", "bathrooms", "construction_sqm",
    "zone", "image", "is_verified", "is_featured",
    "days_listed", "interested", "views"
  }]
}
```

**Mapeo en frontend (`mapItem` en `get-featured-properties.actions.ts`):**
| Backend campo | Frontend campo | Estado |
|---|---|---|
| `bedrooms` | `beds` | ✅ |
| `bathrooms` | `baths` | ✅ |
| `construction_sqm` | `sqm` (parseFloat) | ✅ |
| `property_type` | `type` | ✅ |
| `property_condition` | `state` | ✅ |
| `image` | `image` (null → "") | ✅ |
| `price` (string) | `price` (formateado MXN) + `priceNum` | ✅ |
| `is_featured`, `is_verified`, `days_listed`, `interested`, `views` | igual | ✅ |

### Diferencias encontradas
Ninguna.

### Cambios necesarios en el frontend
Ninguno.

### Cambios necesarios en el backend
Ninguno.

---

## 3. BUY — COMPRAR / DETALLE DE PROPIEDAD

### Estado actual
Conectado. Las tres features (lista, detalle, citas) están bien integradas.

### Endpoints usados

| Frontend call | Backend URL | Estado |
|---|---|---|
| `GET /public/properties?...` | `GET /api/v1/public/properties` | ✅ |
| `GET /public/properties/:id` | `GET /api/v1/public/properties/:id` | ✅ |
| `GET /public/appointment/slots?property_id=&date=` | `GET /api/v1/public/appointment/slots` | ✅ |
| `POST /public/properties/:id/appointment` | `POST /api/v1/public/properties/:id/appointment` | ✅ |

### Verificación — Lista de propiedades
Idéntico al dominio Home. Mismo mapeo. ✅

### Verificación — Detalle de propiedad

**Response backend (spec):**
```json
{
  "id", "title", "description", "price", "currency",
  "property_type", "property_condition", "status",
  "bedrooms", "bathrooms", "parking_spaces",
  "construction_sqm", "land_sqm",
  "address", "zone",
  "latitude", "longitude",  ← campos separados en la base de datos
  "is_verified", "views", "days_listed", "interested",
  "images": [{ "id", "image_url", "is_cover", "sort_order" }],
  "amenities": [{ "id", "name", "icon" }],
  "nearby_places": [{ "name", "place_type", "distance_km" }],
  "video_id", "video_thumbnail",
  "agent": { "name", "photo", "phone", "email" },
  "coordinates": { "lat": 18.85, "lng": -97.10 }   ← objeto computado por el serializer
}
```

El serializer del backend construye `coordinates` a partir de `latitude`/`longitude` del modelo. La spec lo confirma explícitamente (sección 6).

**Mapeo en frontend (`mapDetail`):**
| Backend | Frontend | Estado |
|---|---|---|
| `bedrooms` | `beds` | ✅ |
| `bathrooms` | `baths` | ✅ |
| `construction_sqm` | `sqm` | ✅ |
| `is_verified` | `verified` | ✅ |
| `images[]` → sorted by `sort_order` → `image_url` | `images: string[]` | ✅ |
| `video_thumbnail` | `video_img` | ✅ |
| `nearby_places[]` → `{place_type, name, distance_km}` | `"nearby-places": [{icon, label}]` | ✅ |
| `agent` | `agent` | ✅ |
| `coordinates` | `coordinates` | ✅ |

### Verificación — Agendar cita

**Request frontend:**
```json
{ "date": "2026-03-15", "time": "10:00", "name": "...", "phone": "...", "email": "..." }
```
(el frontend convierte de 12h "10:00 AM" a 24h "10:00" antes de enviar)

**Spec request:**
```json
{ "date": "2026-03-15", "time": "10:00", "name": "...", "phone": "...", "email": "..." }
```
✅ Coincide exactamente.

**Response spec:**
```json
{ "id", "matricula", "scheduled_date", "scheduled_time", "duration_minutes", "status", "property": {...}, "agent": {...} }
```
Frontend `AppointmentResponse` type: ✅ campos correctos.

### Diferencias encontradas
Ninguna.

### Cambios necesarios en el frontend
Ninguno.

### Cambios necesarios en el backend
Ninguno.

---

## 4. SELL — SELLER LEADS

### Estado actual
Conectado. El formulario de venta envía correctamente al backend.

### Endpoints usados

| Frontend call | Backend URL | Estado |
|---|---|---|
| `POST /public/seller-leads` | `POST /api/v1/public/seller-leads` | ✅ |

### Verificación de campos

**Request frontend (después de transformación):**
```json
{
  "full_name": "...",
  "email": "...",
  "phone": "...",
  "property_type": "house",   ← mapeado de casa→house, departamento→apartment, etc.
  "location": "...",
  "square_meters": 200.0,     ← parseFloat
  "bedrooms": 3,              ← parseInt
  "bathrooms": 2,             ← parseInt
  "expected_price": 3000000.0 ← parseFloat
}
```

**Spec request:** ✅ Campos idénticos.

**Response spec:**
```json
{ "id": 1, "full_name": "...", "status": "new", "message": "..." }
```

Frontend extrae `response.id` → `leadId` ✅

### Nota de backend
El `SellerLeadCreateView` hardcodea `tenant='altas-montanas'`. En producción multi-tenant esto requeriría leer el tenant del subdominio o header. No es bloqueante para MVP con un solo tenant.

### Cambios necesarios en el frontend
Ninguno.

### Cambios necesarios en el backend
Ninguno (hardcode de tenant es limitación conocida del MVP).

---

## 5. ADMIN

### Estado actual
Mayormente conectado. Todos los endpoints de propiedades, agentes, citas, asignaciones, clientes, kanban, historial e insights están correctamente mapeados. Hay una incertidumbre sobre `PATCH /admin/seller-leads/{id}`.

### Endpoints usados

| Frontend call | Backend URL | Estado |
|---|---|---|
| `GET /admin/properties` | `GET /api/v1/admin/properties` | ✅ |
| `POST /admin/properties` | `POST /api/v1/admin/properties` | ✅ |
| `PATCH /admin/properties/:id` | `PATCH /api/v1/admin/properties/:id` | ✅ |
| `DELETE /admin/properties/:id` | `DELETE /api/v1/admin/properties/:id` | ✅ |
| `POST /admin/properties/:id/images` | `POST /api/v1/admin/properties/:id/images` | ✅ |
| `DELETE /admin/properties/:id/images/:img_id` | `DELETE /api/v1/admin/properties/:id/images/:image_id` | ✅ |
| `PATCH /admin/properties/:id/toggle-featured` | `PATCH /api/v1/admin/properties/:id/toggle-featured` | ✅ |
| `GET /admin/agents` | `GET /api/v1/admin/agents` | ✅ |
| `POST /admin/agents` | `POST /api/v1/admin/agents` | ✅ |
| `PATCH /admin/agents/:id` | `PATCH /api/v1/admin/agents/:id` | ✅ |
| `DELETE /admin/agents/:id` | `DELETE /api/v1/admin/agents/:id` | ✅ |
| `GET /admin/agents/:id/schedules` | `GET /api/v1/admin/agents/:id/schedules` | ✅ |
| `POST /admin/agents/:id/schedules` | `POST /api/v1/admin/agents/:id/schedules` | ✅ |
| `PATCH /admin/agents/:id/schedules/:sid` | `PATCH /api/v1/admin/agents/:id/schedules/:sid` | ✅ |
| `DELETE /admin/agents/:id/schedules/:sid` | `DELETE /api/v1/admin/agents/:id/schedules/:sid` | ✅ |
| `GET /admin/appointments` | `GET /api/v1/admin/appointments` | ✅ |
| `POST /admin/appointments` | `POST /api/v1/admin/appointments` | ✅ |
| `PATCH /admin/appointments/:id` | `PATCH /api/v1/admin/appointments/:id` | ✅ |
| `GET /admin/appointments/availability` | `GET /api/v1/admin/appointments/availability` | ✅ |
| `GET /admin/assignments` | `GET /api/v1/admin/assignments` | ✅ |
| `POST /admin/assignments` | `POST /api/v1/admin/assignments` | ✅ |
| `PATCH /admin/assignments/:id` | `PATCH /api/v1/admin/assignments/:id` | ✅ |
| `DELETE /admin/assignments/:id` | `DELETE /api/v1/admin/assignments/:id` | ✅ |
| `GET /admin/clients` | `GET /api/v1/admin/clients` | ✅ |
| `GET /admin/clients/:id` | `GET /api/v1/admin/clients/:id` | ✅ |
| `GET /admin/purchase-processes` | `GET /api/v1/admin/purchase-processes` | ✅ |
| `POST /admin/purchase-processes` | `POST /api/v1/admin/purchase-processes` | ✅ |
| `PATCH /admin/purchase-processes/:id/status` | `PATCH /api/v1/admin/purchase-processes/:id/status` | ✅ |
| `GET /admin/sale-processes` | `GET /api/v1/admin/sale-processes` | ✅ |
| `POST /admin/sale-processes` | `POST /api/v1/admin/sale-processes` | ✅ |
| `PATCH /admin/sale-processes/:id/status` | `PATCH /api/v1/admin/sale-processes/:id/status` | ✅ |
| `GET /admin/seller-leads` | `GET /api/v1/admin/seller-leads` | ✅ |
| `PATCH /admin/seller-leads/:id` | `PATCH /api/v1/admin/seller-leads/:id` | ⚠️ Ver nota |
| `POST /admin/seller-leads/:id/convert` | `POST /api/v1/admin/seller-leads/:id/convert` | ✅ |
| `GET /admin/history` | `GET /api/v1/admin/history` | ✅ |
| `GET /admin/insights` | `GET /api/v1/admin/insights` | ✅ |

### Verificación de tipos

**`AdminProperty`** (frontend type vs spec):
```
id, title, address, price, currency, property_type, listing_type,
status, is_featured, is_verified, is_active, image,
agent: {id, name} | null, documents_count, created_at
```
Spec retorna estos mismos campos ✅

**`AdminAgent`** (frontend type vs spec):
```
id, membership_id, name, email, phone, avatar, zone, bio, score,
properties_count, sales_count, leads_count, active_leads
```
Spec retorna estos mismos campos ✅

**`AdminAppointment`** (frontend type vs spec):
```
id, matricula, scheduled_date, scheduled_time, duration_minutes,
status, client_name, client_email, client_phone,
property: {id, title}, agent: {id, name}
```
Spec retorna estos mismos campos ✅

**`AdminAssignmentsResponse`** (frontend type vs spec):
```json
{
  "unassigned_properties": [{ "id", "title", "property_type" }],
  "assignments": [{ "property": {...}, "agents": [{ "membership_id", "name", "is_visible" }] }]
}
```
Spec retorna esta estructura exacta ✅

**`AdminPurchaseProcess`** (frontend type vs spec):
```
id, status, overall_progress,
client: {id, name, avatar},
property: {id, title, image},
agent: {id, name},
created_at, updated_at
```
Spec retorna estos campos ✅

**`AdminSellerLead`** (frontend type vs spec):
```
id, full_name, email, phone, property_type, location,
expected_price, status, assigned_agent: {id, name} | null, created_at
```
Spec retorna estos campos ✅

**`AdminSaleHistoryItem`** (frontend type vs spec):
```
id,
property: {title, property_type, zone},
client: {name},
agent: {name},
sale_price, payment_method, closed_at
```
Spec retorna estos campos ✅

**`AdminInsights`** (frontend type vs spec):
```
period, sales_by_month, distribution_by_type,
activity_by_zone, top_agents, summary
```
Spec retorna esta estructura ✅

### Diferencias encontradas

**⚠️ INCERTIDUMBRE — `PATCH /admin/seller-leads/{id}`:**

La spec (sección 7.8, línea 1478) define este endpoint:
```json
PATCH /admin/seller-leads/{id}
Request: { "status": "contacted", "assigned_agent_membership_id": 3, "notes": "..." }
```

El frontend tiene `adminApi.updateSellerLead(id, data)` que llama a este endpoint.

Sin embargo, el análisis del código backend solo encontró `AdminSellerLeadDetailView` registrado como GET (el explorador advirtió que las vistas de transacciones admin estaban parcialmente capturadas).

**Acción requerida:** Verificar en `backend/apps/transactions/views/admin.py` si `AdminSellerLeadDetailView` implementa PATCH además de GET. Si no, este endpoint está **roto**.

### Cambios necesarios en el frontend
Ninguno (si el backend implementa el PATCH de seller-leads correctamente).

### Cambios necesarios en el backend
Verificar que `AdminSellerLeadDetailView` acepte PATCH además de GET. Si no:
- Agregar método `partial_update` o usar `RetrieveUpdateAPIView` en lugar de `RetrieveAPIView`.

---

## 6. AGENTE

### Estado actual
Completamente conectado. Todos los endpoints están correctamente integrados.

### Endpoints usados

| Frontend call | Backend URL | Estado |
|---|---|---|
| `GET /agent/dashboard` | `GET /api/v1/agent/dashboard` | ✅ |
| `GET /agent/properties` | `GET /api/v1/agent/properties` | ✅ |
| `GET /agent/properties/:id/leads` | `GET /api/v1/agent/properties/:id/leads` | ✅ |
| `GET /agent/appointments` | `GET /api/v1/agent/appointments` | ✅ |
| `PATCH /agent/appointments/:id/status` | `PATCH /api/v1/agent/appointments/:id/status` | ✅ |

### Verificación de tipos

**`AgentDashboard`** (frontend vs spec):
```json
{
  "agent": { "id", "name", "avatar", "zone", "score" },
  "stats": { "active_leads", "today_appointments", "month_sales" }
}
```
Spec retorna esta estructura ✅

**`AgentProperty`** — backend retorna:
```json
{ "id", "title", "address", "price", "property_type", "status", "image", "leads_count", "assigned_at" }
```
Frontend mapea:
- `address` → `location` ✅
- `price` → formateado MXN ✅
- `leads_count` → `leads` ✅

**`AgentAppointment`** — backend retorna:
```json
{ "id", "matricula", "scheduled_date", "scheduled_time", "duration_minutes", "status", "client_name", "client_phone", "property": {...} }
```
Frontend mapea:
- `client_name` → `client` ✅
- `property.title` → `property` ✅
- `scheduled_date` → formateado "15 mar" ✅
- `scheduled_time` → formateado 12h ✅
- `matricula`, `duration_minutes`, `client_phone` incluidos ✅

**Leads de propiedad** — backend retorna:
```json
{ "id", "status", "overall_progress", "client": { "name", "email", "phone" }, "created_at", "updated_at" }
```
Frontend mapea:
- `overall_progress` → `stage` ✅
- `updated_at` → `lastContact` ✅

### Diferencias encontradas
Ninguna.

### Cambios necesarios en el frontend
Ninguno.

### Cambios necesarios en el backend
Ninguno.

---

## 7. CLIENTE

### Estado actual
Mayormente conectado, con **un bug crítico**: el endpoint para listar documentos de una compra no existe.

### Endpoints usados

| Frontend call | Backend URL | Estado |
|---|---|---|
| `GET /client/dashboard` | `GET /api/v1/client/dashboard` | ✅ |
| `GET /client/profile` | `GET /api/v1/client/profile` | ✅ |
| `GET /client/notification-preferences` | `GET /api/v1/client/notification-preferences` | ✅ |
| `PUT /client/notification-preferences` | `PUT /api/v1/client/notification-preferences` | ✅ |
| `GET /client/sales` | `GET /api/v1/client/sales` | ✅ |
| `GET /client/sales/:id` | `GET /api/v1/client/sales/:id` | ✅ |
| `GET /client/purchases` | `GET /api/v1/client/purchases` | ✅ |
| `GET /client/purchases/:id` | `GET /api/v1/client/purchases/:id` | ✅ |
| `GET /client/purchases/:id/documents` | ❌ **NO EXISTE EN SPEC NI EN BACKEND** | 🔴 |
| `POST /client/purchases/:id/documents` | `POST /api/v1/client/purchases/:id/documents` | ✅ |

### Bug crítico — Documentos de compra

**Problema:** `client.api.ts` define `getPropertyFiles` como:
```typescript
getPropertyFiles: (processId: number) =>
  axiosInstance.get(`/client/purchases/${processId}/documents`)
```

Este endpoint **no existe** en la spec ni en el backend. La spec solo define POST para subir. Los documentos son retornados **dentro de `GET /client/purchases/:id`** en el campo `documents[]`.

**Spec `GET /client/purchases/:id` retorna:**
```json
{
  "id", "status", "overall_progress", "process_stage",
  "property": {...},
  "agent": {...},
  "steps": [
    { "key", "label", "progress", "status", "allow_upload" }
  ],
  "documents": [
    { "id", "name", "file_url", "document_stage", "uploaded_at" }
  ]
}
```

Los documentos están anidados en el detalle del proceso de compra.

**Fix necesario en el frontend:**
1. En `client.api.ts`: eliminar el método `getPropertyFiles` o redirigirlo a `getPropertyDetail`
2. En `get-client-property-files.actions.ts`: cambiar para llamar `clientApi.getPropertyDetail(processId)` y extraer `data.documents`
3. Verificar que `PropertyFileItem` tenga el campo `uploaded_at` (el type actual no lo incluye, el backend lo retorna)

### Bug potencial — Steps del proceso de compra

**Problema:** La spec retorna un array `steps[]` completo directamente desde el backend (con `key`, `label`, `progress`, `status`, `allow_upload`). El hook `use-client-compras.hook.ts` actualmente reconstruye estos steps localmente desde `overall_progress` (función `buildStepsFromProgress`).

Esto significa que el frontend está computando client-side algo que el backend ya hace server-side. Si el backend calcula los steps correctamente, el frontend debería usarlos directamente.

**Fix necesario:** Verificar si el frontend extrae `steps` del response de `GET /client/purchases/:id` o los recalcula. Si los recalcula, simplificar para usar `data.steps` directamente.

### Verificación de tipos

**`UserProfile`** (frontend vs spec):
```
id, email, first_name, last_name, phone, avatar, city
```
Spec retorna estos campos ✅

**Client dashboard** — backend retorna:
```json
{
  "client": { "name", "avatar", "city" },
  "credit_score": null,
  "recent_activity": [{ "type", "description", "created_at" }],
  "sale_processes_preview": [...],
  "purchase_processes_preview": [...]
}
```
Frontend extrae `dashboard.recent_activity` correctamente ✅
Frontend mapea `type` y `created_at` con `humanizeType` y `hoursAgo` ✅

**Client sales list** — spec retorna:
```json
{
  "stats": { "total_properties", "total_views", "total_interested", "total_value" },
  "results": [{
    "id", "property": { "id", "title", "address", "price", "status", "image" },
    "status", "progress_step", "views", "interested", "days_listed", "trend",
    "agent": { "name" }
  }]
}
```
Frontend mapea `stats` → `summary` y cada `result` → `PropertySaleSummary` ✅
Todos los campos en el nivel correcto (root del result, no dentro de `property`) ✅

**Client purchases list** — spec retorna:
```json
{
  "count", "results": [{
    "id", "status", "overall_progress", "process_stage",
    "property": { "id", "title", "address", "price", "image" },
    "agent": { "name" },
    "documents_count", "created_at"
  }]
}
```
Frontend mapea correctamente a `PropertyBuySummary` ✅

**`NotificationPreferences`** (frontend vs spec):
```
new_properties, price_updates, appointment_reminders, offers
```
Spec retorna estos campos ✅

### Diferencia adicional — PATCH /client/profile faltante en frontend

La spec define `PATCH /client/profile` para editar el perfil del cliente.
El frontend tiene `getUserProfile()` pero no tiene `updateProfile()` en `client.api.ts`.

Si `ClientConfigScreen` necesita guardar cambios de perfil (nombre, teléfono, ciudad), falta implementar este método.

**Fix necesario en el frontend:**
```typescript
updateProfile: (data: Partial<UserProfile>) =>
  axiosInstance.patch("/client/profile", data),
```

### Cambios necesarios en el frontend

1. **CRÍTICO** — `client.api.ts`: cambiar `getPropertyFiles` de `GET /client/purchases/:id/documents` a `GET /client/purchases/:id` (reutilizar `getPropertyDetail` o crear `getPropertyDetailWithDocs`)
2. **CRÍTICO** — `get-client-property-files.actions.ts`: extraer `documents` del response del detalle de compra
3. **RECOMENDADO** — `client.api.ts`: agregar `updateProfile(data)` → `PATCH /client/profile`
4. **RECOMENDADO** — `use-client-compras.hook.ts`: usar `steps[]` del backend directamente en lugar de `buildStepsFromProgress`

### Cambios necesarios en el backend
Ninguno para el bug de documentos (los documentos ya están en el detail endpoint).

---

## 8. FUNCIONALIDADES SIN IMPLEMENTAR EN EL FRONTEND

Estas features existen en el backend pero el frontend no las consume en absoluto.

### 8.1 Notificaciones

**Backend implementado:**
- `GET /api/v1/notifications/` — listar notificaciones con `unread_count`
- `PATCH /api/v1/notifications/:id/read` — marcar como leída
- `POST /api/v1/notifications/read-all` — marcar todas como leídas

**Frontend:** No existe ningún dominio `notifications/`. No hay api, actions, hooks, ni UI.

**Prioridad:** Media. El sistema de notificaciones está completo en backend. Se podría agregar una campana/badge en el header.

### 8.2 Catálogos globales

**Backend implementado:**
- `GET /api/v1/catalogs/countries`
- `GET /api/v1/catalogs/states?country_id=`
- `GET /api/v1/catalogs/cities?state_id=`
- `GET /api/v1/catalogs/amenities`

**Frontend:** No usa estos endpoints. En su lugar:
- Zonas: hardcodeadas en `property.types.ts` (`HOME_ZONES`, `BUY_ZONES`)
- Amenidades: hardcodeadas en `AMENITY_OPTIONS` con IDs strings genéricos (`pool`, `security`, etc.) en lugar de los IDs numéricos reales del backend

**Diferencia importante para amenidades:**
El frontend envía `amenities=pool,security` pero el backend filtra por IDs numéricos (`amenities=1,3`). El filtro de amenidades está roto para la búsqueda de propiedades.

**Prioridad:** Media-Alta para amenidades (búsqueda rota). Baja para zonas (hardcodear zonas es aceptable si no cambian).

**Fix necesario en el frontend:**
- Cargar amenidades desde `GET /catalogs/amenities` al arrancar
- Usar los IDs numéricos reales del backend en los filtros

### 8.3 Indisponibilidades de agente (Admin)

**Backend implementado:**
- `GET /api/v1/admin/agents/:id/unavailabilities`
- `POST /api/v1/admin/agents/:id/unavailabilities`
- `DELETE /api/v1/admin/agents/:id/unavailabilities/:uid`

**Frontend:** La `admin.api.ts` no tiene métodos para indisponibilidades. La sección de config de citas (`ConfigCitasSection`) probablemente no puede gestionar períodos de indisponibilidad.

**Prioridad:** Baja.

---

## 9. TABLA RESUMEN DE CAMBIOS

### Cambios necesarios en el FRONTEND (por prioridad)

| # | Archivo | Cambio | Prioridad |
|---|---|---|---|
| 1 | `myAccount/client/api/client.api.ts` | Eliminar `getPropertyFiles` (endpoint no existe) | 🔴 Crítico |
| 2 | `myAccount/client/actions/get-client-property-files.actions.ts` | Llamar `getPropertyDetail` y extraer `documents[]` | 🔴 Crítico |
| 3 | `buy/types/property.types.ts` | En `AMENITY_OPTIONS`: cambiar IDs de string a numérico real | ⚠️ Alto |
| 4 | `buy/` (nuevo) | Crear `get-amenities.actions.ts` para cargar amenidades desde `/catalogs/amenities` | ⚠️ Alto |
| 5 | `myAccount/client/api/client.api.ts` | Agregar `updateProfile(data)` → `PATCH /client/profile` | ⚠️ Medio |
| 6 | `myAccount/client/hooks/use-client-compras.hook.ts` | Usar `steps[]` del backend en lugar de `buildStepsFromProgress` | ⚠️ Medio |
| 7 | `myAccount/client/types/client.types.ts` | Agregar `uploaded_at?: string` a `PropertyFileItem` | Bajo |
| 8 | (nuevo dominio) `notifications/` | Crear api, actions, hooks para notificaciones | Bajo |

### Cambios necesarios en el BACKEND (por prioridad)

| # | Archivo | Cambio | Prioridad |
|---|---|---|---|
| 1 | `apps/transactions/views/admin.py` | Verificar que `AdminSellerLeadDetailView` soporte PATCH (según spec). Si no, implementarlo. | ⚠️ Alto |

---

## 10. FLUJO DE DATOS — DIAGRAMA POR DOMINIO

```
AUTH ✅
  Browser → send-email-otp.actions → POST /auth/email/otp → { message, email, is_new_user }
  Browser → verify-otp.actions → POST /auth/email/verify → { access, refresh, user: {..., memberships} }
  localStorage: access_token, refresh_token, user
  axios interceptor: adjunta Bearer token automáticamente
  axios interceptor: refresca silenciosamente en 401

PUBLIC PROPERTIES ✅
  HomePage/BuyPage → get-featured/properties.actions → GET /public/properties?featured=true&type=house&...
  Backend: filtra status=disponible, listing_type=sale, is_active=true
  Serializer: computa days_listed, interested (annotate), image (portada)

PROPERTY DETAIL ✅
  PropertyDetailPage → get-property-detail.actions → GET /public/properties/:id
  Backend: incrementa views, retorna agent (is_visible=true), coordinates objeto

APPOINTMENTS ✅
  PropertyDetailPage → get-appointment-slots.actions → GET /public/appointment/slots?property_id=&date=
  PropertyDetailPage → schedule-appointment.actions → POST /public/properties/:id/appointment

SELL ✅
  SellPage → submit-seller-lead.actions → POST /public/seller-leads

ADMIN ✅ (+ verificar PATCH seller-leads)
  AdminPage → 9 secciones, cada una con su actions correspondiente

AGENT ✅
  AgentPage → dashboard + properties + leads + appointments

CLIENT 🔴 (documentos rotos)
  ClientPage → dashboard + ventas + compras + config
  Bug: getPropertyFiles llama endpoint inexistente
  Fix: extraer documents de GET /client/purchases/:id
```

---

## 11. ESTADO DE CONECTIVIDAD VISUAL

```
✅ = Funciona correctamente
⚠️ = Funciona con caveat / necesita verificación
🔴 = Roto / no implementado

Auth          ████████████████████  ✅ 100%
Home          ████████████████████  ✅ 100%
Buy/Detalle   ████████████████████  ✅ 100%
Sell          ████████████████████  ✅ 100%
Admin         ████████████████░░░░  ⚠️  ~90% (seller-lead update sin verificar)
Agente        ████████████████████  ✅ 100%
Cliente       ████████████████░░░░  🔴 ~80% (documentos de compra rotos)
Notificaciones░░░░░░░░░░░░░░░░░░░░  🔴   0% (no implementado en frontend)
Catálogos     ░░░░░░░░░░░░░░░░░░░░  ⚠️   0% (hardcodeado en frontend)
Amenity filter░░░░░░░░░░░░░░░░░░░░  🔴   0% (IDs incorrectos en filtros buy)
```
