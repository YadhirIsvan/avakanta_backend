from django.db import models


def property_image_upload_path(instance, filename):
    return f'properties/{instance.property_id}/images/{filename}'


def property_document_upload_path(instance, filename):
    return f'properties/{instance.property_id}/documents/{filename}'


class Property(models.Model):
    class ListingType(models.TextChoices):
        SALE = 'sale', 'Sale'
        PENDING_LISTING = 'pending_listing', 'Pending Listing'

    class PropertyType(models.TextChoices):
        HOUSE = 'house', 'Casa'
        APARTMENT = 'apartment', 'Departamento'
        LAND = 'land', 'Terreno'
        COMMERCIAL = 'commercial', 'Comercial'
        OFFICE = 'office', 'Oficina'
        WAREHOUSE = 'warehouse', 'Bodega'
        OTHER = 'other', 'Otro'

    class PropertyCondition(models.TextChoices):
        NEW = 'new', 'Nueva'
        SEMI_NEW = 'semi_new', 'Semi-nueva'
        USED = 'used', 'Usada'

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='properties'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    listing_type = models.CharField(max_length=20, choices=ListingType.choices)
    status = models.CharField(max_length=50)
    property_type = models.CharField(max_length=20, choices=PropertyType.choices)
    property_condition = models.CharField(
        max_length=10, choices=PropertyCondition.choices, blank=True, null=True
    )
    price = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, default='MXN')
    bedrooms = models.IntegerField(default=0)
    bathrooms = models.IntegerField(default=0)
    parking_spaces = models.IntegerField(default=0)
    construction_sqm = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    land_sqm = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    views = models.IntegerField(default=0)
    address_street = models.CharField(max_length=255, blank=True, null=True)
    address_number = models.CharField(max_length=50, blank=True, null=True)
    address_neighborhood = models.CharField(max_length=255, blank=True, null=True)
    address_zip = models.CharField(max_length=20, blank=True, null=True)
    city = models.ForeignKey(
        'locations.City',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='properties'
    )
    zone = models.CharField(max_length=100, blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=8, blank=True, null=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, blank=True, null=True)
    video_id = models.CharField(max_length=50, blank=True, null=True)
    video_thumbnail = models.CharField(max_length=500, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'properties'
        verbose_name = 'Property'
        verbose_name_plural = 'Properties'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.tenant.name})'

    def get_display_status(self):
        """
        Calcula el estado equivalente para mostrar al cliente basado en el SaleProcess MÁS RECIENTE:
        - SaleProcess status: vendedor_completado, contacto_inicial, evaluacion, valuacion, firma_contrato, marketing
        - PurchaseProcess status: cerrado (vendida)
        
        Equivalencias:
        - "registrar_propiedad" = nuevo flujo de venta (sale_process en estados iniciales)
        - "aprobar_estado" = firma_contrato (SaleProcess)
        - "marketing" = marketing (SaleProcess)
        - "vendida" = cerrado (PurchaseProcess)
        """
        # Verificar si hay un PurchaseProcess cerrado
        purchase_process = self.purchase_processes.filter(
            status='cerrado'
        ).order_by('-updated_at').first()
        if purchase_process:
            return 'vendida'
        
        # Verificar el estado del SaleProcess MÁS RECIENTE (por updated_at)
        sale_process = self.sale_processes.order_by('-updated_at').first()
        if sale_process:
            if sale_process.status == 'firma_contrato':
                return 'aprobar_estado'
            elif sale_process.status == 'marketing':
                return 'marketing'
            # Si el sale_process existe en cualquier otro estado, está en el flujo de registro
            else:
                return 'registrar_propiedad'
        
        # Si no hay procesos relacionados, devolver el status actual o default
        return self.status


class PropertyImage(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image_url = models.CharField(max_length=500)
    is_cover = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'property_images'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'Image({self.property_id}, cover={self.is_cover})'


class PropertyAmenity(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='property_amenities'
    )
    amenity = models.ForeignKey(
        'locations.Amenity',
        on_delete=models.CASCADE,
        related_name='property_amenities'
    )

    class Meta:
        db_table = 'property_amenities'
        unique_together = [('property', 'amenity')]

    def __str__(self):
        return f'{self.property_id} — {self.amenity.name}'


class PropertyDocument(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    uploaded_by_membership = models.ForeignKey(
        'users.TenantMembership',
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_documents'
    )
    purchase_process = models.ForeignKey(
        'transactions.PurchaseProcess',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents'
    )
    name = models.CharField(max_length=255)
    file_url = models.CharField(max_length=500)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    size_bytes = models.BigIntegerField(blank=True, null=True)
    document_stage = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'property_documents'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.property_id})'


class PropertyNearbyPlace(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='nearby_places'
    )
    name = models.CharField(max_length=255)
    place_type = models.CharField(max_length=100, blank=True, null=True)
    distance_km = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    class Meta:
        db_table = 'property_nearby_places'
        ordering = ['distance_km']

    def __str__(self):
        return f'{self.name} ({self.place_type})'


class PropertyAssignment(models.Model):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    agent_membership = models.ForeignKey(
        'users.TenantMembership',
        on_delete=models.CASCADE,
        related_name='property_assignments'
    )
    is_visible = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'property_assignments'
        unique_together = [('property', 'agent_membership')]

    def __str__(self):
        return f'Assignment({self.property_id} → {self.agent_membership_id})'
