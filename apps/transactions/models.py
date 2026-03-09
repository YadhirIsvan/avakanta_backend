from django.db import models


class PurchaseProcess(models.Model):
    class Status(models.TextChoices):
        LEAD = 'lead', 'Lead'
        VISITA = 'visita', 'Visita'
        INTERES = 'interes', 'Interés'
        PRE_APROBACION = 'pre_aprobacion', 'Pre-aprobación'
        AVALUO = 'avaluo', 'Avalúo'
        CREDITO = 'credito', 'Crédito'
        DOCS_FINALES = 'docs_finales', 'Docs finales'
        ESCRITURAS = 'escrituras', 'Escrituras'
        CERRADO = 'cerrado', 'Cerrado'
        CANCELADO = 'cancelado', 'Cancelado'

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE, related_name='purchase_processes'
    )
    property = models.ForeignKey(
        'properties.Property', on_delete=models.CASCADE, related_name='purchase_processes'
    )
    client_membership = models.ForeignKey(
        'users.TenantMembership', on_delete=models.CASCADE,
        related_name='client_purchase_processes'
    )
    agent_membership = models.ForeignKey(
        'users.TenantMembership', on_delete=models.CASCADE,
        related_name='agent_purchase_processes'
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.LEAD
    )
    overall_progress = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    sale_price = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    payment_method = models.CharField(max_length=100, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'purchase_processes'

    def __str__(self):
        return f'PurchaseProcess({self.pk}) — {self.status}'


class SaleProcess(models.Model):
    class Status(models.TextChoices):
        NUEVO = 'nuevo', 'Nuevo'
        CONTACTADO = 'contactado', 'Contactado'
        EN_REVISION = 'en_revision', 'En revisión'
        VENDEDOR_COMPLETADO = 'vendedor_completado', 'Vendedor completado'
        CONTACTO_INICIAL = 'contacto_inicial', 'Contacto inicial'
        EVALUACION = 'evaluacion', 'Evaluación'
        VALUACION = 'valuacion', 'Valuación'
        FIRMA_CONTRATO = 'firma_contrato', 'Firma de contrato'
        MARKETING = 'marketing', 'Marketing'
        PUBLICAR = 'publicar', 'Publicar'
        CANCELADO = 'cancelado', 'Cancelado'

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE, related_name='sale_processes'
    )
    property = models.ForeignKey(
        'properties.Property', on_delete=models.CASCADE, related_name='sale_processes'
    )
    client_membership = models.ForeignKey(
        'users.TenantMembership', on_delete=models.CASCADE,
        null=True, blank=True, related_name='client_sale_processes'
    )
    agent_membership = models.ForeignKey(
        'users.TenantMembership', on_delete=models.CASCADE,
        null=True, blank=True, related_name='agent_sale_processes'
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NUEVO
    )
    name_form = models.CharField(max_length=255, blank=True, default='')
    phone_form = models.CharField(max_length=50, blank=True, default='')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sale_processes'

    def __str__(self):
        return f'SaleProcess({self.pk}) — {self.status}'


class ProcessStatusHistory(models.Model):
    class ProcessType(models.TextChoices):
        PURCHASE = 'purchase', 'Compra'
        SALE = 'sale', 'Venta'

    process_type = models.CharField(max_length=10, choices=ProcessType.choices)
    process_id = models.PositiveIntegerField()
    previous_status = models.CharField(max_length=50, blank=True)
    new_status = models.CharField(max_length=50)
    changed_by_membership = models.ForeignKey(
        'users.TenantMembership', on_delete=models.CASCADE,
        related_name='status_history_changes'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'process_status_history'

    def __str__(self):
        return f'{self.process_type}:{self.process_id} → {self.new_status}'


class SellerLead(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'Nuevo'
        CONTACTED = 'contacted', 'Contactado'
        IN_REVIEW = 'in_review', 'En revisión'
        CONVERTED = 'converted', 'Convertido'
        REJECTED = 'rejected', 'Rechazado'

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE, related_name='seller_leads'
    )
    full_name = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    phone = models.CharField(max_length=50)
    property_type = models.CharField(max_length=20)
    location = models.CharField(max_length=255, blank=True)
    square_meters = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    bedrooms = models.IntegerField(null=True, blank=True)
    bathrooms = models.IntegerField(null=True, blank=True)
    expected_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.NEW)
    assigned_agent_membership = models.ForeignKey(
        'users.TenantMembership', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_seller_leads'
    )
    created_by_membership = models.ForeignKey(
        'users.TenantMembership', on_delete=models.CASCADE,
        null=True, blank=True, related_name='created_seller_leads'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'seller_leads'

    def __str__(self):
        return f'SellerLead({self.pk}) — {self.full_name}'

    def save(self, *args, **kwargs):
        """
        Override save to auto-convert to property + sale process when status changes to 'converted'.
        """
        # Check if this is an update (object already exists in DB)
        is_update = self.pk is not None

        if is_update:
            # Get the original object from DB to check if status changed
            original = SellerLead.objects.get(pk=self.pk)
            status_changed_to_converted = (
                original.status != self.Status.CONVERTED and
                self.status == self.Status.CONVERTED
            )

            # If status changed to 'converted' and agent is assigned, auto-convert
            if status_changed_to_converted and self.assigned_agent_membership:
                # First, save the model
                super().save(*args, **kwargs)

                # Then run the conversion logic
                from .services import convert_seller_lead
                try:
                    convert_seller_lead(self, self.assigned_agent_membership)
                except Exception:
                    # If conversion fails, revert status back to original
                    self.status = original.status
                    super().save(*args, **kwargs)
                    raise

                return  # Already saved above

        # Normal save for non-converted states or first creation
        super().save(*args, **kwargs)
