from rest_framework import serializers
from ..models import TenantMembership


class OTPRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField(min_length=6, max_length=6)


class MembershipSerializer(serializers.ModelSerializer):
    tenant_id = serializers.IntegerField(source='tenant.id')
    tenant_name = serializers.CharField(source='tenant.name')
    tenant_slug = serializers.CharField(source='tenant.slug')

    class Meta:
        model = TenantMembership
        fields = ['id', 'tenant_id', 'tenant_name', 'tenant_slug', 'role']
