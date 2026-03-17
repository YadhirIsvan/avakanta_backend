from django.core.management.base import BaseCommand

from apps.users.otp import cleanup_expired_otps


class Command(BaseCommand):
    help = "Elimina OTPs expirados de la base de datos"

    def handle(self, *args, **options):
        count = cleanup_expired_otps()
        self.stdout.write(
            self.style.SUCCESS(f"Eliminados {count} OTPs expirados.")
        )
