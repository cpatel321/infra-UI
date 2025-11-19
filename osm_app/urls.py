from django.urls import path
from . import views

app_name = 'osm_app'

urlpatterns = [
    path('', views.index, name='index'),
    path('use-default-map/', views.use_default_map, name='use_default_map'),
    path('upload/', views.upload_file, name='upload_file'),
    path('process/<int:file_id>/', views.process_file, name='process_file'),
    path('crop/<int:file_id>/', views.crop_file, name='crop_file'),
    path('download/<int:file_id>/', views.download_file, name='download_file'),
    path('get-osm-data/<int:file_id>/', views.get_osm_data, name='get_osm_data'),
    path('ward-config/<int:file_id>/', views.ward_config, name='ward_config'),
    path('<int:file_id>/create-ward-config/', views.create_ward_config, name='create_ward_config'),
    path('<int:file_id>/multiward-routing/', views.multiward_routing, name='multiward_routing'),
    path('<int:file_id>/compute-ward-route/', views.compute_ward_route, name='compute_ward_route'),
    path('route-planning/<int:file_id>/', views.route_planning, name='route_planning'),
    path('compute-routes/<int:file_id>/', views.compute_routes, name='compute_routes'),
    path('log-computation/', views.log_computation, name='log_computation'),
]
