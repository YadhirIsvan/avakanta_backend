from rest_framework import serializers
from ..models import TenantMembership


class OTPRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField(min_length=6, max_length=6)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)


class MembershipSerializer(serializers.ModelSerializer):
    tenant_id = serializers.IntegerField(source='tenant.id')
    tenant_name = serializers.CharField(source='tenant.name')
    tenant_slug = serializers.CharField(source='tenant.slug')

    class Meta:
        model = TenantMembership
        fields = ['id', 'tenant_id', 'tenant_name', 'tenant_slug', 'role']
