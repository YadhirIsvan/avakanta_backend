from datetime import date

from rest_framework import serializers

from ..models import SaleProcess, PurchaseProcess


SALE_STAGES = [
    ('contacto_inicial', 'Contacto Inicial'),
    ('evaluacion', 'Evaluación'),
    ('valuacion', 'Valuación'),
    ('presentacion', 'Presentación'),
    ('firma_contrato', 'Firma Contrato'),
    ('marketing', 'Marketing'),
    ('publicacion', 'Publicación'),
]

SALE_PROGRESS_STEP = {key: i + 1 for i, (key, _) in enumerate(SALE_STAGES)}

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


def _cover_image(prop):
    cover = prop.images.filter(is_cover=True).first()
    return cover.image_url if cover else None


# ── Client Sale Process ───────────────────────────────────────────────────────

class ClientSaleProcessListSerializer(serializers.ModelSerializer):
    property = serializers.SerializerMethodField()
    progress_step = serializers.SerializerMethodField()
    views = serializers.SerializerMethodField()
    interested = serializers.SerializerMethodField()
    days_listed = serializers.SerializerMethodField()
    trend = serializers.SerializerMethodField()
    agent = serializers.SerializerMethodField()

    class Meta:
        model = SaleProcess
        fields = [
            'id', 'property', 'status', 'progress_step',
            'views', 'interested', 'days_listed', 'trend', 'agent',
        ]

    def get_property(self, obj):
        return {
            'id': obj.property_id,
            'title': obj.property.title,
            'address': _address(obj.property),
            'price': str(obj.property.price),
            'status': obj.property.status,
            'image': _cover_image(obj.property),
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


class ClientSaleProcessDetailSerializer(serializers.ModelSerializer):
    property = serializers.SerializerMethodField()
    agent = serializers.SerializerMethodField()
    stages = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()

    class Meta:
        model = SaleProcess
        fields = ['id', 'status', 'property', 'agent', 'stages', 'history']

    def get_property(self, obj):
        return {
            'id': obj.property_id,
            'title': obj.property.title,
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
    'visita': 11,
    'interes': 22,
    'pre_aprobacion': 33,
    'avaluo': 44,
    'credito': 56,
    'docs_finales': 67,
    'escrituras': 78,
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
        current_status = obj.status
        current_index = next(
            (i for i, (key, _, _) in enumerate(PURCHASE_STAGES) if key == current_status), -1
        )
        steps = []
        for i, (key, label, allow_upload) in enumerate(PURCHASE_STAGES):
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
