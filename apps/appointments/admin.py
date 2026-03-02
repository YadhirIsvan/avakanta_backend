from django.contrib import admin

from .models import AppointmentSettings, AgentSchedule, ScheduleBreak, AgentUnavailability, Appointment


class ScheduleBreakInline(admin.TabularInline):
    model = ScheduleBreak
    extra = 0
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AppointmentSettings)
class AppointmentSettingsAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'slot_duration_minutes', 'max_advance_days', 'min_advance_hours', 'day_start_time', 'day_end_time')
    raw_id_fields = ('tenant',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AgentSchedule)
class AgentScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'agent_membership', 'tenant', 'start_time', 'end_time', 'is_active', 'priority')
    list_filter = ('is_active', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
    search_fields = ('name',)
    raw_id_fields = ('tenant', 'agent_membership')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ScheduleBreakInline]


@admin.register(ScheduleBreak)
class ScheduleBreakAdmin(admin.ModelAdmin):
    list_display = ('name', 'schedule', 'break_type', 'start_time', 'end_time')
    list_filter = ('break_type',)
    raw_id_fields = ('schedule',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AgentUnavailability)
class AgentUnavailabilityAdmin(admin.ModelAdmin):
    list_display = ('agent_membership', 'tenant', 'start_date', 'end_date', 'reason')
    list_filter = ('reason',)
    raw_id_fields = ('tenant', 'agent_membership')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('matricula', 'property', 'client_name', 'agent_membership', 'scheduled_date', 'scheduled_time', 'status')
    list_filter = ('status', 'tenant')
    search_fields = ('matricula', 'client_name', 'client_email')
    raw_id_fields = ('tenant', 'property', 'client_membership', 'agent_membership')
    readonly_fields = ('created_at', 'updated_at')
