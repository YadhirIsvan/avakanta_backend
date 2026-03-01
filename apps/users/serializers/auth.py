from rest_framework import serializers


class OTPRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
