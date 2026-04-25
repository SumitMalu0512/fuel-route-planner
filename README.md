# Fuel Route Planner API

A Django REST API that plans fuel-optimized road trips across the USA. Given start and end locations, it returns the driving route with optimal (cheapest) fuel stops, factoring in vehicle range constraints and real fuel station pricing data.

## Features

- **Route planning** between any two US cities
- **Optimal fuel stop selection** based on real retail fuel prices from 6,600+ truck stops
- **Cost calculation** assuming 500-mile vehicle range and 10 MPG efficiency
- **Interactive map** view with route polyline and fuel stop markers (Leaflet/OpenStreetMap)
- **Single external API call** to OSRM for routing (with straight-line fallback)

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd fuel-route-planner

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Import fuel station data
python manage.py import_fuel_stations

# Start the server
python manage.py runserver
```

### API Usage

#### Plan a Route

**POST** `/api/route/`

```json
{
    "start": "New York, NY",
    "end": "Los Angeles, CA"
}
```

**Response:**

```json
{
    "start_location": "New York, NY",
    "end_location": "Los Angeles, CA",
    "start_coords": [40.7128, -74.006],
    "end_coords": [34.0522, -118.2437],
    "total_distance_miles": 3179.4,
    "fuel_stops": [
        {
            "station_name": "GO MART FOOD STORE #44",
            "address": "I-79, EXIT 62",
            "city": "Sutton",
            "state": "WV",
            "latitude": 38.66,
            "longitude": -80.71,
            "fuel_price": 3.559,
            "miles_from_start": 407.0,
            "gallons_needed": 40.39,
            "cost": 144.70
        }
        // ... more stops
    ],
    "total_fuel_cost": 1001.99,
    "total_gallons": 318.0,
    "summary": "Route from New York, NY to Los Angeles, CA: 3179 miles, 7 fuel stop(s)...",
    "map_url": "http://localhost:8000/api/route/map/?start=New+York,+NY&end=Los+Angeles,+CA",
    "route_geometry": [[-74.006, 40.7128], ...]
}
```

#### View Interactive Map

**GET** `/api/route/map/?start=New+York,+NY&end=Los+Angeles,+CA`

Returns an HTML page with a Leaflet map showing the route, start/end markers, and fuel stop pins with price/cost popups.

#### API Info

**GET** `/api/route/`

Returns API usage information and parameter descriptions.

## Architecture

```
fuel_route_planner/
├── manage.py
├── requirements.txt
├── data/
│   └── fuel-prices-for-be-assessment.csv   # Fuel pricing data (8,151 rows)
├── fuel_route_planner/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── api/
    ├── models.py          # FuelStation model
    ├── geocoder.py        # US city geocoding (300+ cities + fallback)
    ├── services.py        # Route planning & fuel stop optimization
    ├── serializers.py     # DRF serializers
    ├── views.py           # API views + map HTML generation
    ├── urls.py            # URL routing
    ├── tests.py           # 17 unit/integration tests
    └── management/
        └── commands/
            └── import_fuel_stations.py  # CSV data import command
```

### How It Works

1. **Geocoding**: Start/end locations are geocoded using a built-in database of 300+ major US cities. Unknown cities fall back to a deterministic state-centroid offset.

2. **Routing**: The route is fetched from [OSRM](http://project-osrm.org/) (Open Source Routing Machine) — a free, no-API-key-required routing engine. A single API call returns the full driving route geometry and distance. If OSRM is unavailable, a straight-line fallback with a 1.3x road-distance multiplier is used.

3. **Fuel Stop Selection**: The algorithm walks along the route and triggers a fuel search when the vehicle has ~400 miles of range used (leaving a 100-mile safety buffer). At each refuel point, it queries the database for the cheapest station within a 25–100 mile radius of the route.

4. **Cost Calculation**: Each stop's cost = (miles since last stop ÷ 10 MPG) × station price per gallon. The total includes all stops plus the final leg to the destination.

### External API Usage

| API | Calls per Request | Purpose |
|-----|-------------------|---------|
| OSRM | 1 | Route geometry + distance |

OSRM is free, requires no API key, and has no strict rate limits for reasonable use.

## Running Tests

```bash
python manage.py test api -v 2
```

Runs 17 tests covering geocoding, distance calculations, data import, API endpoints, and cost calculations.

## Assumptions

- Vehicle maximum range: **500 miles**
- Fuel efficiency: **10 miles per gallon**
- Fuel stations are sourced from the provided CSV (OPIS truckstop data)
- For stations with duplicate entries, the **cheapest price** is used
- Canadian stations are filtered out (US-only routes)
- The vehicle starts with a full tank
