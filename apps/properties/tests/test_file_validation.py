"""
Tests de validación de archivos (T-087).

Cubren los criterios:
- Subir un .exe retorna 400 con mensaje de error claro
- Subir un archivo mayor al límite retorna 400

Incluye:
- Tests unitarios de validate_file_type y validate_file_size
- Tests de integración para los tres endpoints que aceptan archivos:
    1. POST /admin/properties/{pk}/images
    2. POST /admin/properties/{pk}/documents
    3. POST /client/purchases/{pk}/documents
"""
import tempfile
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.validators import (
    validate_file_type,
    validate_file_size,
    ALLOWED_IMAGE_TYPES,
    ALLOWED_DOCUMENT_TYPES,
    MAX_IMAGE_SIZE_MB,
    MAX_DOCUMENT_SIZE_MB,
)
from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership, AgentProfile
from apps.properties.models import Property
from apps.transactions.models import PurchaseProcess


def _token(user):
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


def _exe_file(name='malware.exe'):
    return SimpleUploadedFile(name, b'MZ\x90\x00bad', content_type='application/x-msdownload')


def _fake_image(name='photo.jpg'):
    return SimpleUploadedFile(name, b'\xff\xd8\xff\xe0', content_type='image/jpeg')


def _fake_pdf(name='doc.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 fake', content_type='application/pdf')


# ── Validators unitarios ───────────────────────────────────────────────────────

class TestValidateFileType(TestCase):
    """validate_file_type: tipos permitidos pasan, el resto lanza ValidationError."""

    def test_valid_jpeg_image_passes(self):
        f = SimpleUploadedFile('img.jpg', b'data', content_type='image/jpeg')
        validate_file_type(f, ALLOWED_IMAGE_TYPES)  # no debe lanzar

    def test_valid_png_image_passes(self):
        f = SimpleUploadedFile('img.png', b'data', content_type='image/png')
        validate_file_type(f, ALLOWED_IMAGE_TYPES)

    def test_valid_webp_image_passes(self):
        f = SimpleUploadedFile('img.webp', b'data', content_type='image/webp')
        validate_file_type(f, ALLOWED_IMAGE_TYPES)

    def test_exe_image_raises_validation_error(self):
        f = _exe_file()
        with self.assertRaises(ValidationError):
            validate_file_type(f, ALLOWED_IMAGE_TYPES)

    def test_error_message_contains_content_type(self):
        f = _exe_file()
        with self.assertRaises(ValidationError) as ctx:
            validate_file_type(f, ALLOWED_IMAGE_TYPES)
        self.assertIn('application/x-msdownload', str(ctx.exception))

    def test_valid_pdf_document_passes(self):
        f = _fake_pdf()
        validate_file_type(f, ALLOWED_DOCUMENT_TYPES)

    def test_exe_document_raises_validation_error(self):
        f = _exe_file()
        with self.assertRaises(ValidationError):
            validate_file_type(f, ALLOWED_DOCUMENT_TYPES)


class TestValidateFileSize(TestCase):
    """validate_file_size: dentro del límite pasa, excedido lanza ValidationError."""

    def test_small_file_passes(self):
        f = SimpleUploadedFile('tiny.pdf', b'small', content_type='application/pdf')
        validate_file_size(f, MAX_DOCUMENT_SIZE_MB)  # no debe lanzar

    def test_file_exactly_at_limit_passes(self):
        f = SimpleUploadedFile('exact.pdf', b'data', content_type='application/pdf')
        f.size = MAX_DOCUMENT_SIZE_MB * 1024 * 1024  # exactamente el límite
        validate_file_size(f, MAX_DOCUMENT_SIZE_MB)  # no debe lanzar

    def test_file_over_image_limit_raises(self):
        f = _fake_image()
        f.size = (MAX_IMAGE_SIZE_MB + 1) * 1024 * 1024  # 11 MB
        with self.assertRaises(ValidationError):
            validate_file_size(f, MAX_IMAGE_SIZE_MB)

    def test_file_over_document_limit_raises(self):
        f = _fake_pdf()
        f.size = (MAX_DOCUMENT_SIZE_MB + 1) * 1024 * 1024  # 21 MB
        with self.assertRaises(ValidationError):
            validate_file_size(f, MAX_DOCUMENT_SIZE_MB)

    def test_error_message_mentions_max_size(self):
        f = _fake_pdf()
        f.size = 999 * 1024 * 1024
        with self.assertRaises(ValidationError) as ctx:
            validate_file_size(f, MAX_DOCUMENT_SIZE_MB)
        self.assertIn(str(MAX_DOCUMENT_SIZE_MB), str(ctx.exception))


# ── Helpers de setup ───────────────────────────────────────────────────────────

class AdminFileUploadSetup(APITestCase):
    """Base: tenant, admin y propiedad activa."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='FileVal Tenant', slug='fileval-tenant',
            email='fileval@test.com', is_active=True,
        )
        admin_user = User.objects.create(email='admin_fv@test.com', is_active=True)
        TenantMembership.objects.create(
            user=admin_user, tenant=self.tenant,
            role=TenantMembership.Role.ADMIN, is_active=True,
        )
        self.token = _token(admin_user)
        self.prop = Property.objects.create(
            tenant=self.tenant, title='Casa FileVal',
            listing_type='sale', status='disponible',
            property_type='house', price=500_000, is_active=True,
        )


# ── Endpoint: POST /admin/properties/{pk}/images ───────────────────────────────

class TestPropertyImageUploadValidation(AdminFileUploadSetup):
    """Endpoint de imágenes rechaza tipos inválidos y archivos demasiado grandes."""

    def _url(self):
        return f'/api/v1/admin/properties/{self.prop.pk}/images'

    def test_exe_upload_returns_400(self):
        resp = self.client.post(
            self._url(),
            {'images': _exe_file()},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)

    def test_exe_error_message_is_clear(self):
        resp = self.client.post(
            self._url(),
            {'images': _exe_file()},
            format='multipart',
            **_auth(self.token),
        )
        self.assertIn('application/x-msdownload', resp.data['error'])

    def test_oversized_image_returns_400(self):
        """Simula archivo sobre el límite mockeando validate_file_size."""
        with patch(
            'apps.properties.views.admin.validate_file_size',
            side_effect=ValidationError('El archivo excede el tamaño máximo permitido de 10 MB.'),
        ):
            resp = self.client.post(
                self._url(),
                {'images': _fake_image()},
                format='multipart',
                **_auth(self.token),
            )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)

    def test_valid_jpeg_upload_returns_201(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                resp = self.client.post(
                    self._url(),
                    {'images': _fake_image()},
                    format='multipart',
                    **_auth(self.token),
                )
        self.assertEqual(resp.status_code, 201)


# ── Endpoint: POST /admin/properties/{pk}/documents ───────────────────────────

class TestPropertyDocumentUploadValidation(AdminFileUploadSetup):
    """Endpoint de documentos de propiedad rechaza tipos inválidos y archivos grandes."""

    def _url(self):
        return f'/api/v1/admin/properties/{self.prop.pk}/documents'

    def test_exe_upload_returns_400(self):
        resp = self.client.post(
            self._url(),
            {'file': _exe_file(), 'name': 'Virus'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)

    def test_exe_error_message_is_clear(self):
        resp = self.client.post(
            self._url(),
            {'file': _exe_file(), 'name': 'Virus'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertIn('application/x-msdownload', resp.data['error'])

    def test_oversized_document_returns_400(self):
        with patch(
            'apps.properties.views.admin.validate_file_size',
            side_effect=ValidationError('El archivo excede el tamaño máximo permitido de 20 MB.'),
        ):
            resp = self.client.post(
                self._url(),
                {'file': _fake_pdf(), 'name': 'Grande'},
                format='multipart',
                **_auth(self.token),
            )
        self.assertEqual(resp.status_code, 400)

    def test_valid_pdf_upload_returns_201(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                resp = self.client.post(
                    self._url(),
                    {'file': _fake_pdf(), 'name': 'Contrato'},
                    format='multipart',
                    **_auth(self.token),
                )
        self.assertEqual(resp.status_code, 201)


# ── Endpoint: POST /client/purchases/{pk}/documents ───────────────────────────

class ClientPurchaseDocumentValidationSetup(APITestCase):
    """Base: tenant, cliente, agente, propiedad y proceso en pre_aprobacion."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='ClientFV Tenant', slug='clientfv-tenant',
            email='clientfv@test.com', is_active=True,
        )
        client_user = User.objects.create(email='client_fv@test.com', is_active=True)
        self.client_m = TenantMembership.objects.create(
            user=client_user, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT, is_active=True,
        )
        self.token = _token(client_user)

        agent_user = User.objects.create(email='agent_fv@test.com', is_active=True)
        agent_m = TenantMembership.objects.create(
            user=agent_user, tenant=self.tenant,
            role=TenantMembership.Role.AGENT, is_active=True,
        )
        AgentProfile.objects.create(membership=agent_m)

        prop = Property.objects.create(
            tenant=self.tenant, title='Casa FV',
            listing_type='sale', status='disponible',
            property_type='house', price=1_000_000, is_active=True,
        )
        self.process = PurchaseProcess.objects.create(
            tenant=self.tenant, property=prop,
            client_membership=self.client_m,
            agent_membership=agent_m,
            status='pre_aprobacion',
        )

    def _url(self):
        return f'/api/v1/client/purchases/{self.process.pk}/documents'


class TestClientPurchaseDocumentValidation(ClientPurchaseDocumentValidationSetup):
    """Endpoint de documentos del cliente rechaza tipos inválidos y archivos grandes."""

    def test_exe_upload_returns_400(self):
        resp = self.client.post(
            self._url(),
            {'file': _exe_file(), 'name': 'Virus'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.data)

    def test_exe_error_message_is_clear(self):
        resp = self.client.post(
            self._url(),
            {'file': _exe_file(), 'name': 'Virus'},
            format='multipart',
            **_auth(self.token),
        )
        self.assertIn('application/x-msdownload', resp.data['error'])

    def test_oversized_document_returns_400(self):
        with patch(
            'apps.transactions.views.client.validate_file_size',
            side_effect=ValidationError('El archivo excede el tamaño máximo permitido de 20 MB.'),
        ):
            resp = self.client.post(
                self._url(),
                {'file': _fake_pdf(), 'name': 'Grande'},
                format='multipart',
                **_auth(self.token),
            )
        self.assertEqual(resp.status_code, 400)

    def test_valid_pdf_returns_201(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                resp = self.client.post(
                    self._url(),
                    {'file': _fake_pdf(), 'name': 'Identificación'},
                    format='multipart',
                    **_auth(self.token),
                )
        self.assertEqual(resp.status_code, 201)
