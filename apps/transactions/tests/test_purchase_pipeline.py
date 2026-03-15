"""
Tests del pipeline de compra (T-080).

Cubren los criterios:
- Cambio a `visita` → overall_progress=11, entrada en historial
- Cambio a `cerrado` sin sale_price → 400
- Cambio a `cerrado` con datos completos → closed_at se llena
- Historial tiene previous_status y new_status correctos
"""
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership, AgentProfile
from apps.properties.models import Property
from apps.transactions.models import PurchaseProcess, ProcessStatusHistory


def _token(user):
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


def _status_url(pk):
    return f'/api/v1/admin/purchase-processes/{pk}/status'


class PurchasePipelineSetup(APITestCase):
    """Base: tenant, admin, agente, cliente y un proceso en estado 'lead'."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Pipeline Tenant', slug='pipeline-tenant',
            email='pipeline@test.com',
        )

        # Admin
        self.admin_user = User.objects.create(email='admin_pipe@test.com')
        self.admin_m = TenantMembership.objects.create(
            user=self.admin_user, tenant=self.tenant,
            role=TenantMembership.Role.ADMIN,
        )
        self.token = _token(self.admin_user)

        # Agent
        agent_user = User.objects.create(email='agent_pipe@test.com')
        self.agent_m = TenantMembership.objects.create(
            user=agent_user, tenant=self.tenant,
            role=TenantMembership.Role.AGENT,
        )
        AgentProfile.objects.create(membership=self.agent_m)

        # Client
        client_user = User.objects.create(email='client_pipe@test.com')
        self.client_m = TenantMembership.objects.create(
            user=client_user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT,
        )

        # Property + PurchaseProcess (initial status: lead)
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Casa Pipeline',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000,
        )
        self.process = PurchaseProcess.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_m,
            agent_membership=self.agent_m,
            status=PurchaseProcess.Status.LEAD,
            overall_progress=0,
        )


class TestStatusTransitionToVisita(PurchasePipelineSetup):
    """Cambio a 'visita' → overall_progress=11, registro en historial."""

    def test_transition_to_visita_sets_overall_progress_11(self):
        resp = self.client.patch(
            _status_url(self.process.pk),
            {'status': 'visita', 'notes': 'Primera visita agendada'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'visita')
        self.assertEqual(resp.data['overall_progress'], 11)

    def test_transition_to_visita_creates_history_record(self):
        self.client.patch(
            _status_url(self.process.pk),
            {'status': 'visita', 'notes': ''},
            format='json',
            **_auth(self.token),
        )
        history = ProcessStatusHistory.objects.filter(
            process_type='purchase',
            process_id=self.process.pk,
        )
        self.assertEqual(history.count(), 1)

    def test_transition_to_visita_history_has_correct_statuses(self):
        self.client.patch(
            _status_url(self.process.pk),
            {'status': 'visita', 'notes': ''},
            format='json',
            **_auth(self.token),
        )
        entry = ProcessStatusHistory.objects.get(
            process_type='purchase',
            process_id=self.process.pk,
        )
        self.assertEqual(entry.previous_status, 'lead')
        self.assertEqual(entry.new_status, 'visita')

    def test_sequential_transitions_create_correct_history_chain(self):
        """lead → visita → interes: historial refleja la cadena correcta."""
        self.client.patch(
            _status_url(self.process.pk),
            {'status': 'visita', 'notes': ''},
            format='json',
            **_auth(self.token),
        )
        self.client.patch(
            _status_url(self.process.pk),
            {'status': 'interes', 'notes': ''},
            format='json',
            **_auth(self.token),
        )
        entries = ProcessStatusHistory.objects.filter(
            process_type='purchase',
            process_id=self.process.pk,
        ).order_by('created_at')

        self.assertEqual(entries.count(), 2)
        self.assertEqual(entries[0].previous_status, 'lead')
        self.assertEqual(entries[0].new_status, 'visita')
        self.assertEqual(entries[1].previous_status, 'visita')
        self.assertEqual(entries[1].new_status, 'interes')


class TestStatusTransitionToCerrado(PurchasePipelineSetup):
    """Validaciones al cerrar y llenado de closed_at."""

    def test_cerrado_without_sale_price_returns_400(self):
        resp = self.client.patch(
            _status_url(self.process.pk),
            {'status': 'cerrado'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_cerrado_without_payment_method_returns_400(self):
        resp = self.client.patch(
            _status_url(self.process.pk),
            {'status': 'cerrado', 'sale_price': '950000.00'},
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_cerrado_with_complete_data_returns_200(self):
        resp = self.client.patch(
            _status_url(self.process.pk),
            {
                'status': 'cerrado',
                'sale_price': '950000.00',
                'payment_method': 'credito_hipotecario',
                'notes': 'Proceso cerrado exitosamente',
            },
            format='json',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'cerrado')
        self.assertEqual(resp.data['overall_progress'], 100)

    def test_cerrado_fills_closed_at(self):
        self.client.patch(
            _status_url(self.process.pk),
            {
                'status': 'cerrado',
                'sale_price': '950000.00',
                'payment_method': 'contado',
            },
            format='json',
            **_auth(self.token),
        )
        self.process.refresh_from_db()
        self.assertIsNotNone(self.process.closed_at)

    def test_cerrado_stores_sale_price_and_payment_method(self):
        self.client.patch(
            _status_url(self.process.pk),
            {
                'status': 'cerrado',
                'sale_price': '1250000.00',
                'payment_method': 'credito_hipotecario',
            },
            format='json',
            **_auth(self.token),
        )
        self.process.refresh_from_db()
        self.assertEqual(str(self.process.sale_price), '1250000.00')
        self.assertEqual(self.process.payment_method, 'credito_hipotecario')


class TestProgressMap(PurchasePipelineSetup):
    """Verifica que el mapa de progreso es correcto para cada estado."""

    EXPECTED_PROGRESS = {
        'visita': 11,
        'interes': 22,
        'pre_aprobacion': 33,
        'avaluo': 44,
        'credito': 56,
        'docs_finales': 67,
        'escrituras': 78,
    }

    def _transition(self, status):
        return self.client.patch(
            _status_url(self.process.pk),
            {'status': status, 'notes': ''},
            format='json',
            **_auth(self.token),
        )

    def test_each_status_sets_correct_progress(self):
        for status, expected in self.EXPECTED_PROGRESS.items():
            with self.subTest(status=status):
                resp = self._transition(status)
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(
                    resp.data['overall_progress'], expected,
                    f'Status {status!r} debería tener progress={expected}',
                )
