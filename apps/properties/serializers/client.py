from rest_framework import serializers

from ..models import SavedProperty


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
    cover = prop.images.filter(is_cover=True).first() or prop.images.order_by('sort_order').first()
    if not cover or not cover.image_url:
        return None

    image_url = cover.image_url
    if image_url and not image_url.startswith('http'):
        if request:
            base_url = request.build_absolute_uri('/')
            image_url = f"{base_url.rstrip('/')}{image_url}"
        else:
            from django.conf import settings
            base_url = settings.BACKEND_URL or 'http://localhost:8000'
            image_url = f"{base_url.rstrip('/')}{image_url}"

    return image_url


class ClientSavedPropertySerializer(serializers.ModelSerializer):
    property = serializers.SerializerMethodField()
    saved_at = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = SavedProperty
        fields = ['id', 'property', 'saved_at']

    def get_property(self, obj):
        prop = obj.property
        request = self.context.get('request')
        return {
            'id': prop.id,
            'title': prop.title,
            'address': _address(prop),
            'price': str(prop.price),
            'property_type': prop.property_type,
            'bedrooms': prop.bedrooms,
            'bathrooms': prop.bathrooms,
            'construction_sqm': str(prop.construction_sqm) if prop.construction_sqm else None,
            'image': _cover_image(prop, request),
            'is_verified': prop.is_verified,
        }
