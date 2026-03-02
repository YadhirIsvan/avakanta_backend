"""
Management command: seed_demo_data
Carga datos de prueba realistas para el tenant Altas Montañas.

Uso: python manage.py seed_demo_data
     python manage.py seed_demo_data --reset   # borra y recrea todo
"""
import random
from datetime import date, time, timedelta

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.appointments.models import AgentSchedule, Appointment, AppointmentSettings, ScheduleBreak
from apps.locations.models import Amenity, City, Country, State
from apps.notifications.models import Notification
from apps.properties.models import (
    Property,
    PropertyAmenity,
    PropertyAssignment,
    PropertyImage,
    PropertyNearbyPlace,
)
from apps.tenants.models import Tenant
from apps.transactions.models import PurchaseProcess, SaleProcess, SellerLead
from apps.users.models import AgentProfile, TenantMembership, User, UserNotificationPreferences
from core.utils import generate_matricula


# ---------------------------------------------------------------------------
# Datos de prueba
# ---------------------------------------------------------------------------

AGENTS_DATA = [
    {
        "first_name": "Sofía",
        "last_name": "Ramírez Vega",
        "email": "sofia.ramirez@altasmontanas.mx",
        "phone": "+52 55 1234 5678",
        "zone": "Norte",
        "bio": (
            "Especialista en propiedades residenciales en la zona Norte de la ciudad. "
            "Más de 8 años de experiencia en el mercado inmobiliario, con enfoque en "
            "familias que buscan su primera vivienda."
        ),
        "score": "4.85",
        "schedule": {
            "name": "Horario Normal L-V",
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "start_time": time(9, 0),
            "end_time": time(18, 0),
            "lunch_start": time(14, 0),
            "lunch_end": time(15, 0),
        },
    },
    {
        "first_name": "Carlos",
        "last_name": "Mendoza Ríos",
        "email": "carlos.mendoza@altasmontanas.mx",
        "phone": "+52 55 2345 6789",
        "zone": "Sur",
        "bio": (
            "Agente con 12 años de trayectoria en la zona Sur. Especializado en "
            "departamentos y propiedades de lujo. Miembro del top 3 de ventas de "
            "Altas Montañas por cuarto año consecutivo."
        ),
        "score": "4.92",
        "schedule": {
            "name": "Horario L-S",
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"],
            "start_time": time(9, 0),
            "end_time": time(17, 0),
            "lunch_start": time(13, 30),
            "lunch_end": time(14, 30),
        },
    },
    {
        "first_name": "Ana",
        "last_name": "Torres Salinas",
        "email": "ana.torres@altasmontanas.mx",
        "phone": "+52 55 3456 7890",
        "zone": "Centro",
        "bio": (
            "Experta en el Centro histórico y zonas comerciales. Arquitecta de "
            "formación, asesora a inversionistas en terrenos y desarrollos. "
            "Certificada por la AMPI."
        ),
        "score": "4.70",
        "schedule": {
            "name": "Horario M-V con mañana",
            "days": ["tuesday", "wednesday", "thursday", "friday"],
            "start_time": time(10, 0),
            "end_time": time(19, 0),
            "lunch_start": time(14, 30),
            "lunch_end": time(15, 30),
        },
    },
]

CLIENTS_DATA = [
    {
        "first_name": "Roberto",
        "last_name": "García López",
        "email": "roberto.garcia@gmail.com",
        "phone": "+52 55 4567 8901",
        "city": "Ciudad de México",
    },
    {
        "first_name": "Valentina",
        "last_name": "Cruz Herrera",
        "email": "vale.cruz@hotmail.com",
        "phone": "+52 55 5678 9012",
        "city": "Guadalajara",
    },
    {
        "first_name": "Miguel",
        "last_name": "Fernández Ortiz",
        "email": "miguel.fdz@outlook.com",
        "phone": "+52 55 6789 0123",
        "city": "Monterrey",
    },
    {
        "first_name": "Claudia",
        "last_name": "Morales Vázquez",
        "email": "claudia.morales@yahoo.com",
        "phone": "+52 55 7890 1234",
        "city": "Puebla",
    },
    {
        "first_name": "Andrés",
        "last_name": "Jiménez Soto",
        "email": "andres.jimenez@gmail.com",
        "phone": "+52 55 8901 2345",
        "city": "Ciudad de México",
    },
]

# Propiedades: (title, type, condition, listing_type, status, price, beds, baths, parking,
#               construction_sqm, land_sqm, street, number, neighborhood, zip, zone, lat, lng,
#               is_featured, amenities_idx, nearby_places)
PROPERTIES_DATA = [
    {
        "title": "Casa amplia en Lomas Verdes con jardín",
        "description": (
            "Hermosa casa de dos plantas en privada cerrada. Amplio jardín trasero, "
            "cocina integral remodelada y cuarto de servicio independiente. "
            "A 5 minutos del Parque Lomas y Soriana Norte."
        ),
        "property_type": "house",
        "property_condition": "semi_new",
        "listing_type": "sale",
        "status": "disponible",
        "price": "3850000.00",
        "bedrooms": 4,
        "bathrooms": 3,
        "parking_spaces": 2,
        "construction_sqm": "245.00",
        "land_sqm": "320.00",
        "address_street": "Calle Pinos",
        "address_number": "47",
        "address_neighborhood": "Lomas Verdes",
        "address_zip": "53120",
        "zone": "Norte",
        "latitude": "19.52341000",
        "longitude": "-99.24512000",
        "is_featured": True,
        "is_verified": True,
        "views": 142,
        "amenity_names": ["Jardín", "Estacionamiento", "Seguridad 24h"],
        "nearby_places": [
            ("Soriana Norte", "supermercado", "0.80"),
            ("Parque Lomas Verdes", "parque", "0.50"),
            ("Clínica del IMSS", "hospital", "1.20"),
        ],
        "agent_idx": 0,
    },
    {
        "title": "Departamento moderno con terraza en Polanco",
        "description": (
            "Departamento de lujo en el corazón de Polanco. Acabados de alta gama, "
            "terraza privada con vista a la ciudad. Edificio con amenidades completas. "
            "A pasos del parque Lincoln y restaurantes de alta cocina."
        ),
        "property_type": "apartment",
        "property_condition": "new",
        "listing_type": "sale",
        "status": "disponible",
        "price": "6200000.00",
        "bedrooms": 2,
        "bathrooms": 2,
        "parking_spaces": 1,
        "construction_sqm": "128.00",
        "land_sqm": None,
        "address_street": "Emilio Castelar",
        "address_number": "155",
        "address_neighborhood": "Polanco V Sección",
        "address_zip": "11560",
        "zone": "Centro",
        "latitude": "19.43271000",
        "longitude": "-99.19832000",
        "is_featured": True,
        "is_verified": True,
        "views": 287,
        "amenity_names": ["Alberca", "Gimnasio", "Roof Garden", "Elevador", "Estacionamiento"],
        "nearby_places": [
            ("Parque Lincoln", "parque", "0.20"),
            ("Liverpool Polanco", "centro comercial", "0.60"),
            ("Hospital ABC", "hospital", "1.50"),
        ],
        "agent_idx": 1,
    },
    {
        "title": "Terreno en zona industrial Vallejo",
        "description": (
            "Terreno plano con uso de suelo mixto en la zona industrial Vallejo. "
            "Ideal para bodega, oficinas o desarrollo residencial. "
            "Escrituras en orden, entrega inmediata."
        ),
        "property_type": "land",
        "property_condition": None,
        "listing_type": "sale",
        "status": "disponible",
        "price": "4500000.00",
        "bedrooms": 0,
        "bathrooms": 0,
        "parking_spaces": 0,
        "construction_sqm": None,
        "land_sqm": "680.00",
        "address_street": "Av. Cuitláhuac",
        "address_number": "3200",
        "address_neighborhood": "Industrial Vallejo",
        "address_zip": "02300",
        "zone": "Norte",
        "latitude": "19.47820000",
        "longitude": "-99.15230000",
        "is_featured": False,
        "is_verified": True,
        "views": 63,
        "amenity_names": [],
        "nearby_places": [
            ("Metro Vallejo", "transporte", "0.30"),
            ("Home Depot Vallejo", "ferretería", "0.70"),
        ],
        "agent_idx": 2,
    },
    {
        "title": "Casa colonial remodelada en Coyoacán",
        "description": (
            "Encantadora casa estilo colonial en el centro de Coyoacán. "
            "Patio interior con fuente, vigas de madera originales y cocina moderna. "
            "A 3 cuadras del Jardín Centenario."
        ),
        "property_type": "house",
        "property_condition": "used",
        "listing_type": "sale",
        "status": "disponible",
        "price": "5100000.00",
        "bedrooms": 3,
        "bathrooms": 2,
        "parking_spaces": 1,
        "construction_sqm": "210.00",
        "land_sqm": "260.00",
        "address_street": "Francisco Sosa",
        "address_number": "88",
        "address_neighborhood": "Villa Coyoacán",
        "address_zip": "04000",
        "zone": "Sur",
        "latitude": "19.35012000",
        "longitude": "-99.16143000",
        "is_featured": False,
        "is_verified": True,
        "views": 195,
        "amenity_names": ["Jardín", "Estacionamiento"],
        "nearby_places": [
            ("Jardín Centenario", "parque", "0.30"),
            ("Mercado de Coyoacán", "mercado", "0.50"),
            ("Museo Frida Kahlo", "cultura", "0.80"),
        ],
        "agent_idx": 1,
    },
    {
        "title": "Departamento en preventa Santa Fe",
        "description": (
            "Departamento en preventa en desarrollo de lujo en Santa Fe. "
            "Torre de 25 pisos con vista panorámica. Entrega estimada Q2 2026. "
            "Precios de lanzamiento disponibles hasta agotar unidades."
        ),
        "property_type": "apartment",
        "property_condition": "new",
        "listing_type": "sale",
        "status": "preventa",
        "price": "7800000.00",
        "bedrooms": 3,
        "bathrooms": 2,
        "parking_spaces": 2,
        "construction_sqm": "155.00",
        "land_sqm": None,
        "address_street": "Prolongación Paseo de la Reforma",
        "address_number": "600",
        "address_neighborhood": "Santa Fe",
        "address_zip": "05300",
        "zone": "Centro",
        "latitude": "19.36540000",
        "longitude": "-99.26180000",
        "is_featured": True,
        "is_verified": False,
        "views": 412,
        "amenity_names": ["Alberca", "Gimnasio", "Roof Garden", "Elevador", "Seguridad 24h", "Estacionamiento"],
        "nearby_places": [
            ("Centro Santa Fe", "centro comercial", "0.40"),
            ("Universidad Iberoamericana", "educación", "0.60"),
            ("Hospital Ángeles Santa Fe", "hospital", "1.10"),
        ],
        "agent_idx": 2,
    },
    {
        "title": "Casa en fraccionamiento privado Pedregal",
        "description": (
            "Residencia en fraccionamiento cerrado con vigilancia 24h. "
            "Dos plantas, amplio estudio, cuarto de servicio con baño. "
            "Jardín y alberca privados. Vecinos en excelente entorno."
        ),
        "property_type": "house",
        "property_condition": "semi_new",
        "listing_type": "sale",
        "status": "disponible",
        "price": "9200000.00",
        "bedrooms": 5,
        "bathrooms": 4,
        "parking_spaces": 3,
        "construction_sqm": "380.00",
        "land_sqm": "500.00",
        "address_street": "Calle Granito",
        "address_number": "15",
        "address_neighborhood": "Pedregal de San Ángel",
        "address_zip": "01900",
        "zone": "Sur",
        "latitude": "19.32870000",
        "longitude": "-99.19450000",
        "is_featured": True,
        "is_verified": True,
        "views": 321,
        "amenity_names": ["Alberca", "Jardín", "Seguridad 24h", "Estacionamiento"],
        "nearby_places": [
            ("Perisur", "centro comercial", "1.20"),
            ("UNAM Campus", "educación", "2.00"),
            ("Clínica Pedregal", "hospital", "0.90"),
        ],
        "agent_idx": 1,
    },
    {
        "title": "Local comercial en Narvarte Poniente",
        "description": (
            "Local comercial en planta baja sobre avenida principal. "
            "Baño integrado, bodega trasera, fachada remodelada. "
            "Flujo peatonal alto. Actualmente rentado hasta diciembre 2025."
        ),
        "property_type": "commercial",
        "property_condition": "used",
        "listing_type": "sale",
        "status": "oportunidad",
        "price": "2800000.00",
        "bedrooms": 0,
        "bathrooms": 1,
        "parking_spaces": 0,
        "construction_sqm": "85.00",
        "land_sqm": "90.00",
        "address_street": "Av. Insurgentes Sur",
        "address_number": "741",
        "address_neighborhood": "Narvarte Poniente",
        "address_zip": "03020",
        "zone": "Centro",
        "latitude": "19.39421000",
        "longitude": "-99.17032000",
        "is_featured": False,
        "is_verified": True,
        "views": 88,
        "amenity_names": ["Estacionamiento"],
        "nearby_places": [
            ("Metro Insurgentes", "transporte", "0.50"),
            ("Mercado Medellín", "mercado", "0.40"),
        ],
        "agent_idx": 2,
    },
    {
        "title": "Departamento familiar en Tlalpan",
        "description": (
            "Amplio departamento en planta baja con pequeño patio privado. "
            "Cocina equipada, recámaras con closets amplios. "
            "Zona tranquila y arbolada al sur de la ciudad."
        ),
        "property_type": "apartment",
        "property_condition": "semi_new",
        "listing_type": "sale",
        "status": "disponible",
        "price": "2350000.00",
        "bedrooms": 3,
        "bathrooms": 2,
        "parking_spaces": 1,
        "construction_sqm": "115.00",
        "land_sqm": None,
        "address_street": "Calzada de Tlalpan",
        "address_number": "4820",
        "address_neighborhood": "Tlalpan Centro",
        "address_zip": "14000",
        "zone": "Sur",
        "latitude": "19.29870000",
        "longitude": "-99.17230000",
        "is_featured": False,
        "is_verified": False,
        "views": 54,
        "amenity_names": ["Jardín", "Estacionamiento"],
        "nearby_places": [
            ("Centro de Salud Tlalpan", "hospital", "0.60"),
            ("Mercado de Tlalpan", "mercado", "0.80"),
            ("Bosque de Tlalpan", "parque", "1.50"),
        ],
        "agent_idx": 1,
    },
    {
        "title": "Casa con roof garden en Azcapotzalco",
        "description": (
            "Casa remodelada con excelente distribución y roof garden equipado. "
            "Perfecta para familia joven. Cerca de escuelas, mercado y transporte. "
            "Financiamiento disponible con crédito hipotecario."
        ),
        "property_type": "house",
        "property_condition": "used",
        "listing_type": "sale",
        "status": "disponible",
        "price": "2950000.00",
        "bedrooms": 3,
        "bathrooms": 2,
        "parking_spaces": 1,
        "construction_sqm": "160.00",
        "land_sqm": "195.00",
        "address_street": "Calle Aztecas",
        "address_number": "112",
        "address_neighborhood": "Impulsora Popular Avicola",
        "address_zip": "02460",
        "zone": "Norte",
        "latitude": "19.48920000",
        "longitude": "-99.18560000",
        "is_featured": False,
        "is_verified": False,
        "views": 37,
        "amenity_names": ["Roof Garden", "Estacionamiento"],
        "nearby_places": [
            ("Preparatoria UNAM", "educación", "0.70"),
            ("Supermercado Chedraui", "supermercado", "0.90"),
            ("Metro Ferrería", "transporte", "1.20"),
        ],
        "agent_idx": 0,
    },
    {
        "title": "Terreno residencial en Xochimilco",
        "description": (
            "Terreno plano en zona residencial de Xochimilco. "
            "Acceso a servicios de agua, luz y drenaje. "
            "Uso de suelo habitacional. Escrituras al corriente. "
            "Excelente opción para autoconstrucción o inversión."
        ),
        "property_type": "land",
        "property_condition": None,
        "listing_type": "sale",
        "status": "disponible",
        "price": "1850000.00",
        "bedrooms": 0,
        "bathrooms": 0,
        "parking_spaces": 0,
        "construction_sqm": None,
        "land_sqm": "350.00",
        "address_street": "Calle Guadalupe I. Ramírez",
        "address_number": "SN",
        "address_neighborhood": "Santa Cecilia Tepetlapa",
        "address_zip": "16100",
        "zone": "Sur",
        "latitude": "19.25340000",
        "longitude": "-99.10870000",
        "is_featured": False,
        "is_verified": False,
        "views": 29,
        "amenity_names": [],
        "nearby_places": [
            ("Trajineras Xochimilco", "turismo", "1.80"),
            ("Mercado Xochimilco", "mercado", "2.10"),
        ],
        "agent_idx": 1,
    },
    {
        "title": "Departamento ejecutivo en Benito Juárez",
        "description": (
            "Departamento de 1 recámara ideal para ejecutivo soltero o pareja. "
            "Acabados modernos, cocina abierta y balcón al interior. "
            "Edificio con gym y vigilancia. Excelente conectividad."
        ),
        "property_type": "apartment",
        "property_condition": "new",
        "listing_type": "sale",
        "status": "disponible",
        "price": "3100000.00",
        "bedrooms": 1,
        "bathrooms": 1,
        "parking_spaces": 1,
        "construction_sqm": "72.00",
        "land_sqm": None,
        "address_street": "Av. Álvaro Obregón",
        "address_number": "55",
        "address_neighborhood": "Roma Norte",
        "address_zip": "06700",
        "zone": "Centro",
        "latitude": "19.41980000",
        "longitude": "-99.16290000",
        "is_featured": False,
        "is_verified": True,
        "views": 178,
        "amenity_names": ["Gimnasio", "Elevador", "Seguridad 24h", "Estacionamiento"],
        "nearby_places": [
            ("Parque México", "parque", "0.30"),
            ("Metro Insurgentes", "transporte", "0.60"),
            ("Supermercado Superama", "supermercado", "0.20"),
        ],
        "agent_idx": 2,
    },
    {
        "title": "Casa en condominio Satélite Norte",
        "description": (
            "Casa en condominio horizontal con alberca comunitaria. "
            "Sala amplia con doble altura, cocina-comedor integrado. "
            "Recámaras en planta alta con baño completo en principal."
        ),
        "property_type": "house",
        "property_condition": "semi_new",
        "listing_type": "sale",
        "status": "disponible",
        "price": "4400000.00",
        "bedrooms": 3,
        "bathrooms": 2,
        "parking_spaces": 2,
        "construction_sqm": "195.00",
        "land_sqm": "220.00",
        "address_street": "Circuito Novelistas",
        "address_number": "28",
        "address_neighborhood": "Ciudad Satélite",
        "address_zip": "53100",
        "zone": "Norte",
        "latitude": "19.53540000",
        "longitude": "-99.24980000",
        "is_featured": False,
        "is_verified": True,
        "views": 112,
        "amenity_names": ["Alberca", "Jardín", "Estacionamiento"],
        "nearby_places": [
            ("Plaza Satélite", "centro comercial", "1.50"),
            ("Colegio Miraflores", "educación", "0.80"),
            ("Hospital Satélite", "hospital", "2.20"),
        ],
        "agent_idx": 0,
    },
    {
        "title": "Loft industrial en colonia Doctores",
        "description": (
            "Loft de doble altura en edificio reconvertido estilo industrial. "
            "Muros de ladrillo expuesto, vigas metálicas y ventanas panorámicas. "
            "Ideal para artistas, creativos o espacio de trabajo-vivienda."
        ),
        "property_type": "apartment",
        "property_condition": "used",
        "listing_type": "sale",
        "status": "disponible",
        "price": "2700000.00",
        "bedrooms": 1,
        "bathrooms": 1,
        "parking_spaces": 0,
        "construction_sqm": "95.00",
        "land_sqm": None,
        "address_street": "Dr. Río de la Loza",
        "address_number": "240",
        "address_neighborhood": "Doctores",
        "address_zip": "06720",
        "zone": "Centro",
        "latitude": "19.41030000",
        "longitude": "-99.14870000",
        "is_featured": False,
        "is_verified": False,
        "views": 67,
        "amenity_names": ["Gimnasio"],
        "nearby_places": [
            ("Metro Doctores", "transporte", "0.40"),
            ("Hospital General de México", "hospital", "0.70"),
            ("Mercado de Jamaica", "mercado", "1.30"),
        ],
        "agent_idx": 2,
    },
    {
        "title": "Casa nueva en desarrollo Cuajimalpa",
        "description": (
            "Casa nueva en desarrollo habitacional de lujo en Cuajimalpa. "
            "Tres niveles con terraza, spa privado y bodega. "
            "Desarrollo con club house, areas verdes y seguridad perimetral."
        ),
        "property_type": "house",
        "property_condition": "new",
        "listing_type": "sale",
        "status": "disponible",
        "price": "11500000.00",
        "bedrooms": 4,
        "bathrooms": 4,
        "parking_spaces": 3,
        "construction_sqm": "430.00",
        "land_sqm": "420.00",
        "address_street": "Av. Vasco de Quiroga",
        "address_number": "4800",
        "address_neighborhood": "Santa Fe Cuajimalpa",
        "address_zip": "05348",
        "zone": "Centro",
        "latitude": "19.36120000",
        "longitude": "-99.27840000",
        "is_featured": True,
        "is_verified": True,
        "views": 389,
        "amenity_names": ["Alberca", "Gimnasio", "Jardín", "Seguridad 24h", "Estacionamiento"],
        "nearby_places": [
            ("Presa Becerra", "parque", "1.00"),
            ("Centro Santa Fe", "centro comercial", "2.50"),
            ("Hospital Ángeles Santa Fe", "hospital", "2.80"),
        ],
        "agent_idx": 1,
    },
    {
        "title": "Bodega con oficina en Iztapalapa",
        "description": (
            "Nave industrial con oficinas en primer nivel. "
            "Altura libre de 7 metros, andén de carga, acceso a tráileres. "
            "Ideal para almacén, taller o distribuidora."
        ),
        "property_type": "warehouse",
        "property_condition": "used",
        "listing_type": "sale",
        "status": "disponible",
        "price": "5800000.00",
        "bedrooms": 0,
        "bathrooms": 2,
        "parking_spaces": 5,
        "construction_sqm": "850.00",
        "land_sqm": "1200.00",
        "address_street": "Av. Ermita Iztapalapa",
        "address_number": "2300",
        "address_neighborhood": "San Andrés Tetepilco",
        "address_zip": "09440",
        "zone": "Sur",
        "latitude": "19.37450000",
        "longitude": "-99.07280000",
        "is_featured": False,
        "is_verified": True,
        "views": 43,
        "amenity_names": ["Estacionamiento", "Seguridad 24h"],
        "nearby_places": [
            ("Central de Abastos", "mercado", "3.00"),
            ("Metro Iztapalapa", "transporte", "1.80"),
        ],
        "agent_idx": 0,
    },
]

# Citas en diferentes estados
APPOINTMENT_STATUSES = [
    "programada",
    "programada",
    "confirmada",
    "confirmada",
    "en_progreso",
    "completada",
    "completada",
    "completada",
    "cancelada",
    "no_show",
]

PURCHASE_PIPELINE = {
    "lead": 0,
    "visita": 11,
    "interes": 22,
    "pre_aprobacion": 33,
    "avaluo": 44,
    "credito": 56,
    "docs_finales": 67,
    "escrituras": 78,
    "cerrado": 100,
}

# Procesos de compra para los 5 clientes
CLIENT_PROCESS_STATUSES = [
    "credito",       # cliente 0 — proceso avanzado
    "interes",       # cliente 1
    "avaluo",        # cliente 2
    "lead",          # cliente 3 — recién llegó
    "escrituras",    # cliente 4 — casi cierra
]

# Procesos de venta
SALE_PROCESS_STATUSES = [
    "valuacion",        # proceso de venta 1
    "firma_contrato",   # proceso de venta 2
]

SELLER_LEADS_DATA = [
    {
        "full_name": "Patricia Osnaya Delgado",
        "email": "patricia.osnaya@gmail.com",
        "phone": "+52 55 9012 3456",
        "property_type": "house",
        "location": "Narvarte, Ciudad de México",
        "square_meters": "180.00",
        "bedrooms": 3,
        "bathrooms": 2,
        "expected_price": "4200000.00",
        "status": "new",
        "notes": "Heredó la propiedad. No tiene prisa pero quiere un precio justo.",
        "agent_idx": None,
    },
    {
        "full_name": "Eduardo Ríos Castellanos",
        "email": "edo.rios@empresa.com",
        "phone": "+52 55 0123 4567",
        "property_type": "apartment",
        "location": "Polanco, Ciudad de México",
        "square_meters": "95.00",
        "bedrooms": 2,
        "bathrooms": 1,
        "expected_price": "5500000.00",
        "status": "contacted",
        "notes": "Cita programada para el viernes. Interesado en conocer el proceso de valoración.",
        "agent_idx": 0,
    },
    {
        "full_name": "Fernanda Gutiérrez Molina",
        "email": "fernanda.gtz@hotmail.com",
        "phone": "+52 55 1234 0987",
        "property_type": "land",
        "location": "Tlalpan, Ciudad de México",
        "square_meters": "480.00",
        "bedrooms": 0,
        "bathrooms": 0,
        "expected_price": "2800000.00",
        "status": "converted",
        "notes": "Se convirtió a propiedad y proceso de venta. Firmó contrato de exclusiva.",
        "agent_idx": 1,
    },
]


# ---------------------------------------------------------------------------
# Clase del comando
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = "Carga datos de prueba realistas para el tenant Altas Montañas"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Elimina todos los datos existentes del tenant antes de recrearlos",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("\n🏔  Altas Montañas — Seed de datos demo\n"))

        with transaction.atomic():
            if options["reset"]:
                self._reset_tenant_data()

            tenant, city = self._create_tenant_and_location()
            amenities = self._create_amenities()
            admin_membership = self._create_admin(tenant)
            agent_memberships = self._create_agents(tenant)
            client_memberships = self._create_clients(tenant)
            properties = self._create_properties(tenant, city, agent_memberships, amenities)
            purchase_processes = self._create_purchase_processes(
                tenant, properties, client_memberships, agent_memberships
            )
            self._create_sale_processes(
                tenant, properties, client_memberships, agent_memberships
            )
            self._create_appointments(
                tenant, properties, client_memberships, agent_memberships
            )
            self._create_seller_leads(tenant, agent_memberships)
            self._create_notifications(
                tenant, admin_membership, agent_memberships,
                client_memberships, properties, purchase_processes
            )

        self.stdout.write(self.style.SUCCESS("\n✅  Seed completado con éxito.\n"))
        self._print_credentials()

    # -----------------------------------------------------------------------
    # Reset
    # -----------------------------------------------------------------------

    def _reset_tenant_data(self):
        self.stdout.write("  ⚠  Eliminando datos existentes del tenant Altas Montañas…")
        try:
            tenant = Tenant.objects.get(slug="altas-montanas")
            # Cascades eliminan todo lo relacionado
            tenant.delete()
            self.stdout.write("     Tenant eliminado.")
        except Tenant.DoesNotExist:
            self.stdout.write("     No existía el tenant, se creará desde cero.")

        # Eliminar usuarios de demo (no tienen tenant directo)
        all_demo_emails = (
            [d["email"] for d in AGENTS_DATA]
            + [d["email"] for d in CLIENTS_DATA]
            + ["admin@altasmontanas.mx"]
        )
        deleted, _ = User.objects.filter(email__in=all_demo_emails).delete()
        self.stdout.write(f"     {deleted} usuario(s) demo eliminado(s).")

    # -----------------------------------------------------------------------
    # Tenant & Location
    # -----------------------------------------------------------------------

    def _create_tenant_and_location(self):
        self.stdout.write("  📍 Creando tenant y ubicación…")

        mexico, _ = Country.objects.get_or_create(
            code="MX",
            defaults={"name": "México"},
        )
        cdmx_state, _ = State.objects.get_or_create(
            name="Ciudad de México",
            country=mexico,
            defaults={"code": "CDMX"},
        )
        city, _ = City.objects.get_or_create(
            name="Ciudad de México",
            state=cdmx_state,
        )

        tenant, created = Tenant.objects.get_or_create(
            slug="altas-montanas",
            defaults={
                "name": "Altas Montañas Inmobiliaria",
                "email": "contacto@altasmontanas.mx",
                "phone": "+52 55 5555 0000",
                "website": "https://www.altasmontanas.mx",
                "address": "Av. Insurgentes Sur 1234, Piso 8, Col. Del Valle, CDMX",
                "city": city,
                "is_active": True,
            },
        )
        tag = "creado" if created else "ya existía"
        self.stdout.write(f"     Tenant '{tenant.name}' {tag}.")

        # Configuración de citas del tenant
        AppointmentSettings.objects.get_or_create(
            tenant=tenant,
            defaults={
                "slot_duration_minutes": 60,
                "max_advance_days": 30,
                "min_advance_hours": 24,
                "day_start_time": time(9, 0),
                "day_end_time": time(18, 0),
            },
        )

        return tenant, city

    # -----------------------------------------------------------------------
    # Amenidades globales
    # -----------------------------------------------------------------------

    def _create_amenities(self):
        self.stdout.write("  🏊 Creando/verificando amenidades globales…")
        amenities_data = [
            ("Alberca", "waves"),
            ("Gimnasio", "dumbbell"),
            ("Seguridad 24h", "shield"),
            ("Elevador", "arrow-up-down"),
            ("Estacionamiento", "car"),
            ("Jardín", "tree"),
            ("Roof Garden", "sun"),
        ]
        amenities = {}
        for name, icon in amenities_data:
            obj, _ = Amenity.objects.get_or_create(name=name, defaults={"icon": icon})
            amenities[name] = obj
        self.stdout.write(f"     {len(amenities)} amenidades listas.")
        return amenities

    # -----------------------------------------------------------------------
    # Admin
    # -----------------------------------------------------------------------

    def _create_admin(self, tenant):
        self.stdout.write("  👤 Creando admin…")
        user, created = User.objects.get_or_create(
            email="admin@altasmontanas.mx",
            defaults={
                "first_name": "Dirección",
                "last_name": "Altas Montañas",
                "phone": "+52 55 5555 0001",
                "is_active": True,
                "password": make_password("Demo1234!"),
            },
        )
        if not created:
            # Asegura contraseña actualizada
            user.set_password("Demo1234!")
            user.save(update_fields=["password"])

        membership, _ = TenantMembership.objects.get_or_create(
            user=user,
            tenant=tenant,
            defaults={"role": TenantMembership.Role.ADMIN, "is_active": True},
        )
        UserNotificationPreferences.objects.get_or_create(membership=membership)
        self.stdout.write(f"     Admin: {user.email}")
        return membership

    # -----------------------------------------------------------------------
    # Agentes
    # -----------------------------------------------------------------------

    def _create_agents(self, tenant):
        self.stdout.write("  🧑‍💼 Creando agentes…")
        memberships = []
        for data in AGENTS_DATA:
            user, created = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "phone": data["phone"],
                    "is_active": True,
                    "password": make_password("Demo1234!"),
                },
            )
            if not created:
                user.set_password("Demo1234!")
                user.save(update_fields=["password"])

            membership, _ = TenantMembership.objects.get_or_create(
                user=user,
                tenant=tenant,
                defaults={"role": TenantMembership.Role.AGENT, "is_active": True},
            )

            AgentProfile.objects.update_or_create(
                membership=membership,
                defaults={
                    "zone": data["zone"],
                    "bio": data["bio"],
                    "score": data["score"],
                },
            )

            UserNotificationPreferences.objects.get_or_create(membership=membership)

            # Horario
            sched_data = data["schedule"]
            schedule, s_created = AgentSchedule.objects.get_or_create(
                tenant=tenant,
                agent_membership=membership,
                name=sched_data["name"],
                defaults={
                    "start_time": sched_data["start_time"],
                    "end_time": sched_data["end_time"],
                    "has_lunch_break": True,
                    "lunch_start": sched_data["lunch_start"],
                    "lunch_end": sched_data["lunch_end"],
                    "valid_from": date(2025, 1, 1),
                    "is_active": True,
                    "priority": 0,
                    **{day: (day in sched_data["days"]) for day in
                       ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]},
                },
            )
            if s_created:
                ScheduleBreak.objects.create(
                    schedule=schedule,
                    break_type=ScheduleBreak.BreakType.LUNCH,
                    name="Comida",
                    start_time=sched_data["lunch_start"],
                    end_time=sched_data["lunch_end"],
                )

            self.stdout.write(f"     Agente: {user.get_full_name()} ({data['zone']})")
            memberships.append(membership)
        return memberships

    # -----------------------------------------------------------------------
    # Clientes
    # -----------------------------------------------------------------------

    def _create_clients(self, tenant):
        self.stdout.write("  👥 Creando clientes…")
        memberships = []
        for data in CLIENTS_DATA:
            user, created = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "phone": data["phone"],
                    "city": data["city"],
                    "is_active": True,
                    "password": make_password("Demo1234!"),
                },
            )
            if not created:
                user.set_password("Demo1234!")
                user.save(update_fields=["password"])

            membership, _ = TenantMembership.objects.get_or_create(
                user=user,
                tenant=tenant,
                defaults={"role": TenantMembership.Role.CLIENT, "is_active": True},
            )
            UserNotificationPreferences.objects.get_or_create(membership=membership)
            self.stdout.write(f"     Cliente: {user.get_full_name()}")
            memberships.append(membership)
        return memberships

    # -----------------------------------------------------------------------
    # Propiedades
    # -----------------------------------------------------------------------

    def _create_properties(self, tenant, city, agent_memberships, amenities):
        self.stdout.write("  🏠 Creando propiedades…")
        created_properties = []

        for i, data in enumerate(PROPERTIES_DATA):
            prop, created = Property.objects.get_or_create(
                tenant=tenant,
                title=data["title"],
                defaults={
                    "description": data["description"],
                    "property_type": data["property_type"],
                    "property_condition": data.get("property_condition"),
                    "listing_type": data["listing_type"],
                    "status": data["status"],
                    "price": data["price"],
                    "bedrooms": data["bedrooms"],
                    "bathrooms": data["bathrooms"],
                    "parking_spaces": data["parking_spaces"],
                    "construction_sqm": data.get("construction_sqm"),
                    "land_sqm": data.get("land_sqm"),
                    "address_street": data["address_street"],
                    "address_number": data["address_number"],
                    "address_neighborhood": data["address_neighborhood"],
                    "address_zip": data["address_zip"],
                    "city": city,
                    "zone": data["zone"],
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "is_featured": data["is_featured"],
                    "is_verified": data["is_verified"],
                    "is_active": True,
                    "views": data["views"],
                },
            )

            if created:
                # Imágenes placeholder (Picsum Photos)
                seed_base = (i + 1) * 10
                PropertyImage.objects.create(
                    property=prop,
                    image_url=f"https://picsum.photos/seed/{seed_base}/800/600",
                    is_cover=True,
                    sort_order=0,
                )
                for j in range(1, 4):
                    PropertyImage.objects.create(
                        property=prop,
                        image_url=f"https://picsum.photos/seed/{seed_base + j}/800/600",
                        is_cover=False,
                        sort_order=j,
                    )

                # Amenidades
                for amenity_name in data.get("amenity_names", []):
                    if amenity_name in amenities:
                        PropertyAmenity.objects.get_or_create(
                            property=prop,
                            amenity=amenities[amenity_name],
                        )

                # Lugares cercanos
                for name, place_type, distance in data.get("nearby_places", []):
                    PropertyNearbyPlace.objects.create(
                        property=prop,
                        name=name,
                        place_type=place_type,
                        distance_km=distance,
                    )

                # Asignación de agente
                agent_idx = data.get("agent_idx", 0)
                PropertyAssignment.objects.get_or_create(
                    property=prop,
                    agent_membership=agent_memberships[agent_idx],
                    defaults={"is_visible": True},
                )

            created_properties.append(prop)
            tag = "creada" if created else "ya existía"
            self.stdout.write(f"     [{i+1:02d}] {prop.title[:50]} — {tag}")

        return created_properties

    # -----------------------------------------------------------------------
    # Procesos de compra
    # -----------------------------------------------------------------------

    def _create_purchase_processes(self, tenant, properties, client_memberships, agent_memberships):
        self.stdout.write("  📋 Creando procesos de compra…")
        processes = []

        for idx, (client_membership, status_key) in enumerate(
            zip(client_memberships, CLIENT_PROCESS_STATUSES)
        ):
            prop = properties[idx]  # cada cliente a una propiedad distinta
            agent_membership = agent_memberships[idx % len(agent_memberships)]
            progress = PURCHASE_PIPELINE[status_key]

            extra = {}
            if status_key == "cerrado":
                extra = {
                    "sale_price": prop.price,
                    "payment_method": "Crédito hipotecario",
                    "closed_at": timezone.now() - timedelta(days=5),
                }

            pp, created = PurchaseProcess.objects.get_or_create(
                tenant=tenant,
                property=prop,
                client_membership=client_membership,
                defaults={
                    "agent_membership": agent_membership,
                    "status": status_key,
                    "overall_progress": progress,
                    "notes": f"Proceso demo — etapa {status_key}.",
                    **extra,
                },
            )
            tag = "creado" if created else "ya existía"
            self.stdout.write(
                f"     Proceso compra #{pp.pk} — {client_membership.user.get_full_name()} "
                f"→ {status_key} ({progress}%) — {tag}"
            )
            processes.append(pp)
        return processes

    # -----------------------------------------------------------------------
    # Procesos de venta
    # -----------------------------------------------------------------------

    def _create_sale_processes(self, tenant, properties, client_memberships, agent_memberships):
        self.stdout.write("  📝 Creando procesos de venta…")
        # Usamos propiedades 10 y 11 para los procesos de venta
        sale_props = [properties[10], properties[11]]

        for idx, status_key in enumerate(SALE_PROCESS_STATUSES):
            prop = sale_props[idx]
            client_membership = client_memberships[idx]  # los primeros 2 clientes como vendedores
            agent_membership = agent_memberships[(idx + 1) % len(agent_memberships)]

            sp, created = SaleProcess.objects.get_or_create(
                tenant=tenant,
                property=prop,
                client_membership=client_membership,
                defaults={
                    "agent_membership": agent_membership,
                    "status": status_key,
                    "notes": f"Proceso venta demo — etapa {status_key}.",
                },
            )
            tag = "creado" if created else "ya existía"
            self.stdout.write(
                f"     Proceso venta #{sp.pk} — {client_membership.user.get_full_name()} "
                f"→ {status_key} — {tag}"
            )

    # -----------------------------------------------------------------------
    # Citas
    # -----------------------------------------------------------------------

    def _create_appointments(self, tenant, properties, client_memberships, agent_memberships):
        self.stdout.write("  📅 Creando citas…")
        today = date.today()

        # Distribución de fechas relativas a hoy
        date_offsets = [-14, -10, -7, -5, -3, -1, 1, 3, 7, 12]
        times = [
            time(9, 0), time(10, 0), time(11, 0), time(12, 0),
            time(15, 0), time(16, 0), time(9, 0), time(10, 0),
            time(11, 0), time(14, 0),
        ]

        for idx, (status, offset, appt_time) in enumerate(
            zip(APPOINTMENT_STATUSES, date_offsets, times)
        ):
            prop = properties[idx % len(properties)]
            agent_membership = agent_memberships[idx % len(agent_memberships)]
            client_membership = client_memberships[idx % len(client_memberships)]
            scheduled_date = today + timedelta(days=offset)

            matricula = generate_matricula(tenant.id)

            cancellation_reason = ""
            if status == "cancelada":
                cancellation_reason = "El cliente tuvo un imprevisto y solicitó cancelar."

            appt, created = Appointment.objects.get_or_create(
                tenant=tenant,
                matricula=matricula,
                defaults={
                    "property": prop,
                    "client_membership": client_membership,
                    "agent_membership": agent_membership,
                    "client_name": client_membership.user.get_full_name(),
                    "client_email": client_membership.user.email,
                    "client_phone": client_membership.user.phone or "",
                    "scheduled_date": scheduled_date,
                    "scheduled_time": appt_time,
                    "duration_minutes": 60,
                    "status": status,
                    "notes": f"Cita demo #{idx+1}.",
                    "cancellation_reason": cancellation_reason,
                },
            )
            self.stdout.write(
                f"     Cita {appt.matricula} — {scheduled_date} {appt_time} — {status}"
            )

    # -----------------------------------------------------------------------
    # Seller Leads
    # -----------------------------------------------------------------------

    def _create_seller_leads(self, tenant, agent_memberships):
        self.stdout.write("  🎯 Creando seller leads…")
        for data in SELLER_LEADS_DATA:
            agent_membership = (
                agent_memberships[data["agent_idx"]]
                if data["agent_idx"] is not None
                else None
            )
            lead, created = SellerLead.objects.get_or_create(
                tenant=tenant,
                email=data["email"],
                defaults={
                    "full_name": data["full_name"],
                    "phone": data["phone"],
                    "property_type": data["property_type"],
                    "location": data["location"],
                    "square_meters": data["square_meters"],
                    "bedrooms": data["bedrooms"],
                    "bathrooms": data["bathrooms"],
                    "expected_price": data["expected_price"],
                    "status": data["status"],
                    "assigned_agent_membership": agent_membership,
                    "notes": data["notes"],
                },
            )
            tag = "creado" if created else "ya existía"
            self.stdout.write(
                f"     Lead {lead.full_name} — {data['status']} — {tag}"
            )

    # -----------------------------------------------------------------------
    # Notificaciones
    # -----------------------------------------------------------------------

    def _create_notifications(
        self, tenant, admin_membership, agent_memberships,
        client_memberships, properties, purchase_processes
    ):
        self.stdout.write("  🔔 Creando notificaciones de ejemplo…")

        notifications = [
            # Para admin
            {
                "membership": admin_membership,
                "title": "Nuevo seller lead recibido",
                "message": "Patricia Osnaya envió su propiedad en Narvarte para valuación.",
                "notification_type": "lead",
                "reference_type": "seller_lead",
                "is_read": False,
            },
            {
                "membership": admin_membership,
                "title": "Cita completada — CLI-2026-003",
                "message": "Sofía Ramírez marcó la cita CLI-2026-003 como completada.",
                "notification_type": "appointment",
                "reference_type": "appointment",
                "is_read": True,
            },
            # Para agente 0 (Sofía)
            {
                "membership": agent_memberships[0],
                "title": "Nueva cita asignada",
                "message": (
                    f"Se agendó una cita para la propiedad "
                    f"'{properties[0].title[:40]}'. Revisa tu calendario."
                ),
                "notification_type": "appointment",
                "reference_type": "appointment",
                "is_read": False,
            },
            {
                "membership": agent_memberships[0],
                "title": "Proceso de compra avanzó",
                "message": "Roberto García avanzó a la etapa de Crédito en su proceso de compra.",
                "notification_type": "purchase",
                "reference_type": "purchase_process",
                "reference_id": purchase_processes[0].pk if purchase_processes else None,
                "is_read": False,
            },
            # Para agente 1 (Carlos)
            {
                "membership": agent_memberships[1],
                "title": "Propiedad verificada",
                "message": f"La propiedad '{properties[1].title[:40]}' fue marcada como verificada.",
                "notification_type": "system",
                "reference_type": "property",
                "reference_id": properties[1].pk,
                "is_read": True,
            },
            {
                "membership": agent_memberships[1],
                "title": "Nuevo lead de compra",
                "message": "Valentina Cruz mostró interés en tu propiedad en Coyoacán.",
                "notification_type": "purchase",
                "reference_type": "purchase_process",
                "is_read": False,
            },
            # Para agente 2 (Ana)
            {
                "membership": agent_memberships[2],
                "title": "Seller lead asignado",
                "message": "Se te asignó el lead de Eduardo Ríos (departamento en Polanco).",
                "notification_type": "lead",
                "reference_type": "seller_lead",
                "is_read": False,
            },
            # Para cliente 0 (Roberto)
            {
                "membership": client_memberships[0],
                "title": "Tu proceso avanzó a Crédito",
                "message": (
                    "¡Buenas noticias! Tu proceso de compra avanzó a la etapa de Crédito. "
                    "Tu agente Sofía te contactará pronto."
                ),
                "notification_type": "purchase",
                "reference_type": "purchase_process",
                "reference_id": purchase_processes[0].pk if purchase_processes else None,
                "is_read": False,
            },
            {
                "membership": client_memberships[0],
                "title": "Cita confirmada",
                "message": "Tu cita para ver la propiedad en Lomas Verdes fue confirmada.",
                "notification_type": "appointment",
                "reference_type": "appointment",
                "is_read": True,
            },
            # Para cliente 4 (Andrés — casi cierra)
            {
                "membership": client_memberships[4],
                "title": "¡Casi listo! Firma de escrituras próxima",
                "message": (
                    "Tu proceso de compra está en etapa de Escrituras. "
                    "Comunícate con tu agente para coordinar la fecha de firma ante notario."
                ),
                "notification_type": "purchase",
                "reference_type": "purchase_process",
                "reference_id": purchase_processes[4].pk if len(purchase_processes) > 4 else None,
                "is_read": False,
            },
        ]

        count = 0
        for notif_data in notifications:
            # Evitar duplicados exactos por título y membership
            if not Notification.objects.filter(
                tenant=tenant,
                membership=notif_data["membership"],
                title=notif_data["title"],
            ).exists():
                Notification.objects.create(
                    tenant=tenant,
                    membership=notif_data["membership"],
                    title=notif_data["title"],
                    message=notif_data.get("message", ""),
                    notification_type=notif_data.get("notification_type", "system"),
                    is_read=notif_data.get("is_read", False),
                    reference_type=notif_data.get("reference_type", ""),
                    reference_id=notif_data.get("reference_id"),
                )
                count += 1

        self.stdout.write(f"     {count} notificaciones creadas.")

    # -----------------------------------------------------------------------
    # Resumen de credenciales
    # -----------------------------------------------------------------------

    def _print_credentials(self):
        self.stdout.write(self.style.MIGRATE_HEADING("  Credenciales demo (contraseña: Demo1234!)"))
        self.stdout.write("  ┌─────────────────────────────────────────────────────────────┐")
        self.stdout.write("  │ ROL    │ EMAIL                              │ CONTRASEÑA     │")
        self.stdout.write("  ├─────────────────────────────────────────────────────────────┤")
        self.stdout.write("  │ Admin  │ admin@altasmontanas.mx             │ Demo1234!      │")
        self.stdout.write("  │ Agente │ sofia.ramirez@altasmontanas.mx    │ Demo1234!      │")
        self.stdout.write("  │ Agente │ carlos.mendoza@altasmontanas.mx   │ Demo1234!      │")
        self.stdout.write("  │ Agente │ ana.torres@altasmontanas.mx       │ Demo1234!      │")
        self.stdout.write("  │ Cliente│ roberto.garcia@gmail.com          │ Demo1234!      │")
        self.stdout.write("  │ Cliente│ vale.cruz@hotmail.com             │ Demo1234!      │")
        self.stdout.write("  │ Cliente│ miguel.fdz@outlook.com            │ Demo1234!      │")
        self.stdout.write("  │ Cliente│ claudia.morales@yahoo.com         │ Demo1234!      │")
        self.stdout.write("  │ Cliente│ andres.jimenez@gmail.com          │ Demo1234!      │")
        self.stdout.write("  └─────────────────────────────────────────────────────────────┘")
        self.stdout.write("")
        self.stdout.write("  Header para requests autenticados:")
        self.stdout.write("  X-Tenant-ID: altas-montanas")
        self.stdout.write("")
