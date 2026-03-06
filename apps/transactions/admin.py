from django.contrib import admin

from .models import PurchaseProcess, SaleProcess, ProcessStatusHistory, SellerLead
from .services import convert_seller_lead


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
    list_display = ('full_name', 'email', 'property_type', 'location', 'status', 'created_by_membership', 'assigned_agent_membership', 'expected_price', 'created_at')
    list_filter = ('status', 'property_type', 'tenant', 'created_at')
    list_editable = ('status', 'assigned_agent_membership')
    search_fields = ('full_name', 'email', 'phone', 'location')
    raw_id_fields = ('tenant', 'created_by_membership', 'assigned_agent_membership')
    readonly_fields = ('created_at', 'updated_at', 'created_by_membership')

    fieldsets = (
        ('Información del Vendedor', {
            'fields': ('full_name', 'email', 'phone', 'tenant', 'created_by_membership')
        }),
        ('Detalles de la Propiedad', {
            'fields': ('property_type', 'location', 'square_meters', 'bedrooms', 'bathrooms', 'expected_price')
        }),
        ('Gestión del Lead', {
            'fields': ('status', 'assigned_agent_membership', 'notes')
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['convert_selected_leads']

    def convert_selected_leads(self, request, queryset):
        """Action to convert selected seller leads to property + sale process"""
        converted = 0
        errors_no_agent = 0
        errors_already_converted = 0
        errors_exception = []

        for lead in queryset:
            # Skip already converted leads
            if lead.status == 'converted':
                errors_already_converted += 1
                continue

            # Check if agent is assigned
            if not lead.assigned_agent_membership:
                errors_no_agent += 1
                continue

            try:
                convert_seller_lead(lead, lead.assigned_agent_membership)
                converted += 1
            except Exception as e:
                errors_exception.append(f"{lead.full_name}: {str(e)}")

        # Build message
        message = f"✓ {converted} lead(s) convertido(s) a proceso de venta"
        if errors_no_agent > 0:
            message += f"\n⚠ {errors_no_agent} sin agente asignado (asigna uno primero)"
        if errors_already_converted > 0:
            message += f"\n⚠ {errors_already_converted} ya convertido(s)"
        if errors_exception:
            message += f"\n✗ Errores: {', '.join(errors_exception)}"

        self.message_user(request, message)

    convert_selected_leads.short_description = "Convertir leads seleccionados a proceso de venta"
