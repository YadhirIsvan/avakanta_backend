from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'membership', 'tenant', 'notification_type', 'is_read', 'created_at')
    list_filter = ('is_read', 'notification_type', 'tenant')
    search_fields = ('title', 'message', 'membership__user__email')
    raw_id_fields = ('tenant', 'membership')
    readonly_fields = ('created_at',)
