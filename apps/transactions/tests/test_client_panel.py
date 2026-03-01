"""
Tests del panel del cliente — subida de documentos (T-083).

- Cliente puede subir documento en pre_aprobacion (allow_upload=True) → 201
- Cliente no puede subir documento en lead (allow_upload=False) → 403
- Etapas credito y docs_finales también permiten subida
- Proceso de otro cliente → 404
"""
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership, AgentProfile
from apps.properties.models import Property
from apps.transactions.models import PurchaseProcess


def _token(user):
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


def _docs_url(pk):
    return f'/api/v1/client/purchases/{pk}/documents'


def _fake_pdf(name='doc.pdf'):
    """Retorna un SimpleUploadedFile que simula un PDF válido."""
    return SimpleUploadedFile(
        name=name,
        content=b'%PDF-1.4 fake content',
        content_type='application/pdf',
    )


class ClientDocumentUploadSetup(APITestCase):
    """Base: tenant, cliente, agente, propiedad y un PurchaseProcess."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Client Doc Tenant', slug='clientdoc-tenant',
            email='clientdoc@test.com', is_active=True,
        )

        # Cliente principal
        self.client_user = User.objects.create(
            email='client_doc@test.com', is_active=True,
        )
        self.client_m = TenantMembership.objects.create(
            user=self.client_user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT, is_active=True,
        )
        self.token = _token(self.client_user)

        # Otro cliente (para test de aislamiento)
        other_user = User.objects.create(
            email='other_client_doc@test.com', is_active=True,
        )
        self.other_client_m = TenantMembership.objects.create(
            user=other_user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT, is_active=True,
        )
        self.other_token = _token(other_user)

        # Agente
        agent_user = User.objects.create(email='agent_doc@test.com', is_active=True)
        self.agent_m = TenantMembership.objects.create(
            user=agent_user, tenant=self.tenant,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        AgentProfile.objects.create(membership=self.agent_m)

        # Propiedad
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Casa Doc',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000, is_active=True,
        )

    def _make_process(self, status):
        return PurchaseProcess.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.client_m,
            agent_membership=self.agent_m,
            status=status,
        )


class TestDocumentUploadAllowedStages(ClientDocumentUploadSetup):
    """Etapas que permiten subida (ALLOW_UPLOAD_STAGES)."""

    def test_upload_in_pre_aprobacion_returns_201(self):
        process = self._make_process('pre_aprobacion')
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                resp = self.client.post(
                    _docs_url(process.pk),
                    {'file': _fake_pdf(), 'name': 'Carta banco'},
                    format='multipart',
                    **_auth(self.token),
                )
        self.assertEqual(resp.status_code, 201)
        self.assertIn('id', resp.data)
        self.assertEqual(resp.data['document_stage'], 'pre_aprobacion')

    def test_upload_in_credito_returns_201(self):
        process = self._make_process('credito')
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                resp = self.client.post(
                    _docs_url(process.pk),
                    {'file': _fake_pdf('credito.pdf'), 'name': 'Expediente crédito'},
                    format='multipart',
                    **_auth(self.token),
                )
        self.assertEqual(resp.status_code, 201)

    def test_upload_in_docs_finales_returns_201(self):
        process = self._make_process('docs_finales')
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                resp = self.client.post(
                    _docs_url(process.pk),
                    {'file': _fake_pdf('final.pdf'), 'name': 'Docs finales'},
                    format='multipart',
                    **_auth(self.token),
                )
        self.assertEqual(resp.status_code, 201)


class TestDocumentUploadForbiddenStages(ClientDocumentUploadSetup):
    """Etapas que NO permiten subida → 403."""

    def test_upload_in_lead_returns_403(self):
        process = self._make_process('lead')
        resp = self.client.post(
            _docs_url(process.pk),
            {'file': _fake_pdf(), 'name': 'Documento'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 403)

    def test_upload_in_visita_returns_403(self):
        process = self._make_process('visita')
        resp = self.client.post(
            _docs_url(process.pk),
            {'file': _fake_pdf(), 'name': 'Documento'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 403)

    def test_upload_in_interes_returns_403(self):
        process = self._make_process('interes')
        resp = self.client.post(
            _docs_url(process.pk),
            {'file': _fake_pdf(), 'name': 'Documento'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 403)

    def test_upload_in_cerrado_returns_403(self):
        process = self._make_process('cerrado')
        resp = self.client.post(
            _docs_url(process.pk),
            {'file': _fake_pdf(), 'name': 'Documento'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 403)


class TestDocumentUploadValidation(ClientDocumentUploadSetup):
    """Validaciones de archivo y nombre."""

    def test_upload_without_file_returns_400(self):
        process = self._make_process('pre_aprobacion')
        resp = self.client.post(
            _docs_url(process.pk),
            {'name': 'Sin archivo'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_without_name_returns_400(self):
        process = self._make_process('pre_aprobacion')
        resp = self.client.post(
            _docs_url(process.pk),
            {'file': _fake_pdf()},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_on_another_clients_process_returns_404(self):
        """Proceso de otro cliente → 404."""
        process = PurchaseProcess.objects.create(
            tenant=self.tenant,
            property=self.prop,
            client_membership=self.other_client_m,
            agent_membership=self.agent_m,
            status='pre_aprobacion',
        )
        resp = self.client.post(
            _docs_url(process.pk),
            {'file': _fake_pdf(), 'name': 'Intruso'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 404)
