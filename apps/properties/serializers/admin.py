from rest_framework import serializers

from ..models import Property, PropertyImage, PropertyAmenity, PropertyNearbyPlace, PropertyDocument, PropertyAssignment


class AdminPropertyImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyImage
        fields = ['id', 'image_url', 'is_cover', 'sort_order']


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
        cover = obj.images.filter(is_cover=True).first()
        return cover.image_url if cover else None

    def get_agent(self, obj):
        assignment = obj.assignments.filter(is_visible=True).select_related(
            'agent_membership__user'
        ).first()
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
