from rest_framework import serializers

from ..models import Property, PropertyImage, PropertyAmenity, PropertyNearbyPlace, PropertyDocument, PropertyAssignment


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
        from django.conf import settings
        base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    return f"{base_url}{image_url}"


def extract_youtube_id(url_or_id):
    """Extract YouTube video ID from URL or return ID if already extracted."""
    if not url_or_id:
        return None

    import re

    # If it's already a short ID format (11 chars of alphanumeric, dash, underscore)
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id

    # Try to extract from various YouTube URL formats
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/v/([a-zA-Z0-9_-]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    # Try to extract from query parameter
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url_or_id)
        video_id = parse_qs(parsed.query).get('v')
        if video_id and re.match(r'^[a-zA-Z0-9_-]{11}$', video_id[0]):
            return video_id[0]
    except:
        pass

    # Return as-is if no patterns match
    return url_or_id


class AdminPropertyImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = PropertyImage
        fields = ['id', 'image_url', 'is_cover', 'sort_order']

    def get_image_url(self, obj):
        request = self.context.get('request')
        return build_absolute_url(obj.image_url, request)


class AdminPropertyAmenitySerializer(serializers.Serializer):
    id = serializers.IntegerField(source='amenity.id')
    name = serializers.CharField(source='amenity.name')
    icon = serializers.CharField(source='amenity.icon')


class AdminPropertyNearbyPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyNearbyPlace
        fields = ['id', 'name', 'place_type', 'distance_km']


class AdminPropertyDocumentSerializer(serializers.ModelSerializer):
    uploaded_at = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = PropertyDocument
        fields = ['id', 'name', 'file_url', 'mime_type', 'size_bytes', 'document_stage', 'uploaded_at']


class AdminPropertyAssignmentSerializer(serializers.ModelSerializer):
    agent = serializers.SerializerMethodField()

    class Meta:
        model = PropertyAssignment
        fields = ['id', 'agent', 'is_visible', 'assigned_at']

    def get_agent(self, obj):
        user = obj.agent_membership.user
        return {
            'id': obj.agent_membership.pk,
            'name': user.get_full_name() or user.email,
        }


class AdminPropertyListSerializer(serializers.ModelSerializer):
    address = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    agent = serializers.SerializerMethodField()
    documents_count = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            'id', 'title', 'address', 'price', 'currency',
            'property_type', 'listing_type', 'status',
            'is_featured', 'is_verified', 'is_active',
            'image', 'agent', 'documents_count', 'created_at',
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
        return ', '.join(parts) if parts else ''

    def get_image(self, obj):
        request = self.context.get('request')
        cover = obj.images.filter(is_cover=True).first() or obj.images.first()
        return build_absolute_url(cover.image_url, request) if cover else None

    def get_agent(self, obj):
        assignment = obj.assignments.filter(is_visible=True).select_related(
            'agent_membership__user'
        ).order_by('-assigned_at').first()
        if not assignment:
            return None
        user = assignment.agent_membership.user
        return {
            'id': assignment.agent_membership.pk,
            'name': user.get_full_name() or user.email,
        }

    def get_documents_count(self, obj):
        return obj.documents.count()


class AdminPropertyDetailSerializer(serializers.ModelSerializer):
    address = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    images = AdminPropertyImageSerializer(many=True, read_only=True)
    amenities = serializers.SerializerMethodField()
    nearby_places = AdminPropertyNearbyPlaceSerializer(many=True, read_only=True)
    documents = AdminPropertyDocumentSerializer(many=True, read_only=True)
    assignments = AdminPropertyAssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = Property
        fields = [
            'id', 'title', 'description',
            'price', 'currency', 'property_type', 'property_condition',
            'listing_type', 'status',
            'bedrooms', 'bathrooms', 'parking_spaces',
            'construction_sqm', 'land_sqm',
            'address', 'address_street', 'address_number',
            'address_neighborhood', 'address_zip',
            'city', 'zone', 'latitude', 'longitude',
            'is_featured', 'is_verified', 'is_active',
            'video_id', 'video_thumbnail', 'views',
            'created_at', 'updated_at',
            'images', 'amenities', 'nearby_places', 'documents', 'assignments',
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

    def get_city(self, obj):
        if not obj.city_id:
            return None
        return {
            'id': obj.city.id,
            'name': obj.city.name,
            'state_id': obj.city.state_id,
        }

    def get_amenities(self, obj):
        qs = obj.property_amenities.select_related('amenity').all()
        return AdminPropertyAmenitySerializer(qs, many=True).data


class AdminPropertyCreateUpdateSerializer(serializers.ModelSerializer):
    amenity_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, write_only=True
    )

    class Meta:
        model = Property
        fields = [
            'title', 'description', 'listing_type', 'status',
            'property_type', 'property_condition',
            'price', 'currency',
            'bedrooms', 'bathrooms', 'parking_spaces',
            'construction_sqm', 'land_sqm',
            'address_street', 'address_number', 'address_neighborhood', 'address_zip',
            'city', 'zone', 'latitude', 'longitude',
            'video_id', 'video_thumbnail',
            'is_featured', 'is_verified', 'is_active',
            'amenity_ids',
        ]

    def _sync_amenities(self, property_instance, amenity_ids):
        from ..models import PropertyAmenity
        from apps.locations.models import Amenity
        property_instance.property_amenities.all().delete()
        for amenity_id in amenity_ids:
            try:
                amenity = Amenity.objects.get(pk=amenity_id)
                PropertyAmenity.objects.create(property=property_instance, amenity=amenity)
            except Amenity.DoesNotExist:
                pass

    def validate_video_id(self, value):
        """Extract YouTube video ID from URL if needed."""
        if value:
            return extract_youtube_id(value)
        return value

    def create(self, validated_data):
        amenity_ids = validated_data.pop('amenity_ids', [])
        instance = super().create(validated_data)
        if amenity_ids:
            self._sync_amenities(instance, amenity_ids)
        return instance

    def update(self, instance, validated_data):
        amenity_ids = validated_data.pop('amenity_ids', None)
        instance = super().update(instance, validated_data)
        if amenity_ids is not None:
            self._sync_amenities(instance, amenity_ids)
        return instance


class AdminAssignmentSerializer(serializers.ModelSerializer):
    assigned_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = PropertyAssignment
        fields = ['id', 'property_id', 'agent_membership_id', 'is_visible', 'assigned_at']


class AdminAssignmentCreateSerializer(serializers.Serializer):
    property_id = serializers.IntegerField()
    agent_membership_id = serializers.IntegerField()
    is_visible = serializers.BooleanField(default=True)


class AdminAssignmentUpdateSerializer(serializers.Serializer):
    is_visible = serializers.BooleanField()
