from rest_framework import serializers

from ..models import PurchaseProcess, SaleProcess


def _property_image(prop):
    cover = prop.images.filter(is_cover=True).first()
    return cover.image_url if cover else None


def _agent_info(membership):
    if not membership:
        return None
    user = membership.user
    profile = getattr(membership, 'agent_profile', None)
    return {
        'id': profile.pk if profile else None,
        'name': user.get_full_name() or user.email,
    }


def _client_info(membership):
    if not membership:
        return None
    user = membership.user
    return {
        'id': user.pk,
        'name': user.get_full_name() or user.email,
        'avatar': user.avatar,
    }


# ── Purchase Process ──────────────────────────────────────────────────────────

class AdminPurchaseProcessListSerializer(serializers.ModelSerializer):
    client = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()
    agent = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseProcess
        fields = [
            'id', 'status', 'overall_progress',
            'client', 'property', 'agent',
            'created_at', 'updated_at',
        ]

    def get_client(self, obj):
        return _client_info(obj.client_membership)

    def get_property(self, obj):
        return {
            'id': obj.property_id,
            'title': obj.property.title,
            'image': _property_image(obj.property),
            'price': str(obj.property.price) if obj.property.price else '',
        }

    def get_agent(self, obj):
        return _agent_info(obj.agent_membership)


class AdminPurchaseProcessCreateSerializer(serializers.Serializer):
    property_id = serializers.IntegerField()
    client_membership_id = serializers.IntegerField()
    agent_membership_id = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class AdminPurchaseProcessStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=PurchaseProcess.Status.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    sale_price = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    payment_method = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=''
    )

    def validate(self, data):
        if data['status'] == PurchaseProcess.Status.CERRADO:
            if not data.get('sale_price'):
                raise serializers.ValidationError(
                    {'sale_price': 'Este campo es obligatorio cuando el status es cerrado.'}
                )
            if not data.get('payment_method'):
                raise serializers.ValidationError(
                    {'payment_method': 'Este campo es obligatorio cuando el status es cerrado.'}
                )
        return data


class AdminPurchaseProcessUpdateSerializer(serializers.Serializer):
    agent_membership_id = serializers.IntegerField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    sale_price = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    payment_method = serializers.CharField(max_length=100, required=False, allow_blank=True)


# ── Sale Process ──────────────────────────────────────────────────────────────

class AdminSaleProcessListSerializer(serializers.ModelSerializer):
    client = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()
    agent = serializers.SerializerMethodField()

    class Meta:
        model = SaleProcess
        fields = [
            'id', 'status',
            'client', 'property', 'agent',
            'created_at', 'updated_at',
        ]

    def get_client(self, obj):
        return _client_info(obj.client_membership)

    def get_property(self, obj):
        return {
            'id': obj.property_id,
            'title': obj.property.title,
            'image': _property_image(obj.property),
        }

    def get_agent(self, obj):
        return _agent_info(obj.agent_membership)


class AdminSaleProcessCreateSerializer(serializers.Serializer):
    property_id = serializers.IntegerField()
    client_membership_id = serializers.IntegerField()
    agent_membership_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class AdminSaleProcessStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=SaleProcess.Status.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


# ── Seller Leads ──────────────────────────────────────────────────────────────

from ..models import SellerLead  # noqa: E402 — avoid circular at top level


class AdminSellerLeadListSerializer(serializers.ModelSerializer):
    assigned_agent = serializers.SerializerMethodField()

    class Meta:
        model = SellerLead
        fields = [
            'id', 'full_name', 'email', 'phone',
            'property_type', 'location', 'expected_price',
            'status', 'assigned_agent', 'created_at',
        ]

    def get_assigned_agent(self, obj):
        if not obj.assigned_agent_membership_id:
            return None
        user = obj.assigned_agent_membership.user
        profile = getattr(obj.assigned_agent_membership, 'agent_profile', None)
        return {
            'id': profile.pk if profile else None,
            'name': user.get_full_name() or user.email,
        }


class AdminSellerLeadDetailSerializer(AdminSellerLeadListSerializer):
    class Meta(AdminSellerLeadListSerializer.Meta):
        fields = AdminSellerLeadListSerializer.Meta.fields + [
            'square_meters', 'bedrooms', 'bathrooms', 'notes', 'updated_at',
        ]


class AdminSellerLeadUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=SellerLead.Status.choices, required=False)
    assigned_agent_membership_id = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class AdminSellerLeadConvertSerializer(serializers.Serializer):
    agent_membership_id = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True, default='')


# ── History ───────────────────────────────────────────────────────────────────

class AdminHistorySerializer(serializers.ModelSerializer):
    property = serializers.SerializerMethodField()
    client = serializers.SerializerMethodField()
    agent = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseProcess
        fields = ['id', 'property', 'client', 'agent', 'sale_price', 'payment_method', 'closed_at']

    def get_property(self, obj):
        return {
            'title': obj.property.title,
            'property_type': obj.property.property_type,
            'zone': obj.property.zone,
        }

    def get_client(self, obj):
        user = obj.client_membership.user
        return {'name': user.get_full_name() or user.email}

    def get_agent(self, obj):
        user = obj.agent_membership.user
        return {'name': user.get_full_name() or user.email}
