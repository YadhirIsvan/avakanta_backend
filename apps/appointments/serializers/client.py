from rest_framework import serializers
from apps.properties.serializers.public import build_absolute_url
from ..models import Appointment


class ClientAppointmentListSerializer(serializers.ModelSerializer):
    property_title = serializers.CharField(source='property.title', read_only=True)
    property_image = serializers.SerializerMethodField()
    property_address = serializers.SerializerMethodField()
    agent_name = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            'id', 'matricula',
            'scheduled_date', 'scheduled_time', 'duration_minutes',
            'status', 'appointment_type',
            'property_title', 'property_image', 'property_address',
            'agent_name',
            'created_at',
        ]
        read_only_fields = fields

    def get_property_image(self, obj):
        cover = obj.property.images.filter(is_cover=True).first()
        if not cover:
            cover = obj.property.images.first()
        if not cover:
            return None
        request = self.context.get('request')
        return build_absolute_url(cover.image_url, request)

    def get_property_address(self, obj):
        prop = obj.property
        parts = []
        if prop.address_street and prop.address_number:
            parts.append(f'{prop.address_street} {prop.address_number}')
        if prop.address_neighborhood:
            parts.append(f'Col. {prop.address_neighborhood}')
        if prop.city:
            parts.append(prop.city.name)
        return ', '.join(parts) if parts else ''

    def get_agent_name(self, obj):
        user = obj.agent_membership.user
        return user.get_full_name() or user.email
