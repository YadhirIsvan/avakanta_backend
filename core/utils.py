from datetime import date

from django.db import transaction


def generate_matricula(tenant_id):
    """
    Genera una matrícula de cita con formato CLI-{año}-{consecutivo}.
    El consecutivo es por tenant y por año (reinicia en 001 cada año).
    Thread-safe: bloquea la fila del Tenant con SELECT FOR UPDATE para
    serializar la generación concurrente de matrículas del mismo tenant.
    """
    from apps.appointments.models import Appointment
    from apps.tenants.models import Tenant

    with transaction.atomic():
        # Bloquea la fila del tenant → serializa accesos concurrentes al mismo tenant
        Tenant.objects.select_for_update().get(pk=tenant_id)

        year = date.today().year
        prefix = f'CLI-{year}-'
        # Filtra solo matrículas con sufijo numérico para evitar errores con
        # valores de test o formatos inesperados (e.g. CLI-2026-TEST).
        matriculas = (
            Appointment.objects
            .filter(tenant_id=tenant_id, matricula__regex=rf'^CLI-{year}-\d+$')
            .values_list('matricula', flat=True)
        )
        nums = [int(m[len(prefix):]) for m in matriculas]
        next_num = max(nums) + 1 if nums else 1

        return f'{prefix}{str(next_num).zfill(3)}'


def calculate_trend(views_last_7, views_prev_7):
    """
    Compara las vistas de los últimos 7 días vs los 7 días anteriores.
    Retorna "up", "down" o "stable".
    """
    if views_prev_7 == 0:
        return 'stable' if views_last_7 == 0 else 'up'
    diff = views_last_7 - views_prev_7
    if diff > 0:
        return 'up'
    if diff < 0:
        return 'down'
    return 'stable'


def days_listed(created_at):
    """
    Calcula cuántos días lleva publicada una propiedad desde su fecha de creación.
    """
    return (date.today() - created_at.date()).days
