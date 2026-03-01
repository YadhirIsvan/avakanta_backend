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
        CONTACTO_INICIAL = 'contacto_inicial', 'Contacto inicial'
        EVALUACION = 'evaluacion', 'Evaluación'
        VALUACION = 'valuacion', 'Valuación'
        PRESENTACION = 'presentacion', 'Presentación'
        FIRMA_CONTRATO = 'firma_contrato', 'Firma de contrato'
        MARKETING = 'marketing', 'Marketing'
        PUBLICACION = 'publicacion', 'Publicación'
        CANCELADO = 'cancelado', 'Cancelado'

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE, related_name='sale_processes'
    )
    property = models.ForeignKey(
        'properties.Property', on_delete=models.CASCADE, related_name='sale_processes'
    )
    client_membership = models.ForeignKey(
        'users.TenantMembership', on_delete=models.CASCADE,
        related_name='client_sale_processes'
    )
    agent_membership = models.ForeignKey(
        'users.TenantMembership', on_delete=models.CASCADE,
        null=True, blank=True, related_name='agent_sale_processes'
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.CONTACTO_INICIAL
    )
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
