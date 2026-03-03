from django.db import models


class AppointmentSettings(models.Model):
    tenant = models.OneToOneField(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='appointment_settings'
    )
    slot_duration_minutes = models.PositiveIntegerField(default=60)
    max_advance_days = models.PositiveIntegerField(default=30)
    min_advance_hours = models.PositiveIntegerField(default=24)
    day_start_time = models.TimeField(default='09:00')
    day_end_time = models.TimeField(default='18:00')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'appointment_settings'

    def __str__(self):
        return f'AppointmentSettings({self.tenant})'


class AgentSchedule(models.Model):
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE, related_name='agent_schedules'
    )
    agent_membership = models.ForeignKey(
        'users.TenantMembership', on_delete=models.CASCADE, related_name='schedules'
    )
    name = models.CharField(max_length=100)
    monday = models.BooleanField(default=False)
    tuesday = models.BooleanField(default=False)
    wednesday = models.BooleanField(default=False)
    thursday = models.BooleanField(default=False)
    friday = models.BooleanField(default=False)
    saturday = models.BooleanField(default=False)
    sunday = models.BooleanField(default=False)
    start_time = models.TimeField()
    end_time = models.TimeField()
    has_lunch_break = models.BooleanField(default=True)
    lunch_start = models.TimeField(null=True, blank=True)
    lunch_end = models.TimeField(null=True, blank=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agent_schedules'

    def __str__(self):
        return f'{self.name} ({self.agent_membership})'


class ScheduleBreak(models.Model):
    class BreakType(models.TextChoices):
        LUNCH = 'lunch', 'Comida'
        COFFEE = 'coffee', 'Café'
        REST = 'rest', 'Descanso'
        OTHER = 'other', 'Otro'

    schedule = models.ForeignKey(
        AgentSchedule, on_delete=models.CASCADE, related_name='breaks'
    )
    break_type = models.CharField(max_length=10, choices=BreakType.choices)
    name = models.CharField(max_length=100, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'schedule_breaks'

    def __str__(self):
        return f'{self.name or self.break_type} {self.start_time}-{self.end_time}'


class AgentUnavailability(models.Model):
    class Reason(models.TextChoices):
        VACATION = 'vacation', 'Vacaciones'
        SICK_LEAVE = 'sick_leave', 'Incapacidad'
        PERSONAL = 'personal', 'Asunto personal'
        TRAINING = 'training', 'Capacitación'
        OTHER = 'other', 'Otro'

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE, related_name='agent_unavailabilities'
    )
    agent_membership = models.ForeignKey(
        'users.TenantMembership', on_delete=models.CASCADE, related_name='unavailabilities'
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agent_unavailabilities'

    def __str__(self):
        return f'{self.agent_membership} unavailable {self.start_date}–{self.end_date}'


class Appointment(models.Model):
    class Status(models.TextChoices):
        PROGRAMADA = 'programada', 'Programada'
        CONFIRMADA = 'confirmada', 'Confirmada'
        EN_PROGRESO = 'en_progreso', 'En progreso'
        COMPLETADA = 'completada', 'Completada'
        CANCELADA = 'cancelada', 'Cancelada'
        NO_SHOW = 'no_show', 'No show'
        REAGENDADA = 'reagendada', 'Reagendada'

    class AppointmentType(models.TextChoices):
        PRIMERA_VISITA   = 'primera_visita',   'Primera Visita'
        SEGUIMIENTO      = 'seguimiento',      'Seguimiento'
        CIERRE_CONTRATO  = 'cierre_contrato',  'Cierre de Contrato'
        ENTREGA_LLAVES   = 'entrega_llaves',   'Entrega de Llaves'
        AVALUO           = 'avaluo',           'Avalúo'

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE, related_name='appointments'
    )
    property = models.ForeignKey(
        'properties.Property', on_delete=models.CASCADE, related_name='appointments'
    )
    client_membership = models.ForeignKey(
        'users.TenantMembership', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='client_appointments'
    )
    agent_membership = models.ForeignKey(
        'users.TenantMembership', on_delete=models.CASCADE, related_name='agent_appointments'
    )
    client_name = models.CharField(max_length=255, blank=True)
    client_email = models.CharField(max_length=255, blank=True)
    client_phone = models.CharField(max_length=50, blank=True)
    matricula = models.CharField(max_length=20, unique=True)
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.PROGRAMADA
    )
    appointment_type = models.CharField(
        max_length=20,
        choices=AppointmentType.choices,
        default=AppointmentType.PRIMERA_VISITA,
    )
    notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'appointments'

    def __str__(self):
        return f'{self.matricula} — {self.scheduled_date} {self.scheduled_time}'
