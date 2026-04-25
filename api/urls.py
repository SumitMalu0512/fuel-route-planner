from django.urls import path
from api.views import RouteplannerView, RouteMapView

urlpatterns = [
    path('route/', RouteplannerView.as_view(), name='route-planner'),
    path('route/map/', RouteMapView.as_view(), name='route-map'),
]
