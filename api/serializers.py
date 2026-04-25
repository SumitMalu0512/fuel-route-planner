from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(
        help_text="Start location (e.g., 'New York, NY')",
        max_length=200,
    )
    end = serializers.CharField(
        help_text="End location (e.g., 'Los Angeles, CA')",
        max_length=200,
    )


class FuelStopSerializer(serializers.Serializer):
    station_name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    fuel_price = serializers.FloatField()
    miles_from_start = serializers.FloatField()
    gallons_needed = serializers.FloatField()
    cost = serializers.FloatField()


class RouteResponseSerializer(serializers.Serializer):
    start_location = serializers.CharField()
    end_location = serializers.CharField()
    start_coords = serializers.ListField(child=serializers.FloatField())
    end_coords = serializers.ListField(child=serializers.FloatField())
    total_distance_miles = serializers.FloatField()
    fuel_stops = FuelStopSerializer(many=True)
    total_fuel_cost = serializers.FloatField()
    total_gallons = serializers.FloatField()
    summary = serializers.CharField()
    map_url = serializers.CharField()
    route_geometry = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField()),
        help_text="Route polyline as list of [longitude, latitude] pairs",
    )
