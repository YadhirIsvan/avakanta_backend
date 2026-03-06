from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, TenantMembership, AgentProfile, UserNotificationPreferences, ClientFinancialProfile, OTPCode


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'auth_provider')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    readonly_fields = ('date_joined', 'last_login')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Información personal', {'fields': ('first_name', 'last_name', 'phone', 'avatar', 'city')}),
        ('Auth', {'fields': ('auth_provider',)}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas', {'fields': ('date_joined', 'last_login')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name', 'is_staff', 'is_superuser'),
        }),
    )
    filter_horizontal = ('groups', 'user_permissions')


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'tenant', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'tenant')
    search_fields = ('user__email', 'tenant__name')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('user', 'tenant')


@admin.register(AgentProfile)
class AgentProfileAdmin(admin.ModelAdmin):
    list_display = ('membership', 'zone', 'score', 'created_at')
    search_fields = ('membership__user__email',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(UserNotificationPreferences)
class UserNotificationPreferencesAdmin(admin.ModelAdmin):
    list_display = ('membership', 'new_properties', 'price_updates', 'appointment_reminders', 'offers')
    search_fields = ('membership__user__email',)
    readonly_fields = ('updated_at',)


@admin.register(ClientFinancialProfile)
class ClientFinancialProfileAdmin(admin.ModelAdmin):
    list_display = ('membership', 'loan_type', 'monthly_income', 'calculated_budget', 'updated_at')
    list_filter = ('loan_type', 'has_infonavit')
    search_fields = ('membership__user__email',)
    readonly_fields = ('calculated_budget', 'created_at', 'updated_at')
    fieldsets = (
        ('Información del Cliente', {
            'fields': ('membership',)
        }),
        ('Datos Financieros', {
            'fields': ('loan_type', 'monthly_income', 'partner_monthly_income', 'savings_for_enganche')
        }),
        ('Infonavit', {
            'fields': ('has_infonavit', 'infonavit_subcuenta_balance')
        }),
        ('Resultado', {
            'fields': ('calculated_budget',)
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ('email', 'created_at', 'expires_at', 'is_used')
    list_filter = ('is_used',)
    search_fields = ('email',)
    readonly_fields = ('created_at',)
