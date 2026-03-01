# PRD — Avakanta: Plataforma Inmobiliaria Multi-Tenant

> Versión: 1.0
> Fecha: 2026-02-26
> Autor: Equipo Avakanta
> Stack Backend: Django 5 + Django REST Framework + PostgreSQL
> Stack Frontend: React 18 + TypeScript + TanStack Query + shadcn/ui

---

## 1. Visión General

Avakanta es una plataforma tecnológica inmobiliaria (proptech) diseñada para servir a múltiples inmobiliarias bajo un modelo multi-tenant. Cada inmobiliaria opera de forma independiente dentro de la plataforma, con su propio equipo, propiedades, clientes y configuraciones.

La plataforma cubre el ciclo completo del negocio inmobiliario: captación de vendedores, publicación de propiedades, búsqueda y compra, agendamiento de citas, y seguimiento de procesos de compra/venta.

El primer tenant será **Altas Montañas**, una inmobiliaria enfocada en propiedades de la región de las altas montañas de Veracruz.

---

## 2. Arquitectura Multi-Tenant

La plataforma utiliza una base de datos compartida con columna discriminadora (`tenant_id`). Todas las inmobiliarias comparten la misma base de datos y las mismas tablas, pero cada registro está asociado a un tenant específico.

Reglas fundamentales:
- Un tenant NUNCA puede ver ni acceder a datos de otro tenant.
- El `tenant_id` se determina por el contexto del usuario autenticado, nunca por el request del cliente.
- Los catálogos globales (países, estados, ciudades, amenidades) son compartidos entre todos los tenants.
- Un mismo usuario (email) puede pertenecer a diferentes tenants con diferentes roles.

---

## 3. Roles y Accesos

La plataforma tiene 3 roles. El rol es por tenant, no global. Un mismo usuario puede ser cliente en una inmobiliaria y agente en otra.

### 3.1 Administrador (`admin`)
Es el dueño o encargado de la inmobiliaria. Tiene acceso total al panel de administración.

Puede:
- Gestionar propiedades (crear, editar, eliminar, subir documentos e imágenes)
- Gestionar agentes (crear, editar, eliminar, asignar horarios)
- Gestionar citas (crear, editar, cancelar, ver calendario)
- Asignar propiedades a agentes y desasignar/transferir
- Ver y gestionar clientes con su pipeline de compra y venta
- Mover clientes entre etapas del pipeline (Kanban drag & drop)
- Ver historial de ventas completadas con filtros
- Ver insights y analytics (gráficas de ventas, distribución por tipo, heatmap por zona, ranking de agentes)
- Ver log de auditoría de acciones
- Configurar ajustes de la inmobiliaria

### 3.2 Agente Inmobiliario (`agent`)
Es el agente de campo que gestiona propiedades y atiende clientes.

Puede:
- Ver propiedades asignadas con cantidad de leads por propiedad
- Ver y gestionar sus citas (Kanban por estado: programada, confirmada, en progreso, completada, cancelada, reagendada)
- Ver leads/prospectos de cada propiedad asignada
- Actualizar estado de citas
- Ver su dashboard con stats (leads activos, citas del día, ventas del mes)

### 3.3 Cliente (`client`)
Es la persona que compra o vende propiedades a través de la plataforma.

Puede:
- Ver su dashboard con resumen general
- Ver sus propiedades en proceso de venta (con stats: vistas, interesados, días listados, tendencia)
- Ver sus propiedades en proceso de compra (con timeline de etapas y progreso)
- Subir documentos requeridos en etapas específicas del proceso de compra
- Ver y editar su perfil (nombre, teléfono, ciudad)
- Configurar preferencias de notificaciones
- Ver actividad reciente

---

## 4. Pantallas Públicas (Sin autenticación)

### 4.1 Home (`/`)
Página principal de la plataforma.
- Muestra propiedades destacadas (cards con imagen, precio, título, dirección, recámaras, baños, m²)
- Hero section con CTAs a "Buscar" (`/comprar`) y "Vender" (`/vender`)
- Las propiedades destacadas se marcan con el flag `is_featured` desde el admin

### 4.2 Comprar (`/comprar`)
Listado de propiedades disponibles para compra con sistema de filtros.

Filtros disponibles:
- Zona: Norte, Sur, Centro, Oriente, Poniente
- Rango de precio: $0 - $20,000,000 MXN
- Tipo: Casa, Departamento, Terreno, Comercial
- Amenidades: Alberca, Gimnasio, Seguridad, Elevador, Estacionamiento, Jardín, Roof Garden
- Condición: Nueva, Semi-nueva, Usada

Paginación con `limit` y `offset`.

### 4.3 Detalle de Propiedad (`/propiedad/:id`)
Vista completa de una propiedad individual.

Muestra:
- Galería de imágenes
- Precio, título, dirección
- Características: recámaras, baños, m², verificada, estado
- Descripción completa
- Video tour (YouTube embed por `video_id`)
- Mapa de ubicación (Google Maps embed por coordenadas lat/lng)
- Lugares cercanos
- Datos del agente asignado (nombre, foto, teléfono, email)
- Formulario para agendar cita con el agente

Formulario de cita:
- Fecha
- Hora (slots de 09:00 a 18:00)
- Nombre del visitante
- Teléfono
- Email

### 4.4 Vender (`/vender`)
Página de captación de vendedores (seller leads).

- Hero section con CTA para abrir formulario
- Video informativo en modal
- Formulario de 3 pasos:
  - Paso 1 — Datos de la propiedad: tipo, ubicación, m², recámaras, baños
  - Paso 2 — Detalles: precio esperado
  - Paso 3 — Datos de contacto: nombre completo, teléfono, email

Al enviar, se crea un `seller_lead` con status `new`. El admin lo revisa y decide si convertirlo en propiedad + proceso de venta.

### 4.5 Crédito (`/credito`)
Simulador de crédito hipotecario.

Flujo de 4 vistas:
1. **Simulación:** Formulario con ingreso mensual, edad, ahorro para enganche, deudas mensuales
2. **Resultado:** Monto pre-aprobado y score crediticio calculado
3. **Documentos:** Subida de 4 documentos (INE, comprobantes de ingreso, comprobante de domicilio, estado de cuenta bancario)
4. **Seguimiento:** Timeline del proceso crediticio

> [PENDIENTE] Actualmente mock en el frontend. Se implementará cuando se defina la lógica de scoring.

### 4.6 Servicios (`/servicios`)
Página informativa estática sobre los servicios financieros de Avakanta. Sin interacción con el backend.

---

## 5. Panel de Administración (Admin)

Accesible desde `/mi-cuenta` cuando el usuario autenticado tiene `role = admin`.

El panel usa tabs/secciones internas (no cambia la URL).

### 5.1 Propiedades
- Listado de propiedades del tenant con: título, dirección, precio, tipo, estado, agente asignado, documentos
- Crear propiedad nueva (formulario modal)
- Editar propiedad existente
- Eliminar propiedad (con confirmación)
- Subir documentos a una propiedad
- Buscar propiedades por texto

### 5.2 Agentes
- Tarjetas de agentes con: nombre, email, teléfono, zona, propiedades asignadas, ventas, score
- Crear, editar, eliminar agentes
- Editor de horario semanal por agente ("Scheduler Pro"):
  - Bloques de tiempo por día (TimeBlock: start, end)
  - Múltiples breaks por horario (comida, café, descanso)
  - Horarios con vigencia (valid_from / valid_until)
  - Prioridad entre horarios

### 5.3 Citas
- Vista de calendario mensual
- Lista de citas del día seleccionado
- Crear cita: seleccionar cliente (por nombre o matrícula CLI-YYYY-NNN), propiedad, agente, fecha, hora, duración
- Editar y cancelar citas
- Verificación automática de disponibilidad:
  - Considera horario del agente (agent_schedules)
  - Considera breaks del horario (schedule_breaks)
  - Considera indisponibilidades (agent_unavailabilities)
  - Considera citas existentes para evitar solapamientos
  - Respeta duración de la cita

### 5.4 Asignar
- Lista de propiedades sin asignar
- Lista de agentes disponibles
- Mapa visual de asignaciones actuales
- Asignar propiedad a agente
- Desasignar propiedad de agente
- Transferir propiedad entre agentes
- Una propiedad puede tener varios agentes asignados
- Campo `is_visible` controla cuáles se muestran en el frontend público

### 5.5 Clientes
- Directorio de clientes del tenant
- Por cada cliente: propiedades en compra y en venta con su pipeline de etapas
- Documentos por propiedad
- Buscar clientes

Pipeline de compra (9 etapas):
Lead → Visita → Interés → Pre-Aprobación → Avalúo → Crédito → Docs Finales → Escrituras → Cerrado

Pipeline de venta (7 etapas):
Contacto Inicial → Evaluación → Valuación → Presentación → Firma Contrato → Marketing → Publicación

### 5.6 Kanban
- Tablero kanban con 9 columnas (etapas del pipeline de compra)
- Tarjetas de clientes arrastrables entre columnas
- Desktop: drag & drop con HTML5 DragEvent API
- Mobile: vista de columna única con swipe
- Al mover una tarjeta se actualiza el status del `purchase_process` y se registra en `process_status_history`

### 5.7 Historial
- Lista de ventas completadas (purchase_processes con status = cerrado)
- Datos: precio de venta, fecha, agente, método de pago, zona
- Filtros: zona, tipo de propiedad, método de pago
- Búsqueda por texto

### 5.8 Insights
- Gráfica de barras: ventas mensuales (Recharts BarChart)
- Gráfica de pie: distribución por tipo de propiedad (Recharts PieChart)
- Heatmap: actividad por zona
- Ranking de top agentes
- Log de auditoría de acciones
- Selector de período: mes, trimestre, año, todo
- Exportación a PDF y Excel

---

## 6. Panel del Agente

Accesible desde `/mi-cuenta` cuando el usuario autenticado tiene `role = agent`.

### 6.1 Dashboard
- Header con stats: leads activos, citas del día, ventas del mes
- Nombre y datos del agente

### 6.2 Casas Asignadas
- Listado de propiedades asignadas al agente
- Cada tarjeta muestra: imagen, título, ubicación, precio, cantidad de leads, status
- Al hacer clic, ve los leads/prospectos de esa propiedad (datos de `purchase_processes` en etapa temprana)

### 6.3 Gestión de Citas
- Kanban de citas organizadas por estado
- Estados: programada, confirmada, en progreso, completada, cancelada, reagendada
- Puede cambiar el estado de una cita (mover entre columnas)

### 6.4 Configuración
- Botón de logout

---

## 7. Panel del Cliente

Accesible desde `/mi-cuenta` cuando el usuario autenticado tiene `role = client`.

### 7.1 Dashboard
- Score de crédito (widget visual)
- Actividad reciente (últimas acciones relacionadas con sus procesos)
- Vista previa de propiedades en venta
- Vista previa de propiedades en compra

### 7.2 Mis Ventas
- Stats generales: cantidad de propiedades, vistas totales, interesados, valor total
- Lista de propiedades en venta, cada una con:
  - Imagen, título, dirección, precio, status
  - Vistas, interesados, días listados
  - Tendencia (trend)
  - Progreso del proceso (progressStep)
- Detalle de propiedad en venta

### 7.3 Mis Compras
- Lista de propiedades en proceso de compra, cada una con:
  - Imagen, título, dirección, precio, status
  - Nombre del agente asignado
  - Progreso general (0-100%)
  - Etapa actual del proceso (processStage)
  - Archivos subidos
- Timeline visual con las etapas del proceso de compra
- Ciertas etapas permiten subir documentos (allowUpload = true)
- Subida de archivos en formato multipart/form-data

### 7.4 Configuración
- Editar perfil: nombre, teléfono, ciudad
- Toggle de preferencias de notificaciones:
  - Nuevas propiedades
  - Actualizaciones de precio
  - Recordatorios de citas
  - Ofertas
- Guardar cambios

---

## 8. Autenticación

### 8.1 Método principal: OTP por Email
1. Usuario ingresa su email
2. Se envía un código OTP de 6 dígitos al email
3. Usuario ingresa el código
4. Si es válido → autenticado
5. Se muestra selector de rol (si el usuario tiene múltiples roles en el tenant)

### 8.2 Métodos alternativos
- Login con Google (Google Identity / idToken)
- Login con Apple (Sign in with Apple / identityToken)

> [PENDIENTE] Los flujos de Google y Apple aún no están conectados en el frontend.

### 8.3 Sesión
- Autenticación basada en JWT (access token + refresh token)
- Access token: 2 horas de vida
- Refresh token: 7 días de vida, rotación automática
- El frontend debe implementar interceptor de Axios para renovar token automáticamente ante 401

### 8.4 Selector de Rol
Después de autenticarse, si el usuario tiene múltiples roles en el tenant, se le muestra un selector para elegir con qué rol desea ingresar. Según el rol seleccionado, se renderiza el panel correspondiente.

---

## 9. Sistema de Citas y Agenda

### 9.1 Configuración global del tenant
- Duración de slot por defecto (default: 60 minutos)
- Máximo de días de anticipación para agendar (default: 30)
- Mínimo de horas de anticipación (default: 24)
- Hora de inicio y fin de jornada (default: 09:00 - 18:00)

### 9.2 Horarios de agentes
- Cada agente puede tener múltiples horarios nombrados (ej: "Horario normal", "Horario verano")
- Cada horario define qué días aplica (lunes a domingo, con booleans)
- Cada horario tiene hora de inicio y fin
- Opcionalmente tiene break de comida (lunch_start, lunch_end)
- Adicionalmente puede tener múltiples breaks tipificados (comida, café, descanso, otro)
- Los horarios tienen vigencia (valid_from / valid_until) y prioridad
- Si dos horarios coinciden en un día, gana el de mayor prioridad

### 9.3 Indisponibilidades
- Se pueden registrar rangos de fechas donde el agente no está disponible
- Razones: vacaciones, incapacidad, asunto personal, capacitación, otro
- Sobreescriben cualquier horario activo en esas fechas

### 9.4 Verificación de disponibilidad
Al crear una cita, el sistema verifica:
1. Que el agente tenga un horario activo para ese día
2. Que la hora esté dentro del rango del horario
3. Que no caiga en un break
4. Que no haya una indisponibilidad registrada para esa fecha
5. Que no se solape con otra cita existente del agente (considerando duración)

### 9.5 Matrícula de cita
Cada cita recibe una matrícula única con formato `CLI-YYYY-NNN` (ej: CLI-2026-001). Se genera automáticamente. Sirve para buscar citas rápidamente en el admin.

---

## 10. Procesos de Compra

Un proceso de compra se crea cuando un prospecto formaliza su interés en comprar una propiedad. El proceso pasa por 9 etapas secuenciales:

| # | Etapa | Progreso | Descripción |
|---|---|---|---|
| 1 | Lead | 0% | Cliente interesado, prospecto inicial |
| 2 | Visita | 11% | Visita agendada o realizada a la propiedad |
| 3 | Interés | 22% | Cliente confirma interés formal |
| 4 | Pre-Aprobación | 33% | Pre-aprobación crediticia del cliente |
| 5 | Avalúo | 44% | Avalúo de la propiedad |
| 6 | Crédito | 56% | Trámite de crédito hipotecario |
| 7 | Docs Finales | 67% | Recopilación de documentos finales |
| 8 | Escrituras | 78% | Firma de escrituras |
| 9 | Cerrado | 100% | Venta completada |

Adicionalmente existe el estado `cancelado` que puede aplicarse en cualquier etapa.

Cuando un proceso llega a `cerrado`, se llenan los campos: `sale_price`, `payment_method`, `closed_at`.

Cada cambio de etapa se registra en `process_status_history` con: quién lo cambió, cuándo, de qué estado a qué estado.

Ciertas etapas permiten al cliente subir documentos (`allowUpload`). Los documentos se almacenan en `property_documents` vinculados al `purchase_process`.

---

## 11. Procesos de Venta

Un proceso de venta se crea cuando un cliente quiere vender su propiedad a través de la inmobiliaria. Puede originarse desde un `seller_lead` convertido o crearse directamente por el admin.

El proceso pasa por 7 etapas:

| # | Etapa | Descripción |
|---|---|---|
| 1 | Contacto Inicial | Primer contacto con el vendedor |
| 2 | Evaluación | Evaluación de la propiedad |
| 3 | Valuación | Tasación/valuación formal |
| 4 | Presentación | Presentación de propuesta al vendedor |
| 5 | Firma Contrato | Firma de contrato de exclusiva |
| 6 | Marketing | Preparación de fotos, descripción, marketing |
| 7 | Publicación | Propiedad publicada en la plataforma |

Adicionalmente existe el estado `cancelado`.

---

## 12. Captación de Vendedores (Seller Leads)

Flujo:
1. Visitante llena formulario en `/vender` → se crea `seller_lead` con status `new`
2. Admin revisa el lead y lo asigna a un agente → status `contacted`
3. Agente contacta al vendedor y evalúa la propiedad → status `in_review`
4. Si se aprueba:
   - Se crea usuario (si no existe) con role `client`
   - Se crea propiedad con `listing_type = pending_listing`
   - Se crea `sale_process`
   - Status del lead → `converted`
5. Si no se aprueba → status `rejected`

---

## 13. Reglas de Negocio Importantes

- Una propiedad puede estar asignada a varios agentes, pero el campo `is_visible` controla cuáles se muestran en el frontend público.
- Las propiedades tienen un contador de `views` que se incrementa cada vez que alguien visita el detalle.
- El `trend` de una propiedad se calcula comparando las vistas de los últimos 7 días vs los 7 anteriores.
- Los campos `daysListed`, `interested`, `trend`, `image`, `progressStep`, `address` son computados en el backend (serializer), no son columnas de la BD.
- El pipeline de compra del Kanban y el pipeline de la sección Clientes son la misma fuente de datos (`purchase_processes`), solo cambia la visualización.
- El historial de ventas es simplemente `purchase_processes` filtrados por `status = cerrado`.
- Los insights del admin se calculan con queries de agregación sobre las tablas existentes (no hay tablas de analytics separadas).

---

## 14. Integraciones Externas

| Servicio | Uso | Estado |
|---|---|---|
| YouTube | Video tours de propiedades (embed por video_id) | Implementado en front |
| Google Maps | Mapa de ubicación de propiedades (embed por lat/lng) | Implementado en front |
| Google Identity | Login con Google | [PENDIENTE] |
| Apple Sign In | Login con Apple | [PENDIENTE] |

---

## 15. Consideraciones Técnicas

- **Backend:** Django 5 + DRF, API REST pura (no hay templates Django)
- **Frontend:** React 18 + TypeScript, consume la API. Desarrollo independiente.
- **Auth:** JWT con django-rest-framework-simplejwt
- **Documentación API:** drf-spectacular genera OpenAPI spec + Swagger UI + ReDoc
- **Base de datos:** PostgreSQL
- **Multi-tenancy:** Shared database con tenant_id (no schemas separados)
- **Archivos:** Subida de imágenes y documentos via multipart/form-data
- **Paginación:** limit/offset
- **Filtros:** django-filter
- **CORS:** django-cors-headers
