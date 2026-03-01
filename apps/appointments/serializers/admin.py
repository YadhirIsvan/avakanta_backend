from rest_framework import serializers

from ..models import AgentSchedule, AgentUnavailability, ScheduleBreak


class AdminScheduleBreakInputSerializer(serializers.Serializer):
    break_type = serializers.ChoiceField(choices=ScheduleBreak.BreakType.choices)
    name = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()


class AdminAgentScheduleSerializer(serializers.ModelSerializer):
    start_time = serializers.TimeField(format='%H:%M')
    end_time = serializers.TimeField(format='%H:%M')
    lunch_start = serializers.TimeField(format='%H:%M', allow_null=True)
    lunch_end = serializers.TimeField(format='%H:%M', allow_null=True)
    breaks = serializers.SerializerMethodField()

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

    def get_breaks(self, obj):
        return [
            {
                'id': b.pk,
                'break_type': b.break_type,
                'name': b.name,
                'start_time': b.start_time.strftime('%H:%M'),
                'end_time': b.end_time.strftime('%H:%M'),
            }
            for b in obj.breaks.all()
        ]


class AdminAgentScheduleInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    monday = serializers.BooleanField(default=False)
    tuesday = serializers.BooleanField(default=False)
    wednesday = serializers.BooleanField(default=False)
    thursday = serializers.BooleanField(default=False)
    friday = serializers.BooleanField(default=False)
    saturday = serializers.BooleanField(default=False)
    sunday = serializers.BooleanField(default=False)
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    has_lunch_break = serializers.BooleanField(default=False)
    lunch_start = serializers.TimeField(required=False, allow_null=True, default=None)
    lunch_end = serializers.TimeField(required=False, allow_null=True, default=None)
    valid_from = serializers.DateField(required=False, allow_null=True, default=None)
    valid_until = serializers.DateField(required=False, allow_null=True, default=None)
    is_active = serializers.BooleanField(default=True)
    priority = serializers.IntegerField(default=0)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    breaks = AdminScheduleBreakInputSerializer(many=True, required=False, default=list)


class AdminAgentUnavailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentUnavailability
        fields = ['id', 'start_date', 'end_date', 'reason', 'notes']


class AdminAgentUnavailabilityInputSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.ChoiceField(choices=AgentUnavailability.Reason.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError('start_date debe ser menor o igual a end_date.')
        return data
