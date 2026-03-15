"""
Tests de notificaciones (T-084).

Cubren los criterios:
- Usuario A no puede ver notificaciones de usuario B → 404
- read-all solo marca las notificaciones del usuario autenticado
- unread_count decrece al marcar como leídas
"""
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Tenant
from apps.users.models import User, TenantMembership
from apps.notifications.models import Notification


def _token(user):
    return str(RefreshToken.for_user(user).access_token)


def _auth(token):
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


class NotificationTestSetup(APITestCase):
    """
    Base: un tenant con dos clientes.
    Cada cliente tiene notificaciones propias.
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name='Notif Tenant', slug='notif-tenant',
            email='notif@test.com',
        )

        # Usuario A
        self.user_a = User.objects.create(email='notif_a@test.com')
        self.membership_a = TenantMembership.objects.create(
            user=self.user_a, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT,
        )
        self.token_a = _token(self.user_a)

        # Usuario B
        self.user_b = User.objects.create(email='notif_b@test.com')
        self.membership_b = TenantMembership.objects.create(
            user=self.user_b, tenant=self.tenant,
            role=TenantMembership.Role.CLIENT,
        )
        self.token_b = _token(self.user_b)

    def _notif(self, membership, title='Test', is_read=False):
        return Notification.objects.create(
            tenant=self.tenant,
            membership=membership,
            title=title,
            is_read=is_read,
        )


# ── Aislamiento: usuario A no puede ver notifs de B ───────────────────────────

class TestNotificationIsolation(NotificationTestSetup):
    """Usuario A no puede marcar como leída una notificación de B → 404."""

    def test_mark_other_users_notification_as_read_returns_404(self):
        notif_b = self._notif(self.membership_b, 'Notif de B')
        resp = self.client.patch(
            f'/api/v1/notifications/{notif_b.pk}/read',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 404)

    def test_user_a_list_does_not_contain_user_b_notifications(self):
        self._notif(self.membership_a, 'Notif A')
        notif_b = self._notif(self.membership_b, 'Notif B')

        resp = self.client.get('/api/v1/notifications/', **_auth(self.token_a))
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.data['results']]
        self.assertNotIn(notif_b.pk, ids)

    def test_user_a_only_sees_own_count(self):
        self._notif(self.membership_a, 'A1')
        self._notif(self.membership_a, 'A2')
        self._notif(self.membership_b, 'B1')  # no debe contar para A

        resp = self.client.get('/api/v1/notifications/', **_auth(self.token_a))
        self.assertEqual(resp.data['count'], 2)


# ── Marcar como leída ──────────────────────────────────────────────────────────

class TestMarkNotificationRead(NotificationTestSetup):
    """PATCH /notifications/{pk}/read marca la notificación como leída."""

    def test_mark_own_notification_as_read_returns_200(self):
        notif = self._notif(self.membership_a, 'Leer esto')
        resp = self.client.patch(
            f'/api/v1/notifications/{notif.pk}/read',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['is_read'])

    def test_mark_read_persists_in_db(self):
        notif = self._notif(self.membership_a)
        self.client.patch(
            f'/api/v1/notifications/{notif.pk}/read',
            **_auth(self.token_a),
        )
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_nonexistent_notification_returns_404(self):
        resp = self.client.patch(
            '/api/v1/notifications/99999/read',
            **_auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 404)


# ── read-all ──────────────────────────────────────────────────────────────────

class TestReadAll(NotificationTestSetup):
    """POST /notifications/read-all solo marca las del usuario autenticado."""

    def test_read_all_marks_only_own_notifications(self):
        self._notif(self.membership_a, 'A1', is_read=False)
        self._notif(self.membership_a, 'A2', is_read=False)
        notif_b = self._notif(self.membership_b, 'B1', is_read=False)

        resp = self.client.post('/api/v1/notifications/read-all', **_auth(self.token_a))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['marked_as_read'], 2)

        # Notificación de B sigue sin leer
        notif_b.refresh_from_db()
        self.assertFalse(notif_b.is_read)

    def test_read_all_returns_count_of_marked_notifications(self):
        self._notif(self.membership_a, 'N1', is_read=False)
        self._notif(self.membership_a, 'N2', is_read=False)
        self._notif(self.membership_a, 'N3', is_read=True)   # ya leída → no cuenta

        resp = self.client.post('/api/v1/notifications/read-all', **_auth(self.token_a))
        self.assertEqual(resp.data['marked_as_read'], 2)

    def test_read_all_on_empty_returns_zero(self):
        resp = self.client.post('/api/v1/notifications/read-all', **_auth(self.token_a))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['marked_as_read'], 0)

    def test_read_all_does_not_affect_already_read(self):
        self._notif(self.membership_a, 'Ya leída', is_read=True)
        resp = self.client.post('/api/v1/notifications/read-all', **_auth(self.token_a))
        self.assertEqual(resp.data['marked_as_read'], 0)


# ── unread_count ──────────────────────────────────────────────────────────────

class TestUnreadCount(NotificationTestSetup):
    """unread_count en la lista refleja las no leídas del usuario."""

    def test_unread_count_matches_unread_notifications(self):
        self._notif(self.membership_a, 'N1', is_read=False)
        self._notif(self.membership_a, 'N2', is_read=False)
        self._notif(self.membership_a, 'N3', is_read=True)

        resp = self.client.get('/api/v1/notifications/', **_auth(self.token_a))
        self.assertEqual(resp.data['unread_count'], 2)

    def test_unread_count_decreases_after_marking_read(self):
        n1 = self._notif(self.membership_a, 'N1', is_read=False)
        self._notif(self.membership_a, 'N2', is_read=False)

        # Antes: 2 no leídas
        resp = self.client.get('/api/v1/notifications/', **_auth(self.token_a))
        self.assertEqual(resp.data['unread_count'], 2)

        # Marcar una como leída
        self.client.patch(
            f'/api/v1/notifications/{n1.pk}/read',
            **_auth(self.token_a),
        )

        # Después: 1 no leída
        resp = self.client.get('/api/v1/notifications/', **_auth(self.token_a))
        self.assertEqual(resp.data['unread_count'], 1)

    def test_unread_count_zero_after_read_all(self):
        self._notif(self.membership_a, 'N1', is_read=False)
        self._notif(self.membership_a, 'N2', is_read=False)

        self.client.post('/api/v1/notifications/read-all', **_auth(self.token_a))

        resp = self.client.get('/api/v1/notifications/', **_auth(self.token_a))
        self.assertEqual(resp.data['unread_count'], 0)

    def test_unread_count_excludes_other_users_notifications(self):
        self._notif(self.membership_a, 'A', is_read=False)
        self._notif(self.membership_b, 'B', is_read=False)  # no cuenta para A

        resp = self.client.get('/api/v1/notifications/', **_auth(self.token_a))
        self.assertEqual(resp.data['unread_count'], 1)
