import os

from django.conf import settings
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from core.mixins import TenantQuerySetMixin
from core.pagination import StandardPagination
from core.permissions import IsAdmin
from core.validators import validate_file_type, validate_file_size, ALLOWED_IMAGE_TYPES, MAX_IMAGE_SIZE_MB
from ..models import Property, PropertyImage
from ..serializers.admin import (
    AdminPropertyListSerializer,
    AdminPropertyDetailSerializer,
    AdminPropertyCreateUpdateSerializer,
    AdminPropertyImageSerializer,
)


class AdminPropertyListCreateView(TenantQuerySetMixin, ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardPagination
    filter_backends = [SearchFilter]
    search_fields = ['title', 'address_street', 'address_neighborhood']

    queryset = (
        Property.objects
        .select_related('city__state')
        .prefetch_related('images', 'assignments__agent_membership__user', 'documents')
    )

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AdminPropertyCreateUpdateSerializer
        return AdminPropertyListSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        status = self.request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)

        listing_type = self.request.query_params.get('listing_type')
        if listing_type:
            qs = qs.filter(listing_type=listing_type)

        property_type = self.request.query_params.get('property_type')
        if property_type:
            qs = qs.filter(property_type=property_type)

        agent_id = self.request.query_params.get('agent_id')
        if agent_id:
            qs = qs.filter(assignments__agent_membership_id=agent_id, assignments__is_visible=True)

        return qs.order_by('-created_at')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        detail_serializer = AdminPropertyDetailSerializer(
            instance, context=self.get_serializer_context(),
        )
        return Response(detail_serializer.data, status=201)


class AdminPropertyDetailView(TenantQuerySetMixin, RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsAdmin]
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    queryset = (
        Property.objects
        .select_related('city__state')
        .prefetch_related(
            'images',
            'property_amenities__amenity',
            'nearby_places',
            'documents',
            'assignments__agent_membership__user',
        )
    )

    def get_serializer_class(self):
        if self.request.method == 'PATCH':
            return AdminPropertyCreateUpdateSerializer
        return AdminPropertyDetailSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Reload with all relations for detail response
        instance.refresh_from_db()
        detail = AdminPropertyDetailSerializer(
            self.get_queryset().get(pk=instance.pk),
            context=self.get_serializer_context(),
        )
        return Response(detail.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        return Response(status=204)


class AdminPropertyImageView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, pk):
        prop = Property.objects.filter(
            pk=pk, tenant=request.tenant
        ).first()
        if not prop:
            return Response({'error': 'Propiedad no encontrada.'}, status=404)

        files = request.FILES.getlist('images[]') or request.FILES.getlist('images')
        if not files:
            return Response({'error': 'Se requiere al menos una imagen.'}, status=400)

        is_cover = str(request.data.get('is_cover', 'false')).lower() in ('true', '1')

        created = []
        for i, file in enumerate(files):
            try:
                validate_file_type(file, ALLOWED_IMAGE_TYPES)
                validate_file_size(file, MAX_IMAGE_SIZE_MB)
            except Exception as e:
                return Response({'error': str(e)}, status=400)

            # Determine sort_order
            last = prop.images.order_by('-sort_order').first()
            sort_order = (last.sort_order + 1) if last else 0

            # Save file to MEDIA_ROOT
            rel_path = f'properties/{prop.pk}/images/{file.name}'
            abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, 'wb+') as dest:
                for chunk in file.chunks():
                    dest.write(chunk)

            # If is_cover, clear others first
            if is_cover and i == 0:
                prop.images.update(is_cover=False)

            image = PropertyImage.objects.create(
                property=prop,
                image_url=f'/media/{rel_path}',
                is_cover=(is_cover and i == 0),
                sort_order=sort_order,
            )
            created.append(image)

        return Response(AdminPropertyImageSerializer(created, many=True).data, status=201)


class AdminPropertyImageDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, pk, image_id):
        try:
            image = PropertyImage.objects.select_related('property').get(
                pk=image_id, property__pk=pk, property__tenant=request.tenant
            )
        except PropertyImage.DoesNotExist:
            return Response({'error': 'Imagen no encontrada.'}, status=404)

        # Delete file from disk
        if image.image_url:
            # image_url is like /media/properties/1/images/foo.jpg
            rel = image.image_url.lstrip('/')  # media/properties/...
            # Strip the leading "media/" prefix to get the path under MEDIA_ROOT
            if rel.startswith('media/'):
                rel = rel[len('media/'):]
            abs_path = os.path.join(settings.MEDIA_ROOT, rel)
            if os.path.isfile(abs_path):
                os.remove(abs_path)

        image.delete()
        return Response(status=204)
