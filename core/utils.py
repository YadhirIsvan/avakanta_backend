from datetime import date


def generate_matricula(tenant_id):
    """
    Genera una matrícula de cita con formato CLI-{año}-{consecutivo}.
    El consecutivo es por tenant y por año (reinicia en 001 cada año).
    """
    from apps.appointments.models import Appointment

    year = date.today().year
    count = Appointment.objects.filter(
        tenant_id=tenant_id,
        created_at__year=year
    ).count()
    consecutive = str(count + 1).zfill(3)
    return f'CLI-{year}-{consecutive}'


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
