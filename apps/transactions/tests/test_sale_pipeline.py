"""
Tests del pipeline de venta y seller leads (T-081).

Cubren los criterios:
- Conversión de lead crea Property + SaleProcess en una transacción
- Si la conversión falla, nada se crea (rollback)
- status=publicacion actualiza la propiedad a listing_type=sale, status=disponible
"""
from unittest.mock import patch

from django.db import IntegrityError
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership, AgentProfile
from apps.properties.models import Property
from apps.transactions.models import SaleProcess, SellerLead, ProcessStatusHistory
from apps.transactions.services import convert_seller_lead, update_sale_process_status


def _token(user):
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


class SalePipelineSetup(APITestCase):
    """Base: tenant, admin, agente y datos mínimos."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Sale Tenant', slug='sale-tenant',
            email='sale@test.com', is_active=True,
        )

        # Admin
        self.admin_user = User.objects.create(email='admin_sale@test.com', is_active=True)
        self.admin_m = TenantMembership.objects.create(
            user=self.admin_user, tenant=self.tenant,
            role=TenantMembership.Role.ADMIN, is_active=True,
        )
        self.token = _token(self.admin_user)

        # Agent
        agent_user = User.objects.create(email='agent_sale@test.com', is_active=True)
        self.agent_m = TenantMembership.objects.create(
            user=agent_user, tenant=self.tenant,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        AgentProfile.objects.create(membership=self.agent_m)

        # SellerLead
        self.lead = SellerLead.objects.create(
            tenant=self.tenant,
            created_by_membership=self.admin_m,
            full_name='Ana García',
            email='ana@example.com',
            phone='+52 272 000 0001',
            property_type='house',
            expected_price='1200000.00',
            status=SellerLead.Status.NEW,
        )


# ── Conversión de seller lead ──────────────────────────────────────────────────

class TestSellerLeadConversion(SalePipelineSetup):
    """POST /admin/seller-leads/{id}/convert → crea Property + SaleProcess."""

    def _convert_url(self):
        return f'/api/v1/admin/seller-leads/{self.lead.pk}/convert'

    def test_conversion_returns_201_with_ids(self):
        resp = self.client.post(
            self._convert_url(),
            {'agent_membership_id': self.agent_m.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIn('property_id', resp.data)
        self.assertIn('sale_process_id', resp.data)

    def test_conversion_creates_property(self):
        props_before = Property.objects.filter(tenant=self.tenant).count()
        self.client.post(
            self._convert_url(),
            {'agent_membership_id': self.agent_m.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(
            Property.objects.filter(tenant=self.tenant).count(),
            props_before + 1,
        )

    def test_conversion_creates_sale_process(self):
        procs_before = SaleProcess.objects.filter(tenant=self.tenant).count()
        self.client.post(
            self._convert_url(),
            {'agent_membership_id': self.agent_m.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(
            SaleProcess.objects.filter(tenant=self.tenant).count(),
            procs_before + 1,
        )

    def test_conversion_sets_lead_status_to_converted(self):
        self.client.post(
            self._convert_url(),
            {'agent_membership_id': self.agent_m.pk},
            format='json',
            **_auth(self.token),
        )
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, SellerLead.Status.CONVERTED)

    def test_conversion_property_has_pending_listing(self):
        resp = self.client.post(
            self._convert_url(),
            {'agent_membership_id': self.agent_m.pk},
            format='json',
            **_auth(self.token),
        )
        prop = Property.objects.get(pk=resp.data['property_id'])
        self.assertEqual(prop.listing_type, 'pending_listing')

    def test_conversion_already_converted_lead_returns_400(self):
        """Un lead ya convertido no puede convertirse de nuevo."""
        self.lead.status = SellerLead.Status.CONVERTED
        self.lead.save()
        resp = self.client.post(
            self._convert_url(),
            {'agent_membership_id': self.agent_m.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_conversion_nonexistent_lead_returns_404(self):
        resp = self.client.post(
            '/api/v1/admin/seller-leads/99999/convert',
            {'agent_membership_id': self.agent_m.pk},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)


# ── Rollback atómico ───────────────────────────────────────────────────────────

class TestSellerLeadConversionRollback(SalePipelineSetup):
    """Si la conversión falla, nada se crea (transaction.atomic rollback)."""

    def test_rollback_on_sale_process_create_failure(self):
        """
        Si SaleProcess.objects.create falla, el Property tampoco queda en DB.
        Verificado llamando directamente al servicio con un mock.
        """
        props_before = Property.objects.filter(tenant=self.tenant).count()
        sales_before = SaleProcess.objects.filter(tenant=self.tenant).count()

        # Patch SaleProcess.objects.create para que falle
        with patch(
            'apps.transactions.services.SaleProcess.objects.create',
            side_effect=IntegrityError('simulated failure'),
        ):
            with self.assertRaises(IntegrityError):
                convert_seller_lead(
                    lead=self.lead,
                    agent_membership=self.agent_m,
                )

        # Nada debe haberse creado (rollback del savepoint)
        self.assertEqual(
            Property.objects.filter(tenant=self.tenant).count(),
            props_before,
        )
        self.assertEqual(
            SaleProcess.objects.filter(tenant=self.tenant).count(),
            sales_before,
        )

    def test_rollback_leaves_lead_status_unchanged(self):
        """Si la conversión falla, el lead sigue en su estado original."""
        original_status = self.lead.status

        with patch(
            'apps.transactions.services.SaleProcess.objects.create',
            side_effect=IntegrityError('simulated failure'),
        ):
            with self.assertRaises(IntegrityError):
                convert_seller_lead(
                    lead=self.lead,
                    agent_membership=self.agent_m,
                )

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, original_status)


# ── status=publicacion actualiza la propiedad ─────────────────────────────────

class TestSaleProcessPublicacion(SalePipelineSetup):
    """PATCH .../status con publicacion → property.listing_type=sale, status=disponible."""

    def setUp(self):
        super().setUp()

        # Client membership needed for SaleProcess
        client_user = User.objects.create(email='client_sale@test.com', is_active=True)
        self.client_m = TenantMembership.objects.create(
            user=client_user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT, is_active=True,
        )

        # Property in pending_listing (before publication)
        self.prop = Property.objects.create(
            tenant=self.tenant,
            title='Propiedad en venta',
            listing_type='pending_listing',
            status='documentacion',
            property_type='house',
            price=1_000_000,
        )

        # SaleProcess linked to the property
        self.sale_process = SaleProcess.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_m,
            agent_membership=self.agent_m,
            status=SaleProcess.Status.MARKETING,
        )

    def _status_url(self):
        return f'/api/v1/admin/sale-processes/{self.sale_process.pk}/status'

    def test_publicacion_sets_property_listing_type_to_sale(self):
        self.client.patch(
            self._status_url(),
            {'status': SaleProcess.Status.PUBLICAR, 'notes': ''},
            format='json',
            **_auth(self.token),
        )
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.listing_type, 'sale')

    def test_publicacion_sets_property_status_to_disponible(self):
        self.client.patch(
            self._status_url(),
            {'status': SaleProcess.Status.PUBLICAR, 'notes': ''},
            format='json',
            **_auth(self.token),
        )
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.status, 'disponible')

    def test_publicacion_updates_sale_process_status(self):
        resp = self.client.patch(
            self._status_url(),
            {'status': SaleProcess.Status.PUBLICAR, 'notes': ''},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], SaleProcess.Status.PUBLICAR)

    def test_publicacion_creates_history_record(self):
        self.client.patch(
            self._status_url(),
            {'status': SaleProcess.Status.PUBLICAR, 'notes': ''},
            format='json',
            **_auth(self.token),
        )
        history = ProcessStatusHistory.objects.filter(
            process_type='sale',
            process_id=self.sale_process.pk,
        )
        self.assertEqual(history.count(), 1)

    def test_other_status_does_not_change_property(self):
        """Pasar a evaluacion NO cambia la propiedad."""
        self.sale_process.status = SaleProcess.Status.CONTACTO_INICIAL
        self.sale_process.save()

        self.client.patch(
            self._status_url(),
            {'status': 'evaluacion', 'notes': ''},
            format='json',
            **_auth(self.token),
        )
        self.prop.refresh_from_db()
        # Property unchanged
        self.assertEqual(self.prop.listing_type, 'pending_listing')
        self.assertEqual(self.prop.status, 'documentacion')

    def test_publicacion_via_service_directly(self):
        """
        Verificación directa del servicio sin HTTP:
        update_sale_process_status con publicar → propiedad actualizada.
        """
        update_sale_process_status(
            process=self.sale_process,
            new_status=SaleProcess.Status.PUBLICAR,
            notes='',
            changed_by_membership=self.admin_m,
        )
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.listing_type, 'sale')
        self.assertEqual(self.prop.status, 'disponible')
