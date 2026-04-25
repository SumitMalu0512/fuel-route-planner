from django.test import TestCase, Client
from django.core.management import call_command
from api.models import FuelStation
from api.geocoder import geocode_location, geocode_city
from api.services import haversine_distance, plan_route
import json


class GeocoderTests(TestCase):
    """Tests for the geocoder module."""

    def test_geocode_known_city(self):
        lat, lng, city, state = geocode_location("New York, NY")
        self.assertAlmostEqual(lat, 40.7128, places=2)
        self.assertAlmostEqual(lng, -74.006, places=2)
        self.assertEqual(state, "NY")

    def test_geocode_full_state_name(self):
        lat, lng, city, state = geocode_location("Chicago, Illinois")
        self.assertIsNotNone(lat)
        self.assertEqual(state, "IL")

    def test_geocode_unknown_location(self):
        lat, lng, city, state = geocode_location("InvalidPlace")
        self.assertIsNone(lat)

    def test_geocode_city_fallback(self):
        """Unknown cities should still return coordinates within the state."""
        lat, lng = geocode_city("TinyVillage", "TX")
        self.assertIsNotNone(lat)
        self.assertTrue(25 < lat < 37)  # Within Texas latitude range


class HaversineTests(TestCase):
    """Tests for distance calculation."""

    def test_ny_to_la(self):
        dist = haversine_distance(40.7128, -74.0060, 34.0522, -118.2437)
        self.assertTrue(2400 < dist < 2500)  # ~2,450 miles straight line

    def test_same_point(self):
        dist = haversine_distance(40.0, -80.0, 40.0, -80.0)
        self.assertAlmostEqual(dist, 0.0, places=5)


class FuelStationImportTests(TestCase):
    """Tests for data import."""

    def test_import_command(self):
        call_command('import_fuel_stations')
        count = FuelStation.objects.count()
        self.assertGreater(count, 5000)

    def test_stations_have_coordinates(self):
        call_command('import_fuel_stations')
        stations_without_coords = FuelStation.objects.filter(
            latitude__isnull=True
        ).count()
        self.assertEqual(stations_without_coords, 0)

    def test_no_canadian_stations(self):
        call_command('import_fuel_stations')
        canadian = FuelStation.objects.filter(
            state__in=['AB', 'BC', 'MB', 'NB', 'NS', 'ON', 'QC', 'SK', 'YT']
        ).count()
        self.assertEqual(canadian, 0)


class RouteAPITests(TestCase):
    """Integration tests for the route planning API."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command('import_fuel_stations')

    def setUp(self):
        self.client = Client()

    def test_post_route_success(self):
        response = self.client.post(
            '/api/route/',
            data=json.dumps({'start': 'New York, NY', 'end': 'Chicago, IL'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('total_distance_miles', data)
        self.assertIn('fuel_stops', data)
        self.assertIn('total_fuel_cost', data)
        self.assertIn('route_geometry', data)
        self.assertGreater(data['total_distance_miles'], 0)
        self.assertGreater(data['total_fuel_cost'], 0)

    def test_post_short_route_no_stops(self):
        response = self.client.post(
            '/api/route/',
            data=json.dumps({'start': 'New York, NY', 'end': 'Philadelphia, PA'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Short route should have 0 fuel stops
        self.assertEqual(len(data['fuel_stops']), 0)

    def test_post_cross_country_multiple_stops(self):
        response = self.client.post(
            '/api/route/',
            data=json.dumps({'start': 'New York, NY', 'end': 'Los Angeles, CA'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(len(data['fuel_stops']), 3)

    def test_post_missing_fields(self):
        response = self.client.post(
            '/api/route/',
            data=json.dumps({'start': 'New York, NY'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_post_invalid_location(self):
        response = self.client.post(
            '/api/route/',
            data=json.dumps({'start': 'InvalidPlace', 'end': 'Chicago, IL'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_get_api_info(self):
        response = self.client.get('/api/route/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('usage', data)

    def test_map_endpoint(self):
        response = self.client.get(
            '/api/route/map/',
            {'start': 'Dallas, TX', 'end': 'Houston, TX'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/html')
        self.assertIn(b'leaflet', response.content)

    def test_fuel_cost_calculation(self):
        response = self.client.post(
            '/api/route/',
            data=json.dumps({'start': 'Dallas, TX', 'end': 'Houston, TX'}),
            content_type='application/json',
        )
        data = response.json()
        # Total gallons should be distance / MPG
        expected_gallons = data['total_distance_miles'] / 10
        self.assertAlmostEqual(data['total_gallons'], expected_gallons, delta=1.0)
