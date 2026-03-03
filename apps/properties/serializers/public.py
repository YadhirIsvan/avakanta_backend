from datetime import date
from rest_framework import serializers
from django.conf import settings
from ..models import Property, PropertyImage, PropertyAmenity, PropertyNearbyPlace


def build_absolute_url(image_url, request=None):
    """Convert relative URLs to absolute URLs for media files."""
    if not image_url:
        return None
    if image_url.startswith('http'):
        return image_url
    # Construct absolute URL from relative path
    if request:
        base_url = f"{request.scheme}://{request.get_host()}"
    else:
        base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    return f"{base_url}{image_url}"


class PropertyImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = PropertyImage
        fields = ['id', 'image_url', 'is_cover', 'sort_order']

    def get_image_url(self, obj):
        request = self.context.get('request')
        return build_absolute_url(obj.image_url, request)


class PropertyAmenitySerializer(serializers.Serializer):
    id = serializers.IntegerField(source='amenity.id')
    name = serializers.CharField(source='amenity.name')
    icon = serializers.CharField(source='amenity.icon')


class PropertyNearbyPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyNearbyPlace
        fields = ['name', 'place_type', 'distance_km']


class PublicPropertyListSerializer(serializers.ModelSerializer):
    address = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    days_listed = serializers.SerializerMethodField()
    interested = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            'id', 'title', 'address', 'price', 'currency',
            'property_type', 'property_condition',
            'bedrooms', 'bathrooms', 'construction_sqm',
            'zone', 'image', 'is_verified', 'is_featured',
            'days_listed', 'interested', 'views',
        ]

    def get_address(self, obj):
        parts = []
        if obj.address_street:
            street = obj.address_street
            if obj.address_number:
                street += f' {obj.address_number}'
            parts.append(street)
        if obj.address_neighborhood:
            parts.append(f'Col. {obj.address_neighborhood}')
        if obj.city_id:
            parts.append(obj.city.name)
            if obj.city.state:
                parts.append(obj.city.state.code or obj.city.state.name)
        return ', '.join(parts) if parts else ''

    def get_image(self, obj):
        request = self.context.get('request')
        cover = obj.images.filter(is_cover=True).first()
        return build_absolute_url(cover.image_url, request) if cover else None

    def get_days_listed(self, obj):
        return (date.today() - obj.created_at.date()).days

    def get_interested(self, obj):
        # Prefiere el valor anotado en el queryset; si no, cuenta directamente
        if hasattr(obj, 'interested_count'):
            return obj.interested_count
        return obj.purchase_processes.count() if hasattr(obj, 'purchase_processes') else 0


class PublicPropertyDetailSerializer(serializers.ModelSerializer):
    address = serializers.SerializerMethodField()
    days_listed = serializers.SerializerMethodField()
    interested = serializers.SerializerMethodField()
    images = PropertyImageSerializer(many=True, read_only=True)
    amenities = serializers.SerializerMethodField()
    nearby_places = PropertyNearbyPlaceSerializer(many=True, read_only=True)
    agent = serializers.SerializerMethodField()
    coordinates = serializers.SerializerMethodField()
    video_thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            'id', 'title', 'description', 'price', 'currency',
            'property_type', 'property_condition', 'status',
            'bedrooms', 'bathrooms', 'parking_spaces',
            'construction_sqm', 'land_sqm',
            'address', 'zone', 'latitude', 'longitude',
            'is_verified', 'views', 'days_listed', 'interested',
            'images', 'amenities', 'nearby_places',
            'video_id', 'video_thumbnail',
            'agent', 'coordinates',
        ]

    def get_address(self, obj):
        parts = []
        if obj.address_street:
            street = obj.address_street
            if obj.address_number:
                street += f' {obj.address_number}'
            parts.append(street)
        if obj.address_neighborhood:
            parts.append(f'Col. {obj.address_neighborhood}')
        if obj.city_id:
            parts.append(obj.city.name)
            if obj.city.state:
                parts.append(obj.city.state.code or obj.city.state.name)
        return ', '.join(parts) if parts else ''

    def get_days_listed(self, obj):
        return (date.today() - obj.created_at.date()).days

    def get_interested(self, obj):
        if hasattr(obj, 'interested_count'):
            return obj.interested_count
        return 0

    def get_amenities(self, obj):
        qs = obj.property_amenities.select_related('amenity').all()
        return PropertyAmenitySerializer(qs, many=True).data

    def get_agent(self, obj):
        request = self.context.get('request')
        assignment = obj.assignments.filter(
            is_visible=True
        ).select_related(
            'agent_membership__user'
        ).first()
        if not assignment:
            return None
        user = assignment.agent_membership.user
        return {
            'name': user.get_full_name() or user.email,
            'photo': build_absolute_url(user.avatar, request),
            'phone': user.phone,
            'email': user.email,
        }

    def get_video_thumbnail(self, obj):
        request = self.context.get('request')
        return build_absolute_url(obj.video_thumbnail, request)

    def get_coordinates(self, obj):
        if obj.latitude is None or obj.longitude is None:
            return None
        return {
            'lat': float(obj.latitude),
            'lng': float(obj.longitude),
        }
