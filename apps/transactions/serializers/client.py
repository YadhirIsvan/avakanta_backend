from datetime import date

from rest_framework import serializers

from ..models import SaleProcess, PurchaseProcess


SALE_STAGES = [
    ('nuevo', 'Nuevo'),
    ('contactado', 'Contactado'),
    ('en_revision', 'En Revisión'),
    ('vendedor_completado', 'Vendedor Completado'),
    ('contacto_inicial', 'Contacto Inicial'),
    ('evaluacion', 'Evaluación'),
    ('valuacion', 'Valuación'),
    ('firma_contrato', 'Firma Contrato'),
    ('marketing', 'Marketing'),
    ('publicar', 'Publicar'),
]

SALE_PROGRESS_STEP = {key: i + 1 for i, (key, _) in enumerate(SALE_STAGES)}

# Los 5 pasos que se muestran al cliente
PURCHASE_STEPS_DISPLAY = [
    ('lead', 'Lead', False),
    ('visita', 'Visita', False),
    ('credito', 'Crédito', True),
    ('docs_finales', 'Docs finales', True),
    ('cerrado', 'Compra exitosa', False),
]

# Mapeo de status internos a los pasos agrupados que ve el cliente
PURCHASE_STATUS_TO_STEP = {
    'lead': 'lead',
    'visita': 'visita',
    'interes': 'credito',
    'pre_aprobacion': 'credito',
    'avaluo': 'credito',
    'credito': 'docs_finales',
    'docs_finales': 'docs_finales',
    'escrituras': 'docs_finales',
    'cerrado': 'cerrado',
    'cancelado': 'lead',  # fallback
}

# Para backward compatibility
PURCHASE_STAGES = [
    ('lead', 'Lead', False),
    ('visita', 'Visita', False),
    ('interes', 'Interés', False),
    ('pre_aprobacion', 'Pre-Aprobación', True),
    ('avaluo', 'Avalúo', False),
    ('credito', 'Crédito', True),
    ('docs_finales', 'Docs Finales', True),
    ('escrituras', 'Escrituras', False),
    ('cerrado', 'Cerrado', False),
]

PURCHASE_STATUS_LABELS = {key: label for key, label, _ in PURCHASE_STAGES}


def _address(prop):
    parts = []
    if prop.address_street:
        street = prop.address_street
        if prop.address_number:
            street += f' {prop.address_number}'
        parts.append(street)
    if prop.address_neighborhood:
        parts.append(f'Col. {prop.address_neighborhood}')
    if prop.city_id:
        parts.append(prop.city.name)
        if prop.city.state:
            parts.append(prop.city.state.code or prop.city.state.name)
    return ', '.join(parts) if parts else ''


def _cover_image(prop, request=None):
    # Retorna la imagen marcada como cover, o la primera disponible
    cover = prop.images.filter(is_cover=True).first() or prop.images.order_by('sort_order').first()
    if not cover or not cover.image_url:
        return None
    
    # Si la URL es relativa, convertir a absoluta
    image_url = cover.image_url
    if image_url and not image_url.startswith('http'):
        if request:
            base_url = request.build_absolute_uri('/')
            image_url = f"{base_url.rstrip('/')}{image_url}"
        else:
            # Fallback si no hay request
            from django.conf import settings
            base_url = settings.BACKEND_URL or 'http://localhost:8000'
            image_url = f"{base_url.rstrip('/')}{image_url}"
    
    return image_url


def get_client_visible_status(sale_process):
    """
    Maps internal status to 5 client-visible statuses:

    - 'registrar_propiedad' = nuevo, contactado, en_revision, vendedor_completado, contacto_inicial, evaluacion
    - 'aprobar_estado' = valuacion, firma_contrato
    - 'marketing' = marketing, publicar
    - 'cancelado' = cancelado
    - 'vendida' = Si hay un PurchaseProcess cerrado
    """
    # 1. Prioridad máxima: Si hay PurchaseProcess.status='cerrado' → propiedad VENDIDA
    if sale_process.property.purchase_processes.filter(status='cerrado').exists():
        return 'vendida'

    # 2. Cancelado
    if sale_process.status == 'cancelado':
        return 'cancelado'

    # 3. Revisar el estado del SaleProcess
    if sale_process.status in ['nuevo', 'contactado', 'en_revision', 'vendedor_completado', 'contacto_inicial', 'evaluacion']:
        return 'registrar_propiedad'
    elif sale_process.status in ['valuacion', 'firma_contrato']:
        return 'aprobar_estado'
    elif sale_process.status in ['marketing', 'publicar']:
        return 'marketing'

    # Default fallback
    return 'registrar_propiedad'


# ── Client Sale Process ───────────────────────────────────────────────────────

class ClientSaleProcessListSerializer(serializers.ModelSerializer):
    property = serializers.SerializerMethodField()
    progress_step = serializers.SerializerMethodField()
    views = serializers.SerializerMethodField()
    interested = serializers.SerializerMethodField()
    days_listed = serializers.SerializerMethodField()
    trend = serializers.SerializerMethodField()
    agent = serializers.SerializerMethodField()
    client_visible_status = serializers.SerializerMethodField()

    class Meta:
        model = SaleProcess
        fields = [
            'id', 'property', 'status', 'client_visible_status', 'progress_step',
            'views', 'interested', 'days_listed', 'trend', 'agent',
        ]

    def get_property(self, obj):
        request = self.context.get('request')
        return {
            'id': obj.property_id,
            'title': obj.property.title,
            'address': _address(obj.property),
            'price': str(obj.property.price),
            'status': obj.property.status,
            'image': _cover_image(obj.property, request),
        }

    def get_progress_step(self, obj):
        return SALE_PROGRESS_STEP.get(obj.status, 0)

    def get_views(self, obj):
        return obj.property.views

    def get_interested(self, obj):
        if hasattr(obj.property, 'interested_count'):
            return obj.property.interested_count
        return obj.property.purchase_processes.count()

    def get_days_listed(self, obj):
        return (date.today() - obj.created_at.date()).days

    def get_trend(self, obj):
        from core.utils import calculate_trend
        return calculate_trend(obj.property.views, 0)

    def get_agent(self, obj):
        if not obj.agent_membership:
            return None
        return {'name': obj.agent_membership.user.get_full_name() or obj.agent_membership.user.email}

    def get_client_visible_status(self, obj):
        return get_client_visible_status(obj)


class ClientSaleProcessDetailSerializer(serializers.ModelSerializer):
    property = serializers.SerializerMethodField()
    agent = serializers.SerializerMethodField()
    stages = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()

    class Meta:
        model = SaleProcess
        fields = ['id', 'status', 'property', 'agent', 'stages', 'history']

    def get_property(self, obj):
        request = self.context.get('request')
        prop = obj.property
        return {
            'id': prop.id,
            'title': prop.title,
            'image': _cover_image(prop, request),
            'price': str(prop.price),
            'currency': prop.currency,
            'address_street': prop.address_street,
            'address_number': prop.address_number,
            'address_neighborhood': prop.address_neighborhood,
            'city': {'id': prop.city.id, 'name': prop.city.name} if prop.city else None,
            'bedrooms': prop.bedrooms,
            'bathrooms': prop.bathrooms,
            'construction_sqm': float(prop.construction_sqm) if prop.construction_sqm else None,
            'land_sqm': float(prop.land_sqm) if prop.land_sqm else None,
            'views': prop.views,
        }

    def get_agent(self, obj):
        if not obj.agent_membership:
            return None
        user = obj.agent_membership.user
        return {
            'name': user.get_full_name() or user.email,
            'phone': user.phone,
            'email': user.email,
        }

    def get_stages(self, obj):
        from ..models import ProcessStatusHistory
        # Build map of status → completed_at from history
        history_qs = ProcessStatusHistory.objects.filter(
            process_type='sale', process_id=obj.pk
        ).order_by('created_at')
        completed_at_map = {}
        for h in history_qs:
            completed_at_map[h.new_status] = h.created_at

        current_status = obj.status
        current_index = next(
            (i for i, (key, _) in enumerate(SALE_STAGES) if key == current_status), -1
        )

        stages = []
        for i, (key, name) in enumerate(SALE_STAGES):
            if i < current_index:
                stage_status = 'completed'
                completed_at = completed_at_map.get(key)
            elif i == current_index:
                stage_status = 'current'
                completed_at = None
            else:
                stage_status = 'pending'
                completed_at = None
            stages.append({
                'name': name,
                'status': stage_status,
                'completed_at': completed_at,
            })
        return stages

    def get_history(self, obj):
        from ..models import ProcessStatusHistory
        qs = ProcessStatusHistory.objects.filter(
            process_type='sale', process_id=obj.pk
        ).order_by('-created_at')
        return [
            {
                'previous_status': h.previous_status,
                'new_status': h.new_status,
                'changed_at': h.created_at,
                'notes': h.notes,
            }
            for h in qs
        ]


# ── Client Purchase Process ───────────────────────────────────────────────────

class ClientPurchaseProcessListSerializer(serializers.ModelSerializer):
    property = serializers.SerializerMethodField()
    process_stage = serializers.SerializerMethodField()
    agent = serializers.SerializerMethodField()
    documents_count = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseProcess
        fields = [
            'id', 'status', 'overall_progress', 'process_stage',
            'property', 'agent', 'documents_count', 'created_at',
        ]

    def get_property(self, obj):
        return {
            'id': obj.property_id,
            'title': obj.property.title,
            'address': _address(obj.property),
            'price': str(obj.property.price),
            'image': _cover_image(obj.property),
        }

    def get_process_stage(self, obj):
        return PURCHASE_STATUS_LABELS.get(obj.status, obj.status)

    def get_agent(self, obj):
        if not obj.agent_membership:
            return None
        return {'name': obj.agent_membership.user.get_full_name() or obj.agent_membership.user.email}

    def get_documents_count(self, obj):
        return obj.documents.count() if hasattr(obj, 'documents') else 0


PURCHASE_PROGRESS_MAP = {
    'lead': 0,
    'visita': 25,
    'interes': 50,
    'pre_aprobacion': 50,
    'avaluo': 50,
    'credito': 75,
    'docs_finales': 75,
    'escrituras': 75,
    'cerrado': 100,
    'cancelado': 0,
}


class ClientPurchaseProcessDetailSerializer(serializers.ModelSerializer):
    process_stage = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()
    agent = serializers.SerializerMethodField()
    steps = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseProcess
        fields = [
            'id', 'status', 'overall_progress', 'process_stage',
            'property', 'agent', 'steps', 'documents',
        ]

    def get_process_stage(self, obj):
        return PURCHASE_STATUS_LABELS.get(obj.status, obj.status)

    def get_property(self, obj):
        return {
            'id': obj.property_id,
            'title': obj.property.title,
            'price': str(obj.property.price),
            'image': _cover_image(obj.property),
        }

    def get_agent(self, obj):
        if not obj.agent_membership:
            return None
        user = obj.agent_membership.user
        return {
            'name': user.get_full_name() or user.email,
            'phone': user.phone,
            'email': user.email,
        }

    def get_steps(self, obj):
        # Mapear el status actual a su paso agrupado
        current_status = obj.status
        
        # Si el proceso está cerrado, todos los pasos están completados
        if current_status == 'cerrado':
            steps = []
            for i, (key, label, allow_upload) in enumerate(PURCHASE_STEPS_DISPLAY):
                steps.append({
                    'key': key,
                    'label': label,
                    'progress': PURCHASE_PROGRESS_MAP.get(key, 0),
                    'status': 'completed',
                    'allow_upload': False,
                })
            return steps
        
        current_step = PURCHASE_STATUS_TO_STEP.get(current_status, 'lead')
        
        # Encontrar el índice del paso agrupado actual
        current_index = next(
            (i for i, (key, _, _) in enumerate(PURCHASE_STEPS_DISPLAY) if key == current_step), -1
        )
        
        steps = []
        for i, (key, label, allow_upload) in enumerate(PURCHASE_STEPS_DISPLAY):
            if i < current_index:
                step_status = 'completed'
            elif i == current_index:
                step_status = 'current'
            else:
                step_status = 'pending'
            steps.append({
                'key': key,
                'label': label,
                'progress': PURCHASE_PROGRESS_MAP.get(key, 0),
                'status': step_status,
                'allow_upload': allow_upload,
            })
        return steps

    def get_documents(self, obj):
        return [
            {
                'id': doc.pk,
                'name': doc.name,
                'file_url': doc.file_url,
                'document_stage': doc.document_stage,
                'uploaded_at': doc.created_at,
            }
            for doc in obj.documents.all()
        ]
