from rest_framework import serializers

from apps.users.models import User


class ClientDashboardSerializer(serializers.Serializer):
    client = serializers.DictField()
    credit_score = serializers.IntegerField(allow_null=True)
    recent_activity = serializers.ListField()
    sale_processes_preview = serializers.ListField()
    purchase_processes_preview = serializers.ListField()


class ClientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone', 'avatar', 'city']
        read_only_fields = ['id', 'email', 'avatar']


class ClientProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    city = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)


class ClientNotificationPreferencesSerializer(serializers.Serializer):
    new_properties = serializers.BooleanField()
    price_updates = serializers.BooleanField()
    appointment_reminders = serializers.BooleanField()
    offers = serializers.BooleanField()
