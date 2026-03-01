from rest_framework import serializers


class AgentDashboardSerializer(serializers.Serializer):
    agent = serializers.DictField()
    stats = serializers.DictField()
