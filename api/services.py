"""
Route planning service with optimal fuel stop selection.

Architecture:
1. Geocode start/end locations
2. Get driving route from OSRM (1 API call)
3. Walk the route, finding cheapest fuel stops within range
4. Return route + stops + total cost
"""
import math
import requests
from typing import List, Tuple, Optional
from dataclasses import dataclass, asdict
from api.models import FuelStation
from api.geocoder import geocode_location


# Constants
VEHICLE_RANGE_MILES = 500
MPG = 10
OSRM_BASE_URL = "https://router.project-osrm.org"
SEARCH_RADIUS_MILES = 50  # How far from route to search for stations
REFUEL_BUFFER_MILES = 100  # Refuel before tank is completely empty


@dataclass
class FuelStop:
    station_name: str
    address: str
    city: str
    state: str
    latitude: float
    longitude: float
    fuel_price: float
    miles_from_start: float
    gallons_needed: float
    cost: float


@dataclass
class RouteResult:
    start_location: str
    end_location: str
    start_coords: Tuple[float, float]
    end_coords: Tuple[float, float]
    total_distance_miles: float
    route_geometry: list  # List of [lng, lat] pairs for the route polyline
    fuel_stops: List[FuelStop]
    total_fuel_cost: float
    total_gallons: float
    summary: str


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in miles between two coordinates."""
    R = 3959  # Earth's radius in miles
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def decode_polyline(encoded: str) -> List[Tuple[float, float]]:
    """Decode a Google-style encoded polyline into a list of (lat, lng) tuples."""
    points = []
    index = 0
    lat = 0
    lng = 0
    while index < len(encoded):
        # Decode latitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        # Decode longitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        points.append((lat / 1e5, lng / 1e5))
    return points


def get_osrm_route(start_lat: float, start_lng: float,
                   end_lat: float, end_lng: float) -> Optional[dict]:
    """
    Get driving route from OSRM.
    Returns route geometry and distance. Single API call.
    """
    url = (
        f"{OSRM_BASE_URL}/route/v1/driving/"
        f"{start_lng},{start_lat};{end_lng},{end_lat}"
        f"?overview=full&geometries=polyline&steps=false"
    )
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get('code') == 'Ok' and data.get('routes'):
            route = data['routes'][0]
            return {
                'distance_meters': route['distance'],
                'duration_seconds': route['duration'],
                'geometry': route['geometry'],  # Encoded polyline
            }
    except requests.RequestException:
        pass
    return None


def get_straight_line_route(start_lat: float, start_lng: float,
                            end_lat: float, end_lng: float) -> dict:
    """
    Fallback: create a straight-line route with intermediate points.
    Applies a 1.3x multiplier to approximate road distance.
    """
    straight_distance = haversine_distance(start_lat, start_lng, end_lat, end_lng)
    road_distance = straight_distance * 1.3  # Road distance approximation

    # Create intermediate waypoints
    num_points = max(int(road_distance / 20), 10)  # Point every ~20 miles
    points = []
    for i in range(num_points + 1):
        frac = i / num_points
        lat = start_lat + frac * (end_lat - start_lat)
        lng = start_lng + frac * (end_lng - start_lng)
        points.append((lat, lng))

    return {
        'distance_meters': road_distance * 1609.34,
        'duration_seconds': road_distance / 60 * 3600,  # ~60 mph avg
        'points': points,
    }


def find_nearby_stations(lat: float, lng: float, radius_miles: float = SEARCH_RADIUS_MILES) -> list:
    """
    Find fuel stations near a given coordinate.
    Uses bounding box query then Haversine filter.
    """
    # Approximate degree offset for bounding box
    lat_offset = radius_miles / 69.0
    lng_offset = radius_miles / (69.0 * math.cos(math.radians(lat)))

    stations = FuelStation.objects.filter(
        latitude__gte=lat - lat_offset,
        latitude__lte=lat + lat_offset,
        longitude__gte=lng - lng_offset,
        longitude__lte=lng + lng_offset,
    ).order_by('retail_price')

    # Filter by actual Haversine distance and return with distance info
    result = []
    for station in stations:
        dist = haversine_distance(lat, lng, station.latitude, station.longitude)
        if dist <= radius_miles:
            result.append({
                'station': station,
                'distance_from_point': dist,
            })

    return sorted(result, key=lambda x: x['station'].retail_price)


def plan_fuel_stops(route_points: List[Tuple[float, float]],
                    total_distance_miles: float) -> List[FuelStop]:
    """
    Walk along the route and find optimal (cheapest) fuel stops.

    Strategy:
    - Start with a full tank (500 miles range)
    - When remaining range drops below REFUEL_BUFFER_MILES, look for
      the cheapest station within the current drivable range
    - If route is shorter than vehicle range, no stops needed
    """
    if total_distance_miles <= VEHICLE_RANGE_MILES:
        return []  # Can make the trip on one tank

    fuel_stops = []
    remaining_range = VEHICLE_RANGE_MILES
    miles_traveled = 0

    # Calculate cumulative distances along route points
    cumulative_distances = [0.0]
    for i in range(1, len(route_points)):
        d = haversine_distance(
            route_points[i-1][0], route_points[i-1][1],
            route_points[i][0], route_points[i][1]
        )
        cumulative_distances.append(cumulative_distances[-1] + d)

    # Scale cumulative distances to match total route distance
    raw_total = cumulative_distances[-1] if cumulative_distances[-1] > 0 else 1
    scale = total_distance_miles / raw_total
    cumulative_distances = [d * scale for d in cumulative_distances]

    # Determine refuel points
    next_refuel_at = VEHICLE_RANGE_MILES - REFUEL_BUFFER_MILES  # ~400 miles

    i = 0
    last_stop_miles = 0

    while i < len(route_points):
        current_miles = cumulative_distances[i]
        miles_since_last = current_miles - last_stop_miles
        remaining_distance = total_distance_miles - current_miles

        if remaining_distance <= 0:
            break

        # Check if we need to refuel
        if miles_since_last >= next_refuel_at or remaining_range <= REFUEL_BUFFER_MILES:
            # Search for cheapest station near this point
            lat, lng = route_points[i]

            # Search progressively wider if no stations found
            best = None
            for radius in [25, 50, 75, 100]:
                candidates = find_nearby_stations(lat, lng, radius)
                if candidates:
                    best = candidates[0]  # Cheapest (sorted by price)
                    break

            if best:
                station = best['station']
                miles_driven = current_miles - last_stop_miles
                gallons = miles_driven / MPG
                cost = gallons * station.retail_price

                fuel_stops.append(FuelStop(
                    station_name=station.name,
                    address=station.address,
                    city=station.city,
                    state=station.state,
                    latitude=station.latitude,
                    longitude=station.longitude,
                    fuel_price=station.retail_price,
                    miles_from_start=round(current_miles, 1),
                    gallons_needed=round(gallons, 2),
                    cost=round(cost, 2),
                ))

                last_stop_miles = current_miles
                remaining_range = VEHICLE_RANGE_MILES

            # Jump forward along the route
            target_miles = current_miles + next_refuel_at
            while i < len(route_points) and cumulative_distances[i] < target_miles:
                i += 1
            continue

        i += 1

    # Add final leg fuel calculation (fuel needed from last stop to destination)
    final_leg_miles = total_distance_miles - last_stop_miles
    if final_leg_miles > 0 and fuel_stops:
        # The last stop already accounts for fuel to get there
        # We need to account for the remaining distance
        pass

    return fuel_stops


def plan_route(start: str, end: str) -> RouteResult:
    """
    Main entry point: plan a route with optimal fuel stops.

    Args:
        start: Start location string (e.g., "New York, NY")
        end: End location string (e.g., "Los Angeles, CA")

    Returns:
        RouteResult with route details, fuel stops, and costs
    """
    # 1. Geocode locations
    s_lat, s_lng, s_city, s_state = geocode_location(start)
    if s_lat is None:
        raise ValueError(f"Could not geocode start location: '{start}'. "
                        f"Please use format: 'City, State' (e.g., 'New York, NY')")

    e_lat, e_lng, e_city, e_state = geocode_location(end)
    if e_lat is None:
        raise ValueError(f"Could not geocode end location: '{end}'. "
                        f"Please use format: 'City, State' (e.g., 'Los Angeles, CA')")

    # 2. Get route from OSRM (1 API call)
    osrm_route = get_osrm_route(s_lat, s_lng, e_lat, e_lng)

    if osrm_route:
        total_distance_miles = osrm_route['distance_meters'] / 1609.34
        route_points = decode_polyline(osrm_route['geometry'])
        # Convert to [lng, lat] for GeoJSON compatibility
        route_geometry = [[lng, lat] for lat, lng in route_points]
    else:
        # Fallback to straight-line approximation
        fallback = get_straight_line_route(s_lat, s_lng, e_lat, e_lng)
        total_distance_miles = fallback['distance_meters'] / 1609.34
        route_points = fallback['points']
        route_geometry = [[lng, lat] for lat, lng in route_points]

    # 3. Plan fuel stops
    fuel_stops = plan_fuel_stops(route_points, total_distance_miles)

    # 4. Calculate total cost
    # Include the final leg (from last stop to destination)
    if fuel_stops:
        last_stop_miles = fuel_stops[-1].miles_from_start
        final_leg_miles = total_distance_miles - last_stop_miles
        final_leg_gallons = final_leg_miles / MPG
        # For the final leg, use the average price of all stops
        avg_price = sum(s.fuel_price for s in fuel_stops) / len(fuel_stops)
        final_leg_cost = final_leg_gallons * avg_price

        total_fuel_cost = sum(s.cost for s in fuel_stops) + final_leg_cost
        total_gallons = sum(s.gallons_needed for s in fuel_stops) + final_leg_gallons
    else:
        # Trip is within range - calculate direct cost
        total_gallons = total_distance_miles / MPG
        # Find cheapest station near start for pricing
        nearby = find_nearby_stations(s_lat, s_lng, 100)
        if nearby:
            price = nearby[0]['station'].retail_price
        else:
            price = 3.50  # Default fallback
        total_fuel_cost = total_gallons * price

    # 5. Build result
    summary = (
        f"Route from {s_city}, {s_state} to {e_city}, {e_state}: "
        f"{total_distance_miles:.0f} miles, "
        f"{len(fuel_stops)} fuel stop(s), "
        f"{total_gallons:.1f} gallons, "
        f"${total_fuel_cost:.2f} total fuel cost"
    )

    return RouteResult(
        start_location=f"{s_city}, {s_state}",
        end_location=f"{e_city}, {e_state}",
        start_coords=(s_lat, s_lng),
        end_coords=(e_lat, e_lng),
        total_distance_miles=round(total_distance_miles, 1),
        route_geometry=route_geometry,
        fuel_stops=fuel_stops,
        total_fuel_cost=round(total_fuel_cost, 2),
        total_gallons=round(total_gallons, 1),
        summary=summary,
    )
