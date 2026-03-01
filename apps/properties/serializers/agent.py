from rest_framework import serializers

from ..models import PropertyAssignment
from apps.transactions.models import PurchaseProcess


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


class AgentPropertyListSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='property.id')
    title = serializers.CharField(source='property.title')
    address = serializers.SerializerMethodField()
    price = serializers.DecimalField(source='property.price', max_digits=14, decimal_places=2)
    property_type = serializers.CharField(source='property.property_type')
    status = serializers.CharField(source='property.status')
    image = serializers.SerializerMethodField()
    leads_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = PropertyAssignment
        fields = ['id', 'title', 'address', 'price', 'property_type', 'status',
                  'image', 'leads_count', 'assigned_at']

    def get_address(self, obj):
        return _address(obj.property)

    def get_image(self, obj):
        return _cover_image(obj.property)


class AgentPropertyLeadSerializer(serializers.ModelSerializer):
    client = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseProcess
        fields = ['id', 'status', 'overall_progress', 'client', 'created_at', 'updated_at']

    def get_client(self, obj):
        user = obj.client_membership.user
        return {
            'name': user.get_full_name() or user.email,
            'email': user.email,
            'phone': user.phone,
        }
