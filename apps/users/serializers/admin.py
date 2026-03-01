from rest_framework import serializers

from apps.appointments.models import AgentSchedule, ScheduleBreak
from ..models import AgentProfile


class AdminScheduleBreakSerializer(serializers.ModelSerializer):
    start_time = serializers.TimeField(format='%H:%M')
    end_time = serializers.TimeField(format='%H:%M')

    class Meta:
        model = ScheduleBreak
        fields = ['id', 'break_type', 'name', 'start_time', 'end_time']


class AdminAgentScheduleSerializer(serializers.ModelSerializer):
    start_time = serializers.TimeField(format='%H:%M')
    end_time = serializers.TimeField(format='%H:%M')
    lunch_start = serializers.TimeField(format='%H:%M', allow_null=True)
    lunch_end = serializers.TimeField(format='%H:%M', allow_null=True)
    breaks = AdminScheduleBreakSerializer(many=True, read_only=True)

    class Meta:
        model = AgentSchedule
        fields = [
            'id', 'name',
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
            'start_time', 'end_time',
            'has_lunch_break', 'lunch_start', 'lunch_end',
            'valid_from', 'valid_until',
            'is_active', 'priority',
            'breaks',
        ]


class AdminAgentListSerializer(serializers.ModelSerializer):
    membership_id = serializers.IntegerField(source='membership.pk', read_only=True)
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='membership.user.email', read_only=True)
    phone = serializers.CharField(source='membership.user.phone', read_only=True)
    avatar = serializers.CharField(source='membership.user.avatar', read_only=True)
    # Stats — populated via annotate() in the view queryset
    properties_count = serializers.IntegerField(read_only=True)
    sales_count = serializers.IntegerField(read_only=True)
    leads_count = serializers.IntegerField(read_only=True)
    active_leads = serializers.IntegerField(read_only=True)

    class Meta:
        model = AgentProfile
        fields = [
            'id', 'membership_id', 'name', 'email', 'phone', 'avatar',
            'zone', 'bio', 'score',
            'properties_count', 'sales_count', 'leads_count', 'active_leads',
        ]

    def get_name(self, obj):
        full_name = obj.membership.user.get_full_name()
        return full_name or obj.membership.user.email


class AdminAgentDetailSerializer(AdminAgentListSerializer):
    schedules = serializers.SerializerMethodField()

    class Meta(AdminAgentListSerializer.Meta):
        fields = AdminAgentListSerializer.Meta.fields + ['schedules']

    def get_schedules(self, obj):
        schedules = obj.membership.schedules.prefetch_related('breaks').order_by('-priority', 'id')
        return AdminAgentScheduleSerializer(schedules, many=True).data


class AdminAgentCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150, default='')
    last_name = serializers.CharField(max_length=150, default='')
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    zone = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    bio = serializers.CharField(required=False, allow_blank=True, default='')
