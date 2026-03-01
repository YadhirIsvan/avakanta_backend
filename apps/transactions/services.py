from django.db import transaction
from django.utils import timezone

from .models import ProcessStatusHistory, PurchaseProcess, SaleProcess


PURCHASE_PROGRESS_MAP = {
    'lead': 0,
    'visita': 11,
    'interes': 22,
    'pre_aprobacion': 33,
    'avaluo': 44,
    'credito': 56,
    'docs_finales': 67,
    'escrituras': 78,
    'cerrado': 100,
    'cancelado': 0,
}


@transaction.atomic
def update_purchase_process_status(process, new_status, notes, changed_by_membership,
                                   sale_price=None, payment_method=None):
    """
    Moves a PurchaseProcess to a new status, updates progress, and logs history.
    If new_status='cerrado', fills sale_price, payment_method, closed_at.
    """
    previous_status = process.status

    process.status = new_status
    process.overall_progress = PURCHASE_PROGRESS_MAP.get(new_status, 0)

    update_fields = ['status', 'overall_progress', 'updated_at']

    if new_status == PurchaseProcess.Status.CERRADO:
        process.sale_price = sale_price
        process.payment_method = payment_method
        process.closed_at = timezone.now()
        update_fields += ['sale_price', 'payment_method', 'closed_at']

    process.save(update_fields=update_fields)

    ProcessStatusHistory.objects.create(
        process_type=ProcessStatusHistory.ProcessType.PURCHASE,
        process_id=process.pk,
        previous_status=previous_status,
        new_status=new_status,
        changed_by_membership=changed_by_membership,
        notes=notes or '',
    )

    return process


@transaction.atomic
def update_sale_process_status(process, new_status, notes, changed_by_membership):
    """
    Moves a SaleProcess to a new status and logs history.
    If new_status='publicacion', updates the property to listing_type=sale, status=disponible.
    """
    previous_status = process.status

    process.status = new_status
    process.save(update_fields=['status', 'updated_at'])

    ProcessStatusHistory.objects.create(
        process_type=ProcessStatusHistory.ProcessType.SALE,
        process_id=process.pk,
        previous_status=previous_status,
        new_status=new_status,
        changed_by_membership=changed_by_membership,
        notes=notes or '',
    )

    if new_status == SaleProcess.Status.PUBLICACION:
        process.property.listing_type = 'sale'
        process.property.status = 'disponible'
        process.property.save(update_fields=['listing_type', 'status'])

    return process


@transaction.atomic
def convert_seller_lead(lead, agent_membership):
    """
    Converts a SellerLead into a Property + SaleProcess atomically.
    - Finds or creates User by lead.email, with role=client in the tenant.
    - Creates Property with listing_type=pending_listing, status=documentacion.
    - Creates SaleProcess with status=contacto_inicial.
    - Updates lead.status=converted.
    Returns (property, sale_process).
    """
    from apps.users.models import User, TenantMembership
    from apps.properties.models import Property

    # 1. Find or create the user
    user, _ = User.objects.get_or_create(
        email=lead.email,
        defaults={'first_name': lead.full_name.split()[0] if lead.full_name else '',
                  'last_name': ' '.join(lead.full_name.split()[1:]) if lead.full_name else '',
                  'phone': lead.phone or None},
    )

    # 2. Find or create client membership in tenant
    client_membership, _ = TenantMembership.objects.get_or_create(
        user=user,
        tenant=lead.tenant,
        defaults={'role': TenantMembership.Role.CLIENT, 'is_active': True},
    )
    if client_membership.role != TenantMembership.Role.CLIENT:
        # Exists with different role — still use it
        pass

    # 3. Create Property (minimal, pending listing)
    prop = Property.objects.create(
        tenant=lead.tenant,
        title=f'Propiedad de {lead.full_name}',
        listing_type='pending_listing',
        status='documentacion',
        property_type=lead.property_type,
        price=lead.expected_price or 0,
    )

    # 4. Create SaleProcess
    sale_process = SaleProcess.objects.create(
        tenant=lead.tenant,
        property=prop,
        client_membership=client_membership,
        agent_membership=agent_membership,
        status=SaleProcess.Status.CONTACTO_INICIAL,
        notes=f'Convertido desde seller lead #{lead.pk}',
    )

    # 5. Update lead
    lead.status = 'converted'
    lead.save(update_fields=['status', 'updated_at'])

    return prop, sale_process
