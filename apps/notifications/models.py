from django.db import models


class Notification(models.Model):
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE, related_name='notifications'
    )
    membership = models.ForeignKey(
        'users.TenantMembership', on_delete=models.CASCADE, related_name='notifications'
    )
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    notification_type = models.CharField(max_length=50, blank=True)
    is_read = models.BooleanField(default=False)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f'Notification({self.pk}) — {self.title}'
