"""
Tests for UserManager and serializers with 0% coverage.
"""
from django.test import TestCase
from rest_framework import serializers as drf_serializers

from apps.users.models import User
from apps.users.serializers.agent import AgentDashboardSerializer


class TestUserManager(TestCase):
    """Test UserManager.create_user and create_superuser."""

    def test_create_user_with_email_and_password(self):
        """create_user stores email and hashed password."""
        user = User.objects.create_user(email='test@example.com', password='testpass123')
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('testpass123'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_without_password(self):
        """create_user without password sets unusable_password."""
        user = User.objects.create_user(email='nopass@example.com')
        self.assertEqual(user.email, 'nopass@example.com')
        self.assertFalse(user.has_usable_password())

    def test_create_user_with_extra_fields(self):
        """create_user accepts and stores extra fields."""
        user = User.objects.create_user(
            email='extra@example.com',
            password='pass123',
            first_name='John',
            last_name='Doe',
        )
        self.assertEqual(user.first_name, 'John')
        self.assertEqual(user.last_name, 'Doe')

    def test_create_user_stores_email_as_provided(self):
        """create_user stores email as provided (normalized in DB)."""
        user = User.objects.create_user(email='test.user@example.com', password='pass123')
        self.assertEqual(user.email, 'test.user@example.com')

    def test_create_user_without_email_raises_value_error(self):
        """create_user requires email."""
        with self.assertRaises(ValueError) as ctx:
            User.objects.create_user(email=None, password='pass123')
        self.assertIn('email', str(ctx.exception).lower())

    def test_create_user_with_empty_email_raises_value_error(self):
        """create_user with empty email raises ValueError."""
        with self.assertRaises(ValueError):
            User.objects.create_user(email='', password='pass123')

    def test_create_superuser(self):
        """create_superuser sets is_staff and is_superuser."""
        superuser = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123',
        )
        self.assertEqual(superuser.email, 'admin@example.com')
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.check_password('adminpass123'))

    def test_create_superuser_with_extra_fields(self):
        """create_superuser preserves extra fields."""
        superuser = User.objects.create_superuser(
            email='admin2@example.com',
            password='pass123',
            first_name='Admin',
        )
        self.assertEqual(superuser.first_name, 'Admin')
        self.assertTrue(superuser.is_staff)

    def test_create_superuser_without_email(self):
        """create_superuser also validates email."""
        with self.assertRaises(ValueError):
            User.objects.create_superuser(email=None, password='pass123')


class TestAgentDashboardSerializer(TestCase):
    """Test AgentDashboardSerializer."""

    def test_serialize_valid_data(self):
        """Serializer accepts agent and stats dicts."""
        data = {
            'agent': {'id': 1, 'name': 'Agent 1'},
            'stats': {'appointments': 5, 'conversions': 2},
        }
        serializer = AgentDashboardSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['agent']['id'], 1)
        self.assertEqual(serializer.validated_data['stats']['appointments'], 5)

    def test_serialize_empty_dicts(self):
        """Serializer accepts empty dicts."""
        data = {'agent': {}, 'stats': {}}
        serializer = AgentDashboardSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['agent'], {})
        self.assertEqual(serializer.validated_data['stats'], {})

    def test_serialize_nested_dicts(self):
        """Serializer accepts nested dict structures."""
        data = {
            'agent': {
                'id': 1,
                'profile': {'email': 'test@example.com'},
            },
            'stats': {
                'monthly': {'jan': 5, 'feb': 10},
            },
        }
        serializer = AgentDashboardSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(
            serializer.validated_data['agent']['profile']['email'],
            'test@example.com',
        )

    def test_serialize_missing_agent_field(self):
        """Serializer requires agent field."""
        data = {'stats': {'appointments': 5}}
        serializer = AgentDashboardSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('agent', serializer.errors)

    def test_serialize_missing_stats_field(self):
        """Serializer requires stats field."""
        data = {'agent': {'id': 1}}
        serializer = AgentDashboardSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('stats', serializer.errors)

    def test_serialize_invalid_agent_type(self):
        """Serializer requires agent to be a dict."""
        data = {'agent': 'not a dict', 'stats': {}}
        serializer = AgentDashboardSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('agent', serializer.errors)

    def test_serialize_invalid_stats_type(self):
        """Serializer requires stats to be a dict."""
        data = {'agent': {}, 'stats': 'not a dict'}
        serializer = AgentDashboardSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('stats', serializer.errors)
