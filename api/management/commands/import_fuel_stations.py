"""Management command to import fuel station data from CSV."""
import csv
from django.core.management.base import BaseCommand
from django.conf import settings
from api.models import FuelStation
from api.geocoder import geocode_city, US_STATES


class Command(BaseCommand):
    help = 'Import fuel stations from CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-path',
            type=str,
            default=settings.FUEL_PRICES_CSV,
            help='Path to the fuel prices CSV file',
        )

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        self.stdout.write(f"Importing fuel stations from {csv_path}...")

        # Clear existing data
        FuelStation.objects.all().delete()

        stations = []
        seen = {}  # Track (opis_id, rack_id) to handle duplicates - keep cheapest
        skipped = 0
        
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                state = row['State'].strip()
                if state not in US_STATES:
                    skipped += 1
                    continue

                city = row['City'].strip()
                opis_id = int(row['OPIS Truckstop ID'])
                price = float(row['Retail Price'])
                rack_id = int(row['Rack ID'])

                # For duplicate station entries, keep the cheapest price
                key = opis_id
                if key in seen:
                    if price < seen[key]['retail_price']:
                        seen[key]['retail_price'] = price
                    continue

                lat, lng = geocode_city(city, state)
                if lat is None:
                    skipped += 1
                    continue

                seen[key] = {
                    'opis_id': opis_id,
                    'name': row['Truckstop Name'].strip(),
                    'address': row['Address'].strip(),
                    'city': city,
                    'state': state,
                    'rack_id': rack_id,
                    'retail_price': price,
                    'latitude': lat,
                    'longitude': lng,
                }

        # Bulk create
        for data in seen.values():
            stations.append(FuelStation(**data))

        FuelStation.objects.bulk_create(stations, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(
            f"Imported {len(stations)} stations. Skipped {skipped} (non-US or no coords)."
        ))
