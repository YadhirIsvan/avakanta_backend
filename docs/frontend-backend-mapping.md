# Frontend ↔ Backend Mapping — Avakanta

> Generado: 2026-03-01
> Base URL Backend: `http://localhost:8000/api/v1`
> Frontend: `front/ajolote-home-ui/src/`
> Backend Spec: `backend/docs/spec.md`

---

## Estado del arte (resumen rápido)

| Dominio | Estado actual |
|---|---|
| Auth | API real conectada pero **tokens no se guardan**, respuesta no se parsea, interceptor JWT faltante |
| Home | Endpoint incorrecto (`/api/properties`), mock fallback activo |
| Buy / Detalle | Endpoints incorrectos (`/api/properties`), mock fallback activo |
| Sell | Endpoint incorrecto (`/api/seller-leads/`), campos en camelCase (back espera snake_case) |
| MyAccount Admin | Múltiples rutas incorrectas, import de axiosInstance roto, endpoints faltantes |
| MyAccount Agent | Prefijo `/api/` sobrante en todas las rutas, `PATCH status` mal construido |
| MyAccount Client | Todas las rutas incorrectas (`/api/user/...`), campos en PascalCase vs snake_case |
| CreditFlow | 100% UI local, sin API — sin cambios necesarios |

---

## 0. Setup

### 0.1 Configuración de Axios — `src/shared/api/axios.instance.ts`

**Problema actual:** `baseURL` es `""` o `VITE_API_BASE_URL`. No hay interceptor JWT ni refresh automático.

**Archivo a modificar:** `src/shared/api/axios.instance.ts`

```typescript
import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

const axiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// ─── REQUEST: adjunta access token ──────────────────────────────────────────
axiosInstance.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ─── RESPONSE: refresca token automáticamente si recibe 401 ─────────────────
let isRefreshing = false;
let failedQueue: Array<{ resolve: (v: string) => void; reject: (e: unknown) => void }> = [];

const processQueue = (error: unknown, token: string | null) => {
  failedQueue.forEach((p) => (token ? p.resolve(token) : p.reject(error)));
  failedQueue = [];
};

axiosInstance.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return axiosInstance(originalRequest);
        });
      }
      originalRequest._retry = true;
      isRefreshing = true;
      const refresh = localStorage.getItem("refresh_token");
      if (!refresh) {
        isRefreshing = false;
        localStorage.removeItem("access_token");
        window.location.href = "/";
        return Promise.reject(error);
      }
      try {
        const { data } = await axios.post(`${BASE_URL}/auth/refresh`, { refresh });
        localStorage.setItem("access_token", data.access);
        localStorage.setItem("refresh_token", data.refresh);
        processQueue(null, data.access);
        originalRequest.headers.Authorization = `Bearer ${data.access}`;
        return axiosInstance(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/";
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

export default axiosInstance;
export { axiosInstance }; // named export también para compatibilidad
```

### 0.2 Variables de entorno — `.env.local` del frontend

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

### 0.3 Guardar tokens tras login

En la acción de `verifyOtp` (y Google / Apple):
```typescript
localStorage.setItem("access_token", data.access);
localStorage.setItem("refresh_token", data.refresh);
// Guardar también el user en un Context o Zustand store
```

En `logout`:
```typescript
localStorage.removeItem("access_token");
localStorage.removeItem("refresh_token");
```

---

## 1. Auth

**Base backend:** `/api/v1/auth`

### 1.1 Archivos a modificar

| Archivo | Tipo de cambio |
|---|---|
| `src/auth/api/auth.api.ts` | Agregar `register`, body a `logout` y `refreshToken` |
| `src/auth/types/auth.types.ts` | Agregar `RegisterRequest`, `RegisterResponse` y tipos completos de respuesta |
| `src/auth/actions/register.actions.ts` | **Crear nuevo** — manejador del formulario de registro |
| `src/auth/actions/send-email-otp.actions.ts` | Parsear respuesta real del back |
| `src/auth/actions/verify-otp.actions.ts` | Parsear respuesta real + guardar tokens |

### 1.2 Endpoints

#### `register` ← **NUEVO**
```
POST /auth/register
```
**Permisos:** Público (AllowAny)

**Archivo del front a tocar:** `src/auth/api/auth.api.ts` + `src/auth/actions/register.actions.ts` (crear)

**Request body:**
```json
{
  "email": "usuario@ejemplo.com",
  "first_name": "Juan",
  "last_name": "Pérez",
  "phone": "+52 272 100 0000"
}
```
> `phone` es opcional. Todos los demás campos son requeridos.

**Response 201:**
```json
{
  "message": "Usuario creado. OTP enviado al email.",
  "email": "usuario@ejemplo.com"
}
```

**Response 400 — usuario ya existe:**
```json
{ "error": "El usuario ya existe, usa login" }
```

**Response 400 — campos faltantes:**
```json
{ "first_name": ["This field is required."], "last_name": ["This field is required."] }
```

**Notas de implementación:**
- El back crea el usuario, asigna `TenantMembership` con `role=client` en el tenant default **y envía el OTP automáticamente** en una sola llamada. El front **no necesita llamar a `/auth/email/otp` por separado** después del registro.
- Tras recibir 201, redirigir al usuario a la pantalla de verificación OTP (`/auth/verify`) pasando el email como parámetro.
- Si el back retorna 400 con `"El usuario ya existe, usa login"`, mostrar mensaje y redirigir al flujo de login (`/auth/email/otp`).
- Los campos en el body deben estar en **snake_case** (`first_name`, `last_name`), no camelCase.

**Ejemplo de implementación en `auth.api.ts`:**
```typescript
export const register = (data: RegisterRequest) =>
  axiosInstance.post<RegisterResponse>("/auth/register", data);
```

**Flujo completo de registro:**
```
[Formulario Registro] → POST /auth/register → 201
  → redirigir a /auth/verify?email=...
  → [Formulario OTP] → POST /auth/email/verify → 200 + tokens
  → guardar tokens → redirigir a dashboard según role
```

---

#### `sendEmailOtp`
```
POST /auth/email/otp
```
**Request body:**
```json
{ "email": "usuario@ejemplo.com" }
```
**Response 200:**
```json
{
  "message": "OTP enviado al email",
  "email": "usuario@ejemplo.com",
  "is_new_user": true
}
```
> Usar `is_new_user` para decidir qué formulario mostrar en el paso verify:
> - `true` → mostrar campos nombre, apellido y teléfono (registro)
> - `false` → mostrar solo el campo de código OTP (login)

**Response 429:** `{ "error": "Demasiados intentos. Intenta en 60 segundos." }`

---

#### `verifyOtp`
```
POST /auth/email/verify
```
**Request body:**
```json
{
  "email": "usuario@ejemplo.com",
  "token": "123456",
  "first_name": "Juan",
  "last_name": "Pérez",
  "phone": "+52 272 100 0000"
}
```
> `first_name`, `last_name`, `phone` son opcionales. Enviarlos solo si `is_new_user` fue `true`.

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
    "phone": "+52 272 100 0000",
    "memberships": [
      { "id": 1, "tenant_id": 1, "tenant_name": "Altas Montañas", "tenant_slug": "altas-montanas", "role": "client" }
    ]
  }
}
```

---

#### `loginWithGoogle`
```
POST /auth/google
```
**Request body:** `{ "idToken": "eyJ..." }`
**Response 200:** Mismo formato que `verifyOtp`

---

#### `loginWithApple`
```
POST /auth/apple
```
**Request body:** `{ "identityToken": "eyJ..." }`
**Response 200:** Mismo formato que `verifyOtp`

---

#### `refreshToken`
```
POST /auth/refresh
```
**Request body:** `{ "refresh": "eyJ..." }` ← **falta en la implementación actual**
**Response 200:** `{ "access": "eyJ...", "refresh": "eyJ..." }`

---

#### `logout`
```
POST /auth/logout
```
**Permisos:** Bearer token requerido (`IsAuthenticated`)
**Request body:** `{ "refresh": "eyJ..." }` ← **falta en la implementación actual**
**Response 200:** `{ "message": "Sesión cerrada" }`

---

### 1.3 Mapeo de campos

| Front (`SendOtpResponse`) | Back (`/auth/email/otp` response) | Acción |
|---|---|---|
| `isNewUser` | `is_new_user` | Renombrar a camelCase |
| `email` | `email` | Igual |

| Front (`VerifyOtpResponse`) | Back (`/auth/email/verify` response) | Acción |
|---|---|---|
| `accessToken` | `access` | Renombrar campo |
| — | `refresh` | Agregar al tipo |
| — | `user.id`, `user.email`, `user.first_name`, `user.last_name`, `user.phone` | Agregar al tipo |
| — | `user.memberships[].role` | Leer para determinar redirección |
| `success` | — | Campo local, no viene del back |

### 1.4 Tipos TypeScript a agregar en `auth/types/auth.types.ts`

```typescript
export type UserRole = "client" | "agent" | "admin";

// ── OTP Request ───────────────────────────────────────────────────────────────
export interface SendOtpRequest {
  email: string;
}

export interface SendOtpResponse {
  message: string;
  email: string;
  is_new_user: boolean;  // true = registro, false = login
}

// ── OTP Verify ────────────────────────────────────────────────────────────────
export interface VerifyOtpRequest {
  email: string;
  token: string;
  first_name?: string;   // solo si is_new_user fue true
  last_name?: string;    // solo si is_new_user fue true
  phone?: string;        // solo si is_new_user fue true
}

// ── Register ──────────────────────────────────────────────────────────────────
export interface RegisterRequest {
  email: string;
  first_name: string;
  last_name: string;
  phone?: string;
}

export interface RegisterResponse {
  message: string;
  email: string;
}

// ── Auth User / Tokens ────────────────────────────────────────────────────────
export interface AuthMembership {
  id: number;
  tenant_id: number;
  tenant_name: string;
  tenant_slug: string;
  role: UserRole;
}

export interface AuthUser {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  memberships: AuthMembership[];
}

export interface AuthTokens {
  access: string;
  refresh: string;
  user: AuthUser;
}
```

---

## 2. Propiedades Públicas (Home + Buy + Detalle)

**Base backend:** `/api/v1/public`

### 2.1 Archivos a modificar

| Archivo | Tipo de cambio |
|---|---|
| `src/home/api/home.api.ts` | Corregir endpoint |
| `src/home/types/property.types.ts` | Renombrar campos al snake_case del back |
| `src/home/actions/get-featured-properties.actions.ts` | Parsear respuesta paginada, agregar `featured=true` |
| `src/buy/api/buy.api.ts` | Corregir endpoints |
| `src/buy/types/property.types.ts` | Renombrar campos + agregar campos faltantes |
| `src/buy/actions/get-properties.actions.ts` | Parsear respuesta paginada del back |
| `src/buy/actions/get-property-detail.actions.ts` | Parsear respuesta real del back |

### 2.2 `GET /public/properties` — Listado

**Endpoint correcto:**
```
GET /public/properties
```

**Query params disponibles:**
| Param | Tipo | Nota |
|---|---|---|
| `zone` | string | Norte, Sur, Centro, Oriente, Poniente |
| `type` | string | `house`, `apartment`, `land`, `commercial` |
| `state` | string | `new`, `semi_new`, `used` |
| `amenities` | string[] | IDs de amenidades |
| `price_min` | decimal | |
| `price_max` | decimal | |
| `featured` | boolean | Pasar `true` para home |
| `search` | string | Búsqueda por título o dirección |
| `limit` | int | Default 20 |
| `offset` | int | Default 0 |
| `ordering` | string | `price`, `-price`, `created_at`, `-created_at` |

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

**Nota:** La respuesta es **paginada** (`count` + `results`). El front actualmente espera un array directo.

### 2.3 Mapeo de campos — Listado

| Front (`PropertyListItem` / `BuyPropertyListItem`) | Back (`results[]`) | Acción |
|---|---|---|
| `image` | `image` | ✅ Igual |
| `price` | `price` (string `"2500000.00"`) | Formatear en front: `"$2,500,000"` |
| `priceNum` | `price` (parsear a float) | Campo computado en front |
| `title` | `title` | ✅ Igual |
| `address` | `address` | ✅ Igual (el back lo computa) |
| `beds` | `bedrooms` | Renombrar |
| `baths` | `bathrooms` | Renombrar |
| `sqm` | `construction_sqm` (parsear a float) | Renombrar |
| `type` | `property_type` | Renombrar. Valores: `house`/`apartment`/`land`/`commercial` |
| `state` | `property_condition` | Renombrar. Valores: `new`/`semi_new`/`used` |
| — | `days_listed` | Agregar |
| — | `interested` | Agregar |
| — | `views` | Agregar |
| — | `is_featured`, `is_verified` | Agregar |

**Nota sobre filtros:** En el front, los valores de `type` son `"casa"`, `"departamento"`, etc. El back espera `"house"`, `"apartment"`. Hay que hacer la traducción antes de enviar:
```typescript
const typeMap: Record<string, string> = {
  "casa": "house",
  "departamento": "apartment",
  "terreno": "land",
  "local": "commercial",
};
const typeParam = typeMap[filters.type] ?? filters.type;
```
Igualmente para `state`: `"nueva"→"new"`, `"usada"→"used"`, `"semi_new"` ya coincide (verificar si el front usa `"preventa"`; no existe en el back, posiblemente se mapea a `"new"`).

---

### 2.4 `GET /public/properties/{id}` — Detalle

**Endpoint correcto:**
```
GET /public/properties/{id}
```

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
    { "id": 1, "image_url": "https://...", "is_cover": true, "sort_order": 0 }
  ],
  "amenities": [
    { "id": 1, "name": "Alberca", "icon": "waves" }
  ],
  "nearby_places": [
    { "name": "Hospital Regional", "place_type": "hospital", "distance_km": "1.20" }
  ],
  "video_id": "dQw4w9WgXcQ",
  "video_thumbnail": "https://img.youtube.com/vi/dQw4w9WgXcQ/0.jpg",
  "agent": { "name": "Alejandro Torres", "photo": "...", "phone": "+52 272 123 4567", "email": "alejandro@..." },
  "coordinates": { "lat": 18.85, "lng": -97.10 }
}
```

**Nota importante:** El back **incrementa `views` en +1** en cada llamada a este endpoint.

### 2.5 Mapeo de campos — Detalle

| Front (`PropertyDetailData`) | Back | Acción |
|---|---|---|
| `images` (array de strings URL) | `images[].image_url` | Mapear: extraer solo `image_url` |
| `beds` | `bedrooms` | Renombrar |
| `baths` | `bathrooms` | Renombrar |
| `sqm` | `construction_sqm` (parsear) | Renombrar |
| `verified` | `is_verified` | Renombrar |
| `video_id` | `video_id` | ✅ Igual |
| `video_img` | `video_thumbnail` | Renombrar |
| `coordinates` | `coordinates` (`{ lat, lng }`) | ✅ Igual |
| `"nearby-places"[].icon` | `nearby_places[].place_type` | Renombrar + cambiar key |
| `"nearby-places"[].label` | `nearby_places[].name` + `distance_km` | Componer: `"Hospital Regional - 1.2 km"` |
| `agent.phone` (number) | `agent.phone` (string `"+52 272..."`) | Cambiar tipo a string |

---

### 2.6 `POST /public/properties/{id}/appointment` — Agendar cita

> Este endpoint aún no tiene archivo dedicado en el frontend. Crear en `buy/api/buy.api.ts`.

**Endpoint:**
```
POST /public/properties/{id}/appointment
```
**Request body:**
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
  "property": { "id": 1, "title": "Casa en Bosques de Orizaba" },
  "agent": { "name": "Alejandro Torres" }
}
```
**Notas:**
- El agente se asigna automáticamente (el back busca el primer agente con `is_visible=true`)
- `TIME_SLOTS` del front usa formato `"9:00 AM"`, el back espera `"09:00"` (24h) — convertir antes de enviar

---

### 2.7 `GET /public/appointment/slots` — Slots disponibles

> Aún no tiene archivo en el frontend. Agregar a `buy/api/buy.api.ts`.

**Endpoint:**
```
GET /public/appointment/slots?property_id={id}&date={YYYY-MM-DD}
```
**Response 200:**
```json
{
  "date": "2026-03-15",
  "agent": { "name": "Alejandro Torres" },
  "available_slots": ["09:00", "10:00", "11:00", "14:00"],
  "slot_duration_minutes": 60
}
```

---

## 3. Sell — Seller Leads

**Base backend:** `/api/v1/public`

### 3.1 Archivos a modificar

| Archivo | Tipo de cambio |
|---|---|
| `src/sell/api/sell.api.ts` | Corregir endpoint |
| `src/sell/actions/submit-seller-lead.actions.ts` | Renombrar campos a snake_case, parsear respuesta real |

### 3.2 `POST /public/seller-leads` — Enviar lead

**Endpoint correcto:**
```
POST /public/seller-leads
```
*(actualmente el front usa `/api/seller-leads/`)*

**Request body:**
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

### 3.3 Mapeo de campos — SellerLeadData

| Front (`SellerLeadData`) | Back (request body) | Acción |
|---|---|---|
| `propertyType` | `property_type` | Renombrar + traducir: `"casa"→"house"` etc. |
| `location` | `location` | ✅ Igual |
| `squareMeters` (string) | `square_meters` (float) | Renombrar + `parseFloat()` |
| `bedrooms` (string) | `bedrooms` (int) | `parseInt()` |
| `bathrooms` (string) | `bathrooms` (int) | `parseInt()` |
| `expectedPrice` (string) | `expected_price` (float) | Renombrar + `parseFloat()` |
| `fullName` | `full_name` | Renombrar |
| `phone` | `phone` | ✅ Igual |
| `email` | `email` | ✅ Igual |

**Mapeo de `property_type`:**
| Front (español) | Back (inglés) |
|---|---|
| `"casa"` | `"house"` |
| `"departamento"` | `"apartment"` |
| `"terreno"` | `"land"` |
| `"local"` | `"commercial"` |

---

## 4. MyAccount — Admin

**Base backend:** `/api/v1/admin`
**Permisos:** Bearer token con `role=admin`

### 4.1 Archivos a modificar

| Archivo | Tipo de cambio |
|---|---|
| `src/myAccount/admin/api/admin.api.ts` | Corregir rutas, método PATCH, agregar endpoints faltantes, fix import |
| `src/myAccount/admin/types/admin.types.ts` | Agregar tipos de respuesta del back |
| `src/myAccount/admin/hooks/use-admin-dashboard.hook.ts` | Integrar llamadas reales |

**Bug crítico de import:** `admin.api.ts` importa `import { axiosInstance } from "@/shared/api/axios.instance"` (named import), pero el archivo actualmente solo exporta `export default`. Después de aplicar el nuevo `axios.instance.ts` con `export { axiosInstance }` el import queda correcto.

---

### 4.2 Propiedades Admin

#### `GET /admin/properties`
**Query params:** `search`, `status`, `listing_type`, `property_type`, `agent_id`, `limit`, `offset`

**Response 200:**
```json
{
  "count": 25,
  "results": [
    {
      "id": 1,
      "title": "Casa en Bosques de Orizaba",
      "address": "...",
      "price": "2500000.00",
      "currency": "MXN",
      "property_type": "house",
      "listing_type": "sale",
      "status": "disponible",
      "is_featured": false,
      "is_verified": false,
      "is_active": true,
      "image": "...",
      "agent": { "id": 1, "name": "Alejandro Torres" },
      "documents_count": 3,
      "created_at": "2026-01-15T10:00:00Z"
    }
  ]
}
```

---

#### `POST /admin/properties`
**Nota:** Usa `multipart/form-data` (no JSON) porque puede incluir imagen de portada.

**Request fields:**
```
title, description, listing_type, status, property_type, property_condition,
price, currency, bedrooms, bathrooms, parking_spaces, construction_sqm, land_sqm,
address_street, address_number, address_neighborhood, address_zip,
city_id, zone, latitude, longitude, video_id, is_featured, amenity_ids[]
```

**Front actualmente usa:** `axiosInstance.post("/admin/properties", data)` con JSON.
**Corrección:** Cambiar a `multipart/form-data` si se envían imágenes, o mantener JSON si solo se envían datos (sin imagen inicial).

---

#### `PATCH /admin/properties/{id}` ← **el front usa PUT, debe ser PATCH**
**Request body:** Mismos campos que POST, todos opcionales.

---

#### `DELETE /admin/properties/{id}`
**Response:** 204 No Content

---

#### `POST /admin/properties/{id}/images`
**Tipo:** `multipart/form-data`
```
images[]: archivo(s) de imagen
is_cover: boolean (opcional)
```

---

#### `PATCH /admin/properties/{id}/toggle-featured`
**Response:** `{ "is_featured": true }`

---

### 4.3 Agentes Admin

#### `GET /admin/agents`
**Response 200:**
```json
{
  "count": 5,
  "results": [
    {
      "id": 1,
      "membership_id": 3,
      "name": "Alejandro Torres",
      "email": "alejandro@...",
      "phone": "+52 272 123 4567",
      "avatar": "...",
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

#### `POST /admin/agents`
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

#### `PATCH /admin/agents/{id}`
**Body:** Mismos campos que POST, todos opcionales.

#### `DELETE /admin/agents/{id}` → Response 204

---

### 4.4 Horarios de agente (Config Citas)

#### `GET /admin/agents/{id}/schedules`
**Response 200:** Array de horarios con estructura:
```json
[{
  "id": 1, "name": "Horario normal",
  "monday": true, "tuesday": true, "wednesday": true, "thursday": true, "friday": true,
  "saturday": false, "sunday": false,
  "start_time": "09:00", "end_time": "18:00",
  "has_lunch_break": true, "lunch_start": "14:00", "lunch_end": "15:00",
  "valid_from": "2026-01-01", "valid_until": null,
  "is_active": true, "priority": 0,
  "breaks": [{ "id": 1, "break_type": "lunch", "name": "Comida", "start_time": "14:00", "end_time": "15:00" }]
}]
```

#### `POST /admin/agents/{id}/schedules`
**Body:** Mismo formato sin `id`, incluyendo `breaks[]`.

#### `PATCH /admin/agents/{id}/schedules/{schedule_id}` — actualizar horario
#### `DELETE /admin/agents/{id}/schedules/{schedule_id}` — eliminar horario

---

### 4.5 Citas Admin

#### `GET /admin/appointments`
**Query params:** `date`, `agent_id`, `status`, `search`, `limit`, `offset`

**Response 200:**
```json
{
  "count": 30,
  "results": [{
    "id": 1, "matricula": "CLI-2026-001",
    "scheduled_date": "2026-03-15", "scheduled_time": "10:00:00",
    "duration_minutes": 60, "status": "programada",
    "client_name": "María García", "client_email": "maria@gmail.com", "client_phone": "+52...",
    "property": { "id": 1, "title": "Casa en Bosques de Orizaba" },
    "agent": { "id": 1, "name": "Alejandro Torres" }
  }]
}
```

#### `POST /admin/appointments`
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

#### `PATCH /admin/appointments/{id}` — actualizar (estado, fecha, hora, notas)
**Nota:** Si `status=cancelada`, enviar también `cancellation_reason`.

#### `GET /admin/appointments/availability?agent_id={id}&date={YYYY-MM-DD}`
**Response:** `{ "available_slots": ["09:00", "10:00"], "slot_duration_minutes": 60 }`

---

### 4.6 Asignaciones ← **el front usa endpoint incorrecto**

**Problema:** El front usa `PATCH /admin/properties/{propertyId}/assign` — **este endpoint no existe en el back**.
**Corrección:** Usar los endpoints de `/admin/assignments`.

#### `GET /admin/assignments`
**Response:**
```json
{
  "unassigned_properties": [{ "id": 2, "title": "...", "property_type": "apartment" }],
  "assignments": [{
    "property": { "id": 1, "title": "Casa en Bosques" },
    "agents": [{ "membership_id": 3, "name": "Alejandro Torres", "is_visible": true }]
  }]
}
```

#### `POST /admin/assignments` ← reemplaza el PATCH actual
```json
{ "property_id": 1, "agent_membership_id": 3, "is_visible": true }
```
**Response 201:** `{ "id": 1, "property_id": 1, "agent_membership_id": 3, "is_visible": true, "assigned_at": "..." }`

#### `PATCH /admin/assignments/{id}`
```json
{ "is_visible": false }
```

#### `DELETE /admin/assignments/{id}` → Response 204

---

### 4.7 Clientes Admin

#### `GET /admin/clients`
**Query params:** `search`, `limit`, `offset`

**Response 200:**
```json
{
  "count": 50,
  "results": [{
    "id": 5, "membership_id": 10,
    "name": "Juan Pérez", "email": "juan@gmail.com", "phone": "+52...",
    "avatar": null, "city": "Orizaba",
    "purchase_processes_count": 2, "sale_processes_count": 1,
    "date_joined": "2026-01-10T08:00:00Z"
  }]
}
```

#### `GET /admin/clients/{id}` — Detalle con todos sus procesos

---

### 4.8 Kanban — Pipeline de Compra

#### `GET /admin/purchase-processes`
**Query params:** `status`, `agent_id`, `limit`, `offset`

**Valores de `status`:** `lead`, `visita`, `interes`, `pre_aprobacion`, `avaluo`, `credito`, `docs_finales`, `escrituras`, `cerrado`

**Response 200:**
```json
{
  "count": 40,
  "results": [{
    "id": 1,
    "status": "visita",
    "overall_progress": 11,
    "client": { "id": 5, "name": "Juan Pérez", "avatar": null },
    "property": { "id": 1, "title": "Casa en Bosques", "image": "..." },
    "agent": { "id": 1, "name": "Alejandro Torres" },
    "created_at": "2026-02-01T08:00:00Z",
    "updated_at": "2026-02-10T15:00:00Z"
  }]
}
```

#### `POST /admin/purchase-processes`
```json
{ "property_id": 1, "client_membership_id": 10, "agent_membership_id": 3, "notes": "..." }
```

#### `PATCH /admin/purchase-processes/{id}/status` ← mover tarjeta Kanban
```json
{ "status": "interes", "notes": "Cliente confirmó interés" }
```
**Response:** `{ "id": 1, "status": "interes", "overall_progress": 22, "updated_at": "..." }`
**Nota:** Si `status=cerrado` requerir también `sale_price` y `payment_method`.

---

### 4.9 Pipeline de Venta

#### `GET /admin/sale-processes`
**Query params:** `status`, `agent_id`, `limit`, `offset`

**Valores de `status`:** `contacto_inicial`, `evaluacion`, `valuacion`, `presentacion`, `firma_contrato`, `marketing`, `publicacion`

#### `POST /admin/sale-processes`
```json
{ "property_id": 3, "client_membership_id": 10, "agent_membership_id": 3, "notes": "..." }
```

#### `PATCH /admin/sale-processes/{id}/status`
```json
{ "status": "evaluacion", "notes": "Agente visitó la propiedad" }
```

---

### 4.10 Seller Leads (gestión admin)

#### `GET /admin/seller-leads`
**Query params:** `status`, `search`, `limit`, `offset`

**Valores de `status`:** `new`, `contacted`, `visit_scheduled`, `converted`, `discarded`

**Response 200:**
```json
{
  "count": 15,
  "results": [{
    "id": 1, "full_name": "Roberto Méndez", "email": "roberto@gmail.com",
    "phone": "+52 272 111 2222", "property_type": "house",
    "location": "Orizaba, Veracruz", "expected_price": "3000000.00",
    "status": "new", "assigned_agent": null, "created_at": "2026-02-27T08:00:00Z"
  }]
}
```

#### `PATCH /admin/seller-leads/{id}`
```json
{ "status": "contacted", "assigned_agent_membership_id": 3, "notes": "..." }
```

#### `POST /admin/seller-leads/{id}/convert` ← nuevo endpoint no implementado en front
```json
{ "agent_membership_id": 3, "notes": "Propiedad aprobada, iniciando proceso de venta" }
```
**Response 201:** `{ "property_id": 5, "sale_process_id": 3, "message": "..." }`

---

### 4.11 Historial de ventas

**Problema:** El front usa `/admin/sales/history` — **el endpoint correcto es `/admin/history`**.

#### `GET /admin/history`
**Query params:** `zone`, `property_type`, `payment_method`, `search`, `date_from`, `date_to`, `limit`, `offset`

**Response 200:**
```json
{
  "count": 20,
  "results": [{
    "id": 1,
    "property": { "title": "Casa en Bosques de Orizaba", "property_type": "house", "zone": "Norte" },
    "client": { "name": "Juan Pérez" },
    "agent": { "name": "Alejandro Torres" },
    "sale_price": "2400000.00",
    "payment_method": "Crédito hipotecario",
    "closed_at": "2026-02-20T15:00:00Z"
  }]
}
```

---

### 4.12 Insights

#### `GET /admin/insights?period={month|quarter|year|all}`

**Response 200:**
```json
{
  "period": "month",
  "sales_by_month": [{ "month": "2026-01", "count": 3, "total_amount": "7200000.00" }],
  "distribution_by_type": [{ "property_type": "house", "count": 15, "percentage": 60.0 }],
  "activity_by_zone": [{ "zone": "Norte", "views": 1200, "leads": 15, "sales": 5 }],
  "top_agents": [{ "id": 1, "name": "Alejandro Torres", "sales_count": 8, "leads_count": 12, "score": "4.50" }],
  "summary": { "total_properties": 25, "total_sales": 20, "total_revenue": "48000000.00", "active_leads": 15 }
}
```

---

## 5. MyAccount — Agente

**Base backend:** `/api/v1/agent`
**Permisos:** Bearer token con `role=agent`

### 5.1 Archivos a modificar

| Archivo | Tipo de cambio |
|---|---|
| `src/myAccount/agent/api/agent.api.ts` | Quitar prefijo `/api/`, corregir ruta de status, agregar dashboard |
| `src/myAccount/agent/types/agent.types.ts` | Alinear tipos con respuesta real del back |
| `src/myAccount/agent/actions/get-agent-properties.actions.ts` | Parsear respuesta paginada |
| `src/myAccount/agent/actions/get-agent-appointments.actions.ts` | Parsear respuesta paginada |

---

### 5.2 `GET /agent/dashboard`

**Endpoint correcto:** `/agent/dashboard` *(no existe en el front actualmente)*

**Response 200:**
```json
{
  "agent": { "id": 1, "name": "Alejandro Torres", "avatar": "...", "zone": "Norte", "score": "4.50" },
  "stats": { "active_leads": 3, "today_appointments": 2, "month_sales": 1 }
}
```

---

### 5.3 `GET /agent/properties`

**Endpoint actual:** `/api/agent/properties` ← quitar `/api/`
**Endpoint correcto:** `/agent/properties`

**Response 200:**
```json
{
  "count": 8,
  "results": [{
    "id": 1,
    "title": "Casa en Bosques de Orizaba",
    "address": "Calle Pino 45, Col. Bosques",
    "price": "2500000.00",
    "property_type": "house",
    "status": "disponible",
    "image": "...",
    "leads_count": 3,
    "assigned_at": "2026-01-15T10:00:00Z"
  }]
}
```

### 5.4 Mapeo de campos — AgentProperty

| Front (`AgentProperty`) | Back (`results[]`) | Acción |
|---|---|---|
| `id` (string) | `id` (number) | Cambiar tipo a `number` |
| `title` | `title` | ✅ Igual |
| `location` | `address` | Renombrar |
| `price` | `price` (string `"2500000.00"`) | Formatear en front |
| `image` | `image` | ✅ Igual |
| `leads` | `leads_count` | Renombrar |
| `status` | `status` (en inglés: `"disponible"`, etc.) | ✅ Igual (ya en español en el back) |

---

### 5.5 `GET /agent/properties/{id}/leads`

**Endpoint actual:** `/api/agent/properties/${id}/leads` ← quitar `/api/`
**Endpoint correcto:** `/agent/properties/{id}/leads`

**Response 200:**
```json
{
  "count": 3,
  "results": [{
    "id": 1,
    "status": "visita",
    "overall_progress": 11,
    "client": { "name": "Juan Pérez", "email": "juan@gmail.com", "phone": "+52 272 111 3333" },
    "created_at": "2026-02-01T08:00:00Z",
    "updated_at": "2026-02-10T15:00:00Z"
  }]
}
```

### 5.6 Mapeo de campos — AgentLead

| Front (`AgentLead`) | Back (`results[]`) | Acción |
|---|---|---|
| `id` (string) | `id` (number) | Cambiar tipo a `number` |
| `name` | `client.name` | Renombrar (viene anidado) |
| `email` | `client.email` | Renombrar |
| `phone` | `client.phone` | Renombrar |
| `stage` (number) | `overall_progress` (number) | Renombrar |
| `lastContact` | — | **No existe en el back** — eliminar o calcular de `updated_at` |
| `interestLevel` | — | **No existe en el back** — eliminar o derivar de `status` |

---

### 5.7 `GET /agent/appointments`

**Endpoint actual:** `/api/agent/appointments` ← quitar `/api/`
**Endpoint correcto:** `/agent/appointments`
**Query params:** `status`, `date`, `limit`, `offset`

**Response 200:**
```json
{
  "count": 12,
  "results": [{
    "id": 1,
    "matricula": "CLI-2026-001",
    "scheduled_date": "2026-03-15",
    "scheduled_time": "10:00:00",
    "duration_minutes": 60,
    "status": "programada",
    "client_name": "María García",
    "client_phone": "+52 272 987 6543",
    "property": { "id": 1, "title": "Casa en Bosques" }
  }]
}
```

### 5.8 Mapeo de campos — AgentAppointment

| Front (`AgentAppointment`) | Back (`results[]`) | Acción |
|---|---|---|
| `id` (string) | `id` (number) | Cambiar tipo a `number` |
| `client` (string) | `client_name` (string) | Renombrar |
| `property` (string) | `property.title` (string anidada) | Extraer: `property.title` |
| `date` | `scheduled_date` | Renombrar |
| `time` | `scheduled_time` (formato `"10:00:00"`) | Renombrar + formatear |
| `status` | `status` | ✅ Valores compatibles |
| — | `matricula` | Agregar al tipo |
| — | `duration_minutes` | Agregar al tipo |
| — | `client_phone` | Agregar al tipo |

---

### 5.9 `PATCH /agent/appointments/{id}/status`

**Endpoint actual:** `PATCH /api/agent/appointments/${id}` con `{ status }`
**Endpoint correcto:** `PATCH /agent/appointments/{id}/status`
**Body:**
```json
{ "status": "confirmada", "notes": "Llamé al cliente, confirmó asistencia" }
```
**Transiciones válidas:** `programada → confirmada → en_progreso → completada | cancelada | no_show | reagendada`

---

## 6. MyAccount — Cliente

**Base backend:** `/api/v1/client`
**Permisos:** Bearer token con `role=client`

### 6.1 Archivos a modificar

| Archivo | Tipo de cambio |
|---|---|
| `src/myAccount/client/api/client.api.ts` | Corregir todas las rutas (`/api/user/...` → `/client/...`) |
| `src/myAccount/client/types/client.types.ts` | Renombrar todos los campos a snake_case, corregir tipos |
| `src/myAccount/client/actions/get-client-profile.actions.ts` | Parsear respuesta real |
| `src/myAccount/client/actions/get-client-properties-sale.actions.ts` | Adaptar a nueva estructura |
| `src/myAccount/client/actions/get-client-properties-buy.actions.ts` | Adaptar a nueva estructura |
| `src/myAccount/client/actions/get-client-property-files.actions.ts` | Cambiar endpoint + parsear |
| `src/myAccount/client/actions/upload-client-property-files.actions.ts` | Cambiar endpoint |
| `src/myAccount/client/actions/get-client-recent-activity.actions.ts` | Cambiar a usar `/client/dashboard` |

---

### 6.2 `GET /client/dashboard`

**Endpoint actual front:** `/api/user/recent-activity` ← incorrecto
**Endpoint correcto:** `/client/dashboard`

**Response 200:**
```json
{
  "client": { "name": "Juan Pérez", "avatar": null, "city": "Orizaba" },
  "credit_score": null,
  "recent_activity": [
    { "type": "purchase_status_change", "description": "Tu proceso de compra avanzó a Visita", "created_at": "2026-02-10T15:00:00Z" }
  ],
  "sale_processes_preview": [{ "id": 1, "property_title": "Casa propia", "status": "marketing", "image": "..." }],
  "purchase_processes_preview": [{ "id": 1, "property_title": "Casa en Bosques", "status": "visita", "overall_progress": 11, "image": "..." }]
}
```

### 6.3 Mapeo de campos — RecentActivityItem

| Front (`RecentActivityItem`) | Back (`recent_activity[]`) | Acción |
|---|---|---|
| `name` | `type` (e.g. `"purchase_status_change"`) | Renombrar + humanizar |
| `descripction` (typo) | `description` | Renombrar (corregir typo) |
| `time` (number, horas) | `created_at` (ISO datetime) | Renombrar + calcular tiempo relativo |

---

### 6.4 `GET /client/sales` — Propiedades en venta

**Endpoint actual:** `/api/user/properties-sale/` ← incorrecto
**Endpoint correcto:** `/client/sales`

**Response 200:**
```json
{
  "stats": {
    "total_properties": 1,
    "total_views": 230,
    "total_interested": 4,
    "total_value": "3000000.00"
  },
  "results": [{
    "id": 1,
    "property": { "id": 3, "title": "Casa propia", "address": "...", "price": "3000000.00", "status": "documentacion", "image": "..." },
    "status": "marketing",
    "progress_step": 6,
    "views": 230,
    "interested": 4,
    "days_listed": 38,
    "trend": "up",
    "agent": { "name": "Alejandro Torres" }
  }]
}
```

### 6.5 Mapeo de campos — PropertySaleSummary / PropertiesSaleResponse

| Front | Back | Acción |
|---|---|---|
| `PropertiesSaleResponse.propertiesAmount` | `stats.total_properties` | Renombrar |
| `PropertiesSaleResponse.totalViews` | `stats.total_views` | Renombrar |
| `PropertiesSaleResponse.interestedAmount` | `stats.total_interested` | Renombrar |
| `PropertiesSaleResponse.totalValue` | `stats.total_value` (string) | Renombrar + parsear |
| `PropertiesSaleResponse.properties` | `results` | Renombrar |
| `PropertySaleSummary.title` | `property.title` | Extraer del objeto anidado |
| `PropertySaleSummary.address` | `property.address` | Extraer |
| `PropertySaleSummary.price` | `property.price` | Extraer |
| `PropertySaleSummary.image` | `property.image` | Extraer |
| `PropertySaleSummary.status` | `status` (del proceso) | ✅ Mismo nivel |
| `PropertySaleSummary.views` | `views` | ✅ Igual |
| `PropertySaleSummary.interested` | `interested` | ✅ Igual |
| `PropertySaleSummary.daysListed` | `days_listed` | Renombrar |
| `PropertySaleSummary.trend` (number) | `trend` (string `"up"/"down"`) | Cambiar tipo + parsear |
| `PropertySaleSummary.progressStep` | `progress_step` | Renombrar |

---

### 6.6 `GET /client/sales/{process_id}` — Detalle proceso de venta

**Endpoint actual:** `/api/user/property-sale/${id}` ← incorrecto
**Endpoint correcto:** `/client/sales/{process_id}`

**Response 200:**
```json
{
  "id": 1, "status": "marketing",
  "property": { "id": 3, "title": "Casa propia", "image": "..." },
  "agent": { "name": "Alejandro Torres", "phone": "+52 272 123 4567", "email": "alejandro@..." },
  "stages": [
    { "name": "Contacto Inicial", "status": "completed", "completed_at": "2026-01-20T08:00:00Z" },
    { "name": "Marketing", "status": "current", "completed_at": null },
    { "name": "Publicación", "status": "pending", "completed_at": null }
  ],
  "history": [{ "previous_status": "firma_contrato", "new_status": "marketing", "changed_at": "...", "notes": "..." }]
}
```

---

### 6.7 `GET /client/purchases` — Propiedades en compra

**Endpoint actual:** `/api/user/properties-buys/` ← incorrecto
**Endpoint correcto:** `/client/purchases`

**Response 200:**
```json
{
  "count": 2,
  "results": [{
    "id": 1,
    "status": "visita",
    "overall_progress": 11,
    "process_stage": "Visita",
    "property": { "id": 1, "title": "Casa en Bosques de Orizaba", "address": "...", "price": "2500000.00", "image": "..." },
    "agent": { "name": "Alejandro Torres" },
    "documents_count": 2,
    "created_at": "2026-02-01T08:00:00Z"
  }]
}
```

### 6.8 Mapeo de campos — PropertyBuySummary

| Front | Back | Acción |
|---|---|---|
| `title` | `property.title` | Extraer |
| `address` | `property.address` | Extraer |
| `price` | `property.price` | Extraer + formatear |
| `image` | `property.image` | Extraer |
| `status` | `status` (proceso) | ✅ Mismo nivel |
| `agent_name` | `agent.name` | Renombrar + extraer |
| `overallProgress` (string `"33%"`) | `overall_progress` (number `33`) | Renombrar + formatear |
| `processStage` | `process_stage` | Renombrar |
| `fileNames` (string[]) | `documents_count` (number) | Cambiar: el back da el conteo, no los nombres |

---

### 6.9 `GET /client/purchases/{process_id}` — Detalle proceso de compra

**Response 200:**
```json
{
  "id": 1, "status": "pre_aprobacion", "overall_progress": 33, "process_stage": "Pre-Aprobación",
  "property": { "id": 1, "title": "...", "price": "2500000.00", "image": "..." },
  "agent": { "name": "Alejandro Torres", "phone": "+52...", "email": "alejandro@..." },
  "steps": [
    { "key": "lead", "label": "Lead", "progress": 0, "status": "completed", "allow_upload": false },
    { "key": "pre_aprobacion", "label": "Pre-Aprobación", "progress": 33, "status": "current", "allow_upload": true },
    { "key": "credito", "label": "Crédito", "progress": 56, "status": "pending", "allow_upload": true }
  ],
  "documents": [
    { "id": 1, "name": "INE", "file_url": "...", "document_stage": "pre_aprobacion", "uploaded_at": "..." }
  ]
}
```

**Nota:** `allow_upload=true` solo en `pre_aprobacion`, `credito`, `docs_finales`. El front actual usa `PropertyFileItem` que es más simple — expandir el tipo.

---

### 6.10 `POST /client/purchases/{process_id}/documents` — Subir documentos

**Endpoint actual:** `POST /api/user/property-files/${propertyId}` ← incorrecto
**Endpoint correcto:** `POST /client/purchases/{process_id}/documents`

**Tipo:** `multipart/form-data`
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

**Nota crítica:** El endpoint recibe `process_id` (ID del `PurchaseProcess`), **no** `property_id`. La acción actual `uploadClientPropertyFilesAction(propertyId, files)` debe cambiar su parámetro a `processId`.

**Cómo construir el FormData:**
```typescript
const formData = new FormData();
files.forEach((f) => {
  formData.append("file", f);
  formData.append("name", f.name.replace(/\.[^/.]+$/, "")); // nombre sin extensión
});
```

---

### 6.11 `GET /client/purchases/{process_id}/documents` — Listar documentos

**Endpoint actual:** `GET /api/user/property-files/${propertyId}` ← incorrecto
**Endpoint correcto:** `GET /client/purchases/{process_id}/documents`
*(Los documentos vienen también dentro de `GET /client/purchases/{process_id}` en el campo `documents`)*

---

### 6.12 `GET /client/profile` — Perfil

**Endpoint actual:** `/api/user/profile` ← incorrecto
**Endpoint correcto:** `/client/profile`

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

### 6.13 Mapeo de campos — UserProfile

| Front (`UserProfile`) | Back | Acción |
|---|---|---|
| `Name` | `first_name` + `last_name` | Separar / unir |
| `PhoneMunber` (typo) / `PhoneNumber` | `phone` | Renombrar + corregir typo |
| `Email` | `email` | Cambiar a minúscula |
| `City` | `city` | Cambiar a minúscula |
| `NewProperties` | — | No en perfil. Viene de preferencias (ver §6.14) |
| `PriceUpdates` | — | No en perfil. Viene de preferencias |
| `AppointmentReminders` | — | No en perfil. Viene de preferencias |
| `Offers` | — | No en perfil. Viene de preferencias |

**Nota:** El `UserProfile` del front mezcla datos del perfil + preferencias de notificación. En el back son dos endpoints separados.

---

### 6.14 Preferencias de notificación

#### `GET /client/notification-preferences`
**Response:**
```json
{ "new_properties": true, "price_updates": true, "appointment_reminders": true, "offers": false }
```

#### `PUT /client/notification-preferences`
**Body:**
```json
{ "new_properties": true, "price_updates": false, "appointment_reminders": true, "offers": false }
```

### 6.15 Mapeo de campos — Preferencias

| Front (`UserProfile`) | Back | Acción |
|---|---|---|
| `NewProperties` | `new_properties` | Renombrar a snake_case |
| `PriceUpdates` | `price_updates` | Renombrar |
| `AppointmentReminders` | `appointment_reminders` | Renombrar |
| `Offers` | `offers` | Cambiar a minúscula |

---

## 7. CreditFlow

**Estado:** 100% UI local — sin endpoints de backend.
El flujo de simulación de crédito (ingreso, edad, ahorro, deudas → cálculo de score) es puramente client-side.
**No requiere cambios de API en esta fase.**

---

## 8. Resumen de correcciones por archivo

### `src/shared/api/axios.instance.ts`
- [ ] Agregar `baseURL = VITE_API_BASE_URL || "http://localhost:8000/api/v1"`
- [ ] Agregar interceptor de request (attach Bearer token de localStorage)
- [ ] Agregar interceptor de response (refresh automático en 401)
- [ ] Agregar named export `export { axiosInstance }`

### `src/auth/api/auth.api.ts`
- [ ] `logout()`: agregar body `{ refresh: localStorage.getItem("refresh_token") }`
- [ ] `refreshToken()`: agregar body `{ refresh: ... }`

### `src/auth/actions/verify-otp.actions.ts`
- [ ] Renombrar `accessToken` → `access` en el tipo
- [ ] Guardar `access` y `refresh` en localStorage tras éxito
- [ ] Agregar `user` al tipo de retorno

### `src/home/api/home.api.ts`
- [ ] Cambiar `FEATURED_PROPERTIES: "/api/properties"` → `"/public/properties"`

### `src/home/actions/get-featured-properties.actions.ts`
- [ ] Agregar `featured=true` a los params
- [ ] Parsear respuesta paginada `{ count, results }`
- [ ] Mapear campos del back → tipos del front (bedrooms→beds, etc.)

### `src/buy/api/buy.api.ts`
- [ ] `PROPERTIES: "/api/properties"` → `"/public/properties"`
- [ ] `PROPERTY_DETAIL: (id) => "/api/properties/${id}/"` → `"/public/properties/${id}"`
- [ ] Agregar `APPOINTMENT: (id) => "/public/properties/${id}/appointment"`
- [ ] Agregar `SLOTS: "/public/appointment/slots"`

### `src/buy/actions/get-properties.actions.ts`
- [ ] Parsear respuesta paginada
- [ ] Traducir valores de filtros (casa→house, nueva→new, etc.)
- [ ] Mapear campos

### `src/buy/actions/get-property-detail.actions.ts`
- [ ] Mapear campos (beds, baths, sqm, nearby-places, agent.phone tipo, images array)

### `src/sell/api/sell.api.ts`
- [ ] `SUBMIT_LEAD: "/api/seller-leads/"` → `"/public/seller-leads"`

### `src/sell/actions/submit-seller-lead.actions.ts`
- [ ] Traducir camelCase → snake_case en el body
- [ ] Traducir property_type al inglés
- [ ] Parsear response real `{ id, full_name, status, message }`

### `src/myAccount/admin/api/admin.api.ts`
- [ ] `getSalesHistory()`: `/admin/sales/history` → `/admin/history`
- [ ] `updateProperty()`: PUT → PATCH
- [ ] `assignAgent()`: eliminar. Reemplazar con `createAssignment()` → `POST /admin/assignments`
- [ ] Agregar: `getSellerLeads()`, `patchSellerLead()`, `convertSellerLead()`
- [ ] Agregar: `getPurchaseProcesses()`, `updatePurchaseStatus()`, `getSaleProcesses()`, `updateSaleStatus()`
- [ ] Agregar: `getAssignments()`, `createAssignment()`, `patchAssignment()`, `deleteAssignment()`
- [ ] Agregar: `getAgentSchedules()`, `createAgentSchedule()`, `deleteAgentSchedule()`

### `src/myAccount/agent/api/agent.api.ts`
- [ ] Quitar prefijo `/api/` en todas las rutas
- [ ] `updateAppointmentStatus()`: PATCH `/agent/appointments/${id}` → `/agent/appointments/${id}/status`
- [ ] Agregar `getDashboard()` → `GET /agent/dashboard`

### `src/myAccount/agent/types/agent.types.ts`
- [ ] `AgentProperty.id`: `string` → `number`
- [ ] `AgentProperty.location` → `address`
- [ ] `AgentProperty.leads` → `leads_count`
- [ ] `AgentAppointment.id`: `string` → `number`
- [ ] `AgentAppointment.client` → `client_name`
- [ ] `AgentAppointment.property` (string) → `property: { id, title }` + extraer título
- [ ] `AgentAppointment.date` → `scheduled_date`
- [ ] `AgentAppointment.time` → `scheduled_time`
- [ ] `AgentLead.stage` → `overall_progress`
- [ ] Eliminar `lastContact` y `interestLevel` (no existen en el back)
- [ ] Agregar `AgentDashboard` type

### `src/myAccount/client/api/client.api.ts`
- [ ] `getPropertiesSale()`: `/api/user/properties-sale/` → `/client/sales`
- [ ] `getPropertySaleDetail(id)`: `/api/user/property-sale/${id}` → `/client/sales/${id}`
- [ ] `getPropertiesBuys()`: `/api/user/properties-buys/` → `/client/purchases`
- [ ] `getPropertyFiles(processId)`: `/api/user/property-files/${propertyId}` → `/client/purchases/${processId}/documents`
- [ ] `uploadPropertyFiles(processId, formData)`: cambiar endpoint + agregar campo `name`
- [ ] `getUserProfile()`: `/api/user/profile` → `/client/profile`
- [ ] `getRecentActivity()`: `/api/user/recent-activity` → `/client/dashboard`
- [ ] Agregar `updateProfile(data)` → `PATCH /client/profile`
- [ ] Agregar `getNotificationPreferences()` → `GET /client/notification-preferences`
- [ ] Agregar `updateNotificationPreferences(data)` → `PUT /client/notification-preferences`

### `src/myAccount/client/types/client.types.ts`
- [ ] `UserProfile`: Convertir todos los campos a `camelCase` o `snake_case` (elegir uno y ser consistente)
- [ ] Separar `UserProfile` en `ClientProfile` + `NotificationPreferences`
- [ ] `PropertySaleSummary.daysListed` → `days_listed`
- [ ] `PropertySaleSummary.progressStep` → `progress_step`
- [ ] `PropertySaleSummary.trend` (number) → `trend: "up" | "down" | string`
- [ ] `PropertyBuySummary.overallProgress` → `overall_progress: number`
- [ ] `PropertyBuySummary.processStage` → `process_stage`
- [ ] `PropertyBuySummary.fileNames` → `documents_count: number`
- [ ] `RecentActivityItem.descripction` → `description` (corregir typo)
- [ ] `RecentActivityItem.time` (number) → `created_at: string`
- [ ] Agregar `Step.key`, `Step.progress`, `Step.allow_upload` (el back los incluye)

---

## 9. Orden de conexión recomendado

1. **`shared/api/axios.instance.ts`** — base de todo, hacer primero
2. **Auth** — sin esto los tokens no se guardan y todo lo protegido falla
3. **`/public/properties`** — home y buy (sin auth, validar que el back esté corriendo)
4. **`/public/seller-leads`** — sell (sin auth)
5. **`/public/appointment/slots` + `/public/properties/{id}/appointment`** — detalle propiedad
6. **`/client/*`** — flujos de cliente (requiere auth)
7. **`/agent/*`** — flujos de agente (requiere auth)
8. **`/admin/*`** — flujos de admin (requiere auth)
