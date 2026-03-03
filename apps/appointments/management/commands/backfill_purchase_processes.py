"""
Management command: backfill_purchase_processes

Creates PurchaseProcess records for existing 'primera_visita' appointments
that were created before the auto-sync feature was added.

Usage:
    python manage.py backfill_purchase_processes
    python manage.py backfill_purchase_processes --dry-run   (preview only)
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.appointments.models import Appointment
from apps.transactions.models import PurchaseProcess


VISITA_STATUSES = {
    Appointment.Status.EN_PROGRESO,
    Appointment.Status.COMPLETADA,
}

PROGRESS = {'lead': 0, 'visita': 11}


class Command(BaseCommand):
    help = 'Backfills PurchaseProcess records for existing primera_visita appointments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would happen without making any changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be saved'))

        # Only primera_visita appointments that have a linked client membership
        appointments = (
            Appointment.objects
            .filter(
                appointment_type=Appointment.AppointmentType.PRIMERA_VISITA,
                client_membership__isnull=False,
            )
            .select_related('property', 'client_membership', 'agent_membership', 'tenant')
            .order_by('created_at')
        )

        created = 0
        skipped = 0
        downgraded = 0

        for appt in appointments:
            existing = PurchaseProcess.objects.filter(
                tenant=appt.tenant,
                property=appt.property,
                client_membership=appt.client_membership,
            ).exclude(status='cancelado').first()

            if existing:
                # Process already exists — this appointment should be 'seguimiento'
                self.stdout.write(
                    f'  SKIP appt #{appt.pk} ({appt.matricula}): '
                    f'process #{existing.pk} already exists in status "{existing.status}" '
                    f'→ downgrading appointment to seguimiento'
                )
                if not dry_run:
                    with transaction.atomic():
                        appt.appointment_type = Appointment.AppointmentType.SEGUIMIENTO
                        appt.save(update_fields=['appointment_type'])
                downgraded += 1
                skipped += 1
            else:
                # Determine process status based on appointment status
                if appt.status in VISITA_STATUSES:
                    proc_status = PurchaseProcess.Status.VISITA
                    progress = PROGRESS['visita']
                else:
                    proc_status = PurchaseProcess.Status.LEAD
                    progress = PROGRESS['lead']

                self.stdout.write(
                    f'  CREATE process for appt #{appt.pk} ({appt.matricula}): '
                    f'client={appt.client_membership_id}, '
                    f'property={appt.property.title!r}, '
                    f'status={proc_status}'
                )
                if not dry_run:
                    with transaction.atomic():
                        PurchaseProcess.objects.create(
                            tenant=appt.tenant,
                            property=appt.property,
                            client_membership=appt.client_membership,
                            agent_membership=appt.agent_membership,
                            status=proc_status,
                            overall_progress=progress,
                            notes=f'Retroactivo: cita #{appt.pk} ({appt.matricula})',
                        )
                created += 1

        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'DRY RUN complete — would create {created} processes, '
                f'downgrade {downgraded} appointments to seguimiento, '
                f'skip {skipped} (already had a process)'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Done — created {created} processes, '
                f'downgraded {downgraded} appointments to seguimiento'
            ))
