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
