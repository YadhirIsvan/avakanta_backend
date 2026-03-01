from rest_framework import serializers


class SellerLeadSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=50)
    property_type = serializers.CharField(max_length=20)
    location = serializers.CharField(max_length=255, required=False, allow_blank=True)
    square_meters = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )
    bedrooms = serializers.IntegerField(required=False, allow_null=True)
    bathrooms = serializers.IntegerField(required=False, allow_null=True)
    expected_price = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
