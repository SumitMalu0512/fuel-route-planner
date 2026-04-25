from dataclasses import asdict
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from django.template.loader import render_to_string

from api.serializers import RouteRequestSerializer, RouteResponseSerializer
from api.services import plan_route


class RouteplannerView(APIView):
    """
    Plan a fuel-optimized route between two US locations.

    POST /api/route/
    {
        "start": "New York, NY",
        "end": "Los Angeles, CA"
    }

    Returns route details with optimal fuel stops based on price,
    assuming 500-mile vehicle range and 10 MPG fuel efficiency.
    """

    def post(self, request):
        serializer = RouteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        start = serializer.validated_data['start']
        end = serializer.validated_data['end']

        try:
            result = plan_route(start, end)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {'error': f'An error occurred while planning the route: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Convert result to dict
        result_dict = asdict(result)

        # Add map URL (URL-encode spaces as + for valid links)
        from urllib.parse import quote
        result_dict['map_url'] = (
            f"{request.build_absolute_uri('/api/route/map/')}?"
            f"start={quote(start)}&end={quote(end)}"
        )

        # Serialize response
        response_serializer = RouteResponseSerializer(data=result_dict)
        response_serializer.is_valid(raise_exception=True)

        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def get(self, request):
        """Also support GET requests for convenience."""
        start = request.query_params.get('start')
        end = request.query_params.get('end')

        if not start or not end:
            return Response(
                {
                    'message': 'Fuel Route Planner API',
                    'usage': 'POST /api/route/ with {"start": "City, ST", "end": "City, ST"}',
                    'example': {
                        'start': 'New York, NY',
                        'end': 'Los Angeles, CA',
                    },
                    'parameters': {
                        'start': 'Start location in "City, State" format',
                        'end': 'End location in "City, State" format',
                    },
                    'assumptions': {
                        'vehicle_range_miles': 500,
                        'fuel_efficiency_mpg': 10,
                    },
                },
                status=status.HTTP_200_OK,
            )

        # Process GET request same as POST
        request.data.update({'start': start, 'end': end})
        return self.post(request)


class RouteMapView(APIView):
    """
    Render an interactive HTML map showing the route and fuel stops.

    GET /api/route/map/?start=New+York,+NY&end=Los+Angeles,+CA
    """

    def get(self, request):
        start = request.query_params.get('start')
        end = request.query_params.get('end')

        if not start or not end:
            return Response(
                {'error': 'Both "start" and "end" query parameters are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = plan_route(start, end)
        except ValueError as e:
            return HttpResponse(f"<h1>Error</h1><p>{e}</p>", status=400)
        except Exception as e:
            return HttpResponse(f"<h1>Error</h1><p>{e}</p>", status=500)

        result_dict = asdict(result)
        html = generate_map_html(result_dict)
        return HttpResponse(html, content_type='text/html')


def generate_map_html(route_data: dict) -> str:
    """Generate an HTML page with a Leaflet map showing route and fuel stops."""
    import json

    start_lat, start_lng = route_data['start_coords']
    end_lat, end_lng = route_data['end_coords']

    # Build fuel stops JS array
    stops_js = json.dumps([{
        'name': s['station_name'],
        'address': s['address'],
        'city': s['city'],
        'state': s['state'],
        'lat': s['latitude'],
        'lng': s['longitude'],
        'price': s['fuel_price'],
        'miles': s['miles_from_start'],
        'gallons': s['gallons_needed'],
        'cost': s['cost'],
    } for s in route_data['fuel_stops']])

    route_coords_js = json.dumps(
        [[coord[1], coord[0]] for coord in route_data['route_geometry']]
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Fuel Route Planner - {route_data['start_location']} to {route_data['end_location']}</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
        #map {{ height: 65vh; width: 100%; }}
        .info-panel {{
            padding: 20px;
            background: #f8f9fa;
            border-top: 2px solid #dee2e6;
        }}
        .info-panel h2 {{ margin-bottom: 10px; color: #212529; }}
        .summary {{ font-size: 1.1em; color: #495057; margin-bottom: 15px; }}
        .stops-list {{ list-style: none; }}
        .stops-list li {{
            background: white;
            padding: 12px 16px;
            margin-bottom: 8px;
            border-radius: 8px;
            border-left: 4px solid #28a745;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .stop-name {{ font-weight: 600; color: #212529; }}
        .stop-detail {{ color: #6c757d; font-size: 0.9em; margin-top: 4px; }}
        .cost-highlight {{ color: #28a745; font-weight: 700; font-size: 1.2em; }}
        .header {{
            background: #212529;
            color: white;
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header h1 {{ font-size: 1.3em; }}
        .total-cost {{ font-size: 1.4em; font-weight: 700; color: #28a745; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚛 {route_data['start_location']} → {route_data['end_location']}</h1>
        <div>
            <span>{route_data['total_distance_miles']:.0f} miles</span> |
            <span class="total-cost">${route_data['total_fuel_cost']:.2f} fuel</span>
        </div>
    </div>
    <div id="map"></div>
    <div class="info-panel">
        <h2>Route Summary</h2>
        <p class="summary">{route_data['summary']}</p>
        <h3>Fuel Stops ({len(route_data['fuel_stops'])})</h3>
        <ul class="stops-list" id="stops-list"></ul>
    </div>

    <script>
        var startCoords = [{start_lat}, {start_lng}];
        var endCoords = [{end_lat}, {end_lng}];
        var fuelStops = {stops_js};
        var routeCoords = {route_coords_js};

        // Initialize map
        var map = L.map('map');

        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 20
        }}).addTo(map);

        // Draw route
        if (routeCoords.length > 0) {{
            var polyline = L.polyline(routeCoords, {{
                color: '#4285F4',
                weight: 4,
                opacity: 0.8
            }}).addTo(map);
            map.fitBounds(polyline.getBounds().pad(0.1));
        }} else {{
            map.fitBounds([startCoords, endCoords]);
        }}

        // Start marker (green)
        L.marker(startCoords, {{
            icon: L.divIcon({{
                className: '',
                html: '<div style="background:#28a745;color:white;border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:14px;border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3);">A</div>',
                iconSize: [32, 32],
                iconAnchor: [16, 16],
            }})
        }}).addTo(map).bindPopup('<b>Start:</b> {route_data["start_location"]}');

        // End marker (red)
        L.marker(endCoords, {{
            icon: L.divIcon({{
                className: '',
                html: '<div style="background:#dc3545;color:white;border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:14px;border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3);">B</div>',
                iconSize: [32, 32],
                iconAnchor: [16, 16],
            }})
        }}).addTo(map).bindPopup('<b>End:</b> {route_data["end_location"]}');

        // Fuel stop markers (orange)
        var stopsList = document.getElementById('stops-list');
        fuelStops.forEach(function(stop, idx) {{
            L.marker([stop.lat, stop.lng], {{
                icon: L.divIcon({{
                    className: '',
                    html: '<div style="background:#fd7e14;color:white;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:12px;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.3);">⛽</div>',
                    iconSize: [28, 28],
                    iconAnchor: [14, 14],
                }})
            }}).addTo(map).bindPopup(
                '<b>' + stop.name + '</b><br>' +
                stop.city + ', ' + stop.state + '<br>' +
                'Price: $' + stop.price.toFixed(3) + '/gal<br>' +
                'Gallons: ' + stop.gallons.toFixed(1) + '<br>' +
                'Cost: $' + stop.cost.toFixed(2)
            );

            var li = document.createElement('li');
            li.innerHTML = '<div class="stop-name">⛽ Stop ' + (idx + 1) + ': ' + stop.name + '</div>' +
                '<div class="stop-detail">' + stop.city + ', ' + stop.state + ' | ' +
                stop.address + ' | Mile ' + stop.miles.toFixed(0) + '</div>' +
                '<div class="stop-detail">$' + stop.price.toFixed(3) + '/gal × ' +
                stop.gallons.toFixed(1) + ' gal = <span class="cost-highlight">$' +
                stop.cost.toFixed(2) + '</span></div>';
            stopsList.appendChild(li);
        }});

        if (fuelStops.length === 0) {{
            stopsList.innerHTML = '<li>No fuel stops needed - destination is within vehicle range (500 miles).</li>';
        }}
    </script>
</body>
</html>"""
    return html
