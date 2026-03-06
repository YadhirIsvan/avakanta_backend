from django.contrib import admin

from .models import (
    Property, PropertyImage, PropertyAmenity,
    PropertyDocument, PropertyNearbyPlace, PropertyAssignment,
    SavedProperty,
)


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 0
    readonly_fields = ('created_at',)


class PropertyAmenityInline(admin.TabularInline):
    model = PropertyAmenity
    extra = 0


class PropertyAssignmentInline(admin.TabularInline):
    model = PropertyAssignment
    extra = 0
    readonly_fields = ('assigned_at',)


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'tenant', 'listing_type', 'property_type',
        'status', 'price', 'bedrooms', 'bathrooms', 'is_active', 'is_featured', 'created_at',
    )
    list_filter = ('listing_type', 'property_type', 'status', 'is_active', 'is_featured', 'is_verified', 'tenant')
    search_fields = ('title', 'address_street', 'address_neighborhood')
    readonly_fields = ('views', 'created_at', 'updated_at')
    raw_id_fields = ('tenant', 'city')
    inlines = [PropertyImageInline, PropertyAmenityInline, PropertyAssignmentInline]
    fieldsets = (
        ('General', {'fields': ('tenant', 'title', 'description', 'listing_type', 'property_type', 'property_condition', 'status')}),
        ('Precio', {'fields': ('price', 'currency')}),
        ('Características', {'fields': ('bedrooms', 'bathrooms', 'parking_spaces', 'construction_sqm', 'land_sqm')}),
        ('Ubicación', {'fields': ('address_street', 'address_number', 'address_neighborhood', 'address_zip', 'city', 'zone', 'latitude', 'longitude')}),
        ('Media', {'fields': ('video_id', 'video_thumbnail')}),
        ('Flags', {'fields': ('is_verified', 'is_featured', 'is_active', 'views')}),
        ('Fechas', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(PropertyImage)
class PropertyImageAdmin(admin.ModelAdmin):
    list_display = ('property', 'image_url', 'is_cover', 'sort_order', 'created_at')
    list_filter = ('is_cover',)
    raw_id_fields = ('property',)
    readonly_fields = ('created_at',)


@admin.register(PropertyDocument)
class PropertyDocumentAdmin(admin.ModelAdmin):
    list_display = ('name', 'property', 'mime_type', 'size_bytes', 'document_stage', 'created_at')
    search_fields = ('name',)
    raw_id_fields = ('property', 'uploaded_by_membership', 'purchase_process')
    readonly_fields = ('created_at',)


@admin.register(PropertyNearbyPlace)
class PropertyNearbyPlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'property', 'place_type', 'distance_km')
    search_fields = ('name',)
    raw_id_fields = ('property',)


@admin.register(PropertyAssignment)
class PropertyAssignmentAdmin(admin.ModelAdmin):
    list_display = ('property', 'agent_membership', 'is_visible', 'assigned_at')
    list_filter = ('is_visible',)
    raw_id_fields = ('property', 'agent_membership')
    readonly_fields = ('assigned_at',)


@admin.register(SavedProperty)
class SavedPropertyAdmin(admin.ModelAdmin):
    list_display = ('client_membership', 'property', 'tenant', 'created_at')
    list_filter = ('tenant',)
    raw_id_fields = ('client_membership', 'property', 'tenant')
    readonly_fields = ('created_at',)
