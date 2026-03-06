from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
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
    - Uses the membership of the user who created the lead (created_by_membership)
    - Creates Property with listing_type=pending_listing, status=documentacion.
    - Creates SaleProcess with status=seller_completed with the actual user account.
    - Email and phone from lead are used for contact info only.
    - Updates lead.status=converted (using .update() to avoid triggering save() hook).
    Returns (property, sale_process).
    """
    from apps.properties.models import Property
    from apps.locations.models import City
    from django.utils import timezone

    # 1. Validate that the lead has a creator (required for conversion)
    if not lead.created_by_membership:
        raise ValueError('El lead debe haber sido creado por un usuario autenticado para convertirse')

    # 2. Use the membership of the user who actually created the lead
    client_membership = lead.created_by_membership

    # 3. Generate property title based on location and type
    location = lead.location or 'Propiedad'
    property_type_display = lead.property_type.capitalize()
    title = f'{property_type_display} en {location}'

    # 4. Find City by name (location)
    city = None
    if lead.location:
        city = City.objects.filter(name__iexact=lead.location).first()

    # 5. Create Property (minimal, pending listing)
    prop = Property.objects.create(
        tenant=lead.tenant,
        title=title,
        listing_type='pending_listing',
        status='documentacion',
        property_type=lead.property_type,
        price=lead.expected_price or 0,
        bedrooms=lead.bedrooms,
        bathrooms=lead.bathrooms,
        land_sqm=lead.square_meters,
        city=city,
        address_neighborhood=lead.location,
    )

    # 6. Create SaleProcess with seller_completed status
    sale_process = SaleProcess.objects.create(
        tenant=lead.tenant,
        property=prop,
        client_membership=client_membership,
        agent_membership=agent_membership,
        status=SaleProcess.Status.SELLER_COMPLETED,
        notes=f'Convertido desde seller lead #{lead.pk} - {lead.full_name} ({lead.email})',
    )

    # 7. Update lead using .update() to avoid triggering save() hook
    # Import SellerLead here to avoid circular imports
    from .models import SellerLead
    SellerLead.objects.filter(pk=lead.pk).update(
        status='converted',
        updated_at=timezone.now()
    )

    return prop, sale_process


def _period_date_from(period):
    """Returns the start date for the given period, or None for 'all'."""
    today = date.today()
    if period == 'month':
        return today.replace(day=1)
    if period == 'quarter':
        month = today.month - (today.month - 1) % 3
        return today.replace(month=month, day=1)
    if period == 'year':
        return today.replace(month=1, day=1)
    return None  # 'all'


def get_insights(tenant, period='month'):
    """Compute analytics for the tenant within the given period."""
    from apps.properties.models import Property
    from apps.users.models import AgentProfile

    date_from = _period_date_from(period)

    # Base closed processes queryset
    closed_qs = PurchaseProcess.objects.filter(tenant=tenant, status='cerrado')
    if date_from:
        closed_qs = closed_qs.filter(closed_at__date__gte=date_from)

    # All processes (leads) in period
    all_qs = PurchaseProcess.objects.filter(tenant=tenant)
    if date_from:
        all_qs = all_qs.filter(created_at__date__gte=date_from)

    # 1. Sales by month
    sales_by_month_raw = (
        closed_qs
        .annotate(month=TruncMonth('closed_at'))
        .values('month')
        .annotate(count=Count('id'), total_amount=Sum('sale_price'))
        .order_by('month')
    )
    sales_by_month = [
        {
            'month': row['month'].strftime('%Y-%m'),
            'count': row['count'],
            'total_amount': str(row['total_amount'] or 0),
        }
        for row in sales_by_month_raw
    ]

    # 2. Distribution by property type (closed sales)
    total_closed = closed_qs.count()
    dist_raw = (
        closed_qs
        .values('property__property_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    distribution_by_type = [
        {
            'property_type': row['property__property_type'],
            'count': row['count'],
            'percentage': round(row['count'] / total_closed * 100, 1) if total_closed else 0,
        }
        for row in dist_raw
    ]

    # 3. Activity by zone
    prop_qs = Property.objects.filter(tenant=tenant, is_active=True)
    zones = set(prop_qs.exclude(zone__isnull=True).exclude(zone='').values_list('zone', flat=True))
    activity_by_zone = []
    for zone in zones:
        if not zone:
            continue
        zone_props = prop_qs.filter(zone=zone)
        views = zone_props.aggregate(v=Sum('views'))['v'] or 0
        leads = all_qs.filter(property__zone=zone).count()
        sales = closed_qs.filter(property__zone=zone).count()
        activity_by_zone.append({'zone': zone, 'views': views, 'leads': leads, 'sales': sales})

    # 4. Top agents
    top_agents_raw = (
        AgentProfile.objects
        .filter(membership__tenant=tenant, membership__is_active=True)
        .select_related('membership__user')
        .annotate(
            sales_count=Count(
                'membership__agent_purchase_processes',
                filter=Q(membership__agent_purchase_processes__status='cerrado'),
                distinct=True,
            ),
            leads_count=Count('membership__agent_purchase_processes', distinct=True),
        )
        .order_by('-sales_count')[:10]
    )
    top_agents = [
        {
            'id': ap.pk,
            'name': ap.membership.user.get_full_name() or ap.membership.user.email,
            'sales_count': ap.sales_count,
            'leads_count': ap.leads_count,
            'score': str(ap.score),
        }
        for ap in top_agents_raw
    ]

    # 5. Summary
    total_properties = Property.objects.filter(tenant=tenant, is_active=True).count()
    total_sales = closed_qs.count()
    total_revenue = closed_qs.aggregate(r=Sum('sale_price'))['r'] or 0
    active_leads = PurchaseProcess.objects.filter(
        tenant=tenant
    ).exclude(status__in=['cerrado', 'cancelado']).count()

    return {
        'period': period,
        'sales_by_month': sales_by_month,
        'distribution_by_type': distribution_by_type,
        'activity_by_zone': activity_by_zone,
        'top_agents': top_agents,
        'summary': {
            'total_properties': total_properties,
            'total_sales': total_sales,
            'total_revenue': str(total_revenue),
            'active_leads': active_leads,
        },
    }
