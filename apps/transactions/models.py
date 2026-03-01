from django.db import models


class PurchaseProcess(models.Model):
    """Placeholder — implementación completa en T-036."""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE)

    class Meta:
        db_table = 'purchase_processes'

    def __str__(self):
        return f'PurchaseProcess({self.pk})'
