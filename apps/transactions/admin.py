from django.contrib import admin

from .models import PurchaseProcess, SaleProcess, ProcessStatusHistory, SellerLead


@admin.register(PurchaseProcess)
class PurchaseProcessAdmin(admin.ModelAdmin):
    list_display = ('id', 'property', 'client_membership', 'agent_membership', 'status', 'overall_progress', 'created_at')
    list_filter = ('status', 'tenant')
    search_fields = ('property__title', 'client_membership__user__email')
    raw_id_fields = ('tenant', 'property', 'client_membership', 'agent_membership')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Proceso', {'fields': ('tenant', 'property', 'client_membership', 'agent_membership', 'status', 'overall_progress', 'notes')}),
        ('Cierre', {'fields': ('sale_price', 'payment_method', 'closed_at')}),
        ('Fechas', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(SaleProcess)
class SaleProcessAdmin(admin.ModelAdmin):
    list_display = ('id', 'property', 'client_membership', 'agent_membership', 'status', 'created_at')
    list_filter = ('status', 'tenant')
    search_fields = ('property__title', 'client_membership__user__email')
    raw_id_fields = ('tenant', 'property', 'client_membership', 'agent_membership')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ProcessStatusHistory)
class ProcessStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('process_type', 'process_id', 'previous_status', 'new_status', 'changed_by_membership', 'created_at')
    list_filter = ('process_type',)
    raw_id_fields = ('changed_by_membership',)
    readonly_fields = ('created_at',)


@admin.register(SellerLead)
class SellerLeadAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'phone', 'property_type', 'status', 'assigned_agent_membership', 'created_at')
    list_filter = ('status', 'property_type', 'tenant')
    search_fields = ('full_name', 'email', 'phone')
    raw_id_fields = ('tenant', 'assigned_agent_membership')
    readonly_fields = ('created_at', 'updated_at')
