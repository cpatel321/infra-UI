from django.urls import path
from . import views

app_name = 'osm_app'

urlpatterns = [
    path('', views.index, name='index'),
    path('upload/', views.upload_file, name='upload_file'),
    path('process/<int:file_id>/', views.process_file, name='process_file'),
    path('crop/<int:file_id>/', views.crop_file, name='crop_file'),
    path('download/<int:file_id>/', views.download_file, name='download_file'),
    path('get-osm-data/<int:file_id>/', views.get_osm_data, name='get_osm_data'),
    path('route-planning/<int:file_id>/', views.route_planning, name='route_planning'),
    path('compute-routes/<int:file_id>/', views.compute_routes, name='compute_routes'),
]
