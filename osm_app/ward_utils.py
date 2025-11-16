"""
Ward division utilities for multi-ward route planning
Divides large OSM areas into equal wards for parallel processing
"""

import math
import xml.etree.ElementTree as ET
from typing import List, Tuple, Dict
from .models import WardConfiguration, Ward, OSMFile
from django.utils import timezone


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points on Earth using Haversine formula.
    Returns distance in kilometers.
    """
    R = 6371.0  # Earth's radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def calculate_area_km2(min_lat: float, max_lat: float, min_lon: float, max_lon: float) -> float:
    """
    Calculate approximate area of a bounding box in square kilometers.
    Uses Haversine distance for better accuracy.
    """
    # Calculate width at center latitude
    center_lat = (min_lat + max_lat) / 2
    width_km = haversine_distance(center_lat, min_lon, center_lat, max_lon)
    
    # Calculate height
    height_km = haversine_distance(min_lat, min_lon, max_lat, min_lon)
    
    return width_km * height_km


def calculate_optimal_grid(num_wards: int) -> Tuple[int, int]:
    """
    Calculate optimal grid layout (rows × cols) for given number of wards.
    Tries to create a layout as close to square as possible.
    
    Returns: (rows, cols) tuple
    """
    cols = math.ceil(math.sqrt(num_wards))
    rows = math.ceil(num_wards / cols)
    return rows, cols


def divide_area_into_wards(osm_file: OSMFile, num_wards: int, ward_layout: str = 'auto_grid') -> WardConfiguration:
    """
    Divide the OSM area into equal wards using grid layout.
    
    Args:
        osm_file: OSMFile instance with bounding box
        num_wards: Number of wards to create
        ward_layout: Layout strategy ('auto_grid')
    
    Returns:
        WardConfiguration instance with associated Ward objects
    """
    # Calculate total area
    total_area = calculate_area_km2(
        osm_file.min_lat, osm_file.max_lat,
        osm_file.min_lon, osm_file.max_lon
    )
    
    # Calculate grid layout
    rows, cols = calculate_optimal_grid(num_wards)
    
    # Calculate approximate dimensions
    latRange = osm_file.max_lat - osm_file.min_lat
    lonRange = osm_file.max_lon - osm_file.min_lon
    
    kmPerLatDegree = 111.32
    kmPerLonDegree = 111.32 * math.cos(math.radians((osm_file.min_lat + osm_file.max_lat) / 2))
    
    totalWidthKm = lonRange * kmPerLonDegree
    totalHeightKm = latRange * kmPerLatDegree
    
    wardWidthKm = totalWidthKm / cols
    wardHeightKm = totalHeightKm / rows
    
    ward_dimensions = f"{wardWidthKm:.2f} × {wardHeightKm:.2f} km"
    
    # Create WardConfiguration
    config = WardConfiguration.objects.create(
        osm_file=osm_file,
        num_wards=num_wards,
        total_area_km2=total_area,
        area_per_ward_km2=total_area / num_wards,
        ward_layout=ward_layout,
        grid_rows=rows,
        grid_cols=cols,
        ward_dimensions_km=ward_dimensions
    )
    
    # Create individual wards
    lat_step = (osm_file.max_lat - osm_file.min_lat) / rows
    lon_step = (osm_file.max_lon - osm_file.min_lon) / cols
    
    ward_number = 1
    for row in range(rows):
        for col in range(cols):
            if ward_number > num_wards:
                break
                
            # Calculate ward boundaries
            ward_min_lat = osm_file.min_lat + (row * lat_step)
            ward_max_lat = osm_file.min_lat + ((row + 1) * lat_step)
            ward_min_lon = osm_file.min_lon + (col * lon_step)
            ward_max_lon = osm_file.min_lon + ((col + 1) * lon_step)
            
            # Calculate centroid
            centroid_lat = (ward_min_lat + ward_max_lat) / 2
            centroid_lon = (ward_min_lon + ward_max_lon) / 2
            
            # Calculate ward area
            ward_area = calculate_area_km2(ward_min_lat, ward_max_lat, ward_min_lon, ward_max_lon)
            
            # Create Ward object
            Ward.objects.create(
                config=config,
                ward_number=ward_number,
                min_lat=ward_min_lat,
                max_lat=ward_max_lat,
                min_lon=ward_min_lon,
                max_lon=ward_max_lon,
                centroid_lat=centroid_lat,
                centroid_lon=centroid_lon,
                area_km2=ward_area
            )
            
            ward_number += 1
    
    return config


def extract_ward_osm_data(osm_file_path: str, ward: Ward) -> str:
    """
    Extract OSM data for a specific ward from the full OSM file.
    Returns OSM XML string containing only ways and nodes within the ward boundaries.
    
    Args:
        osm_file_path: Path to the full OSM file
        ward: Ward instance with bounding box
    
    Returns:
        OSM XML string for the ward
    """
    tree = ET.parse(osm_file_path)
    root = tree.getroot()
    
    # Create new OSM root
    osm_root = ET.Element('osm', version='0.6', generator='WardExtractor')
    bounds = ET.SubElement(osm_root, 'bounds', 
                          minlat=str(ward.min_lat),
                          minlon=str(ward.min_lon),
                          maxlat=str(ward.max_lat),
                          maxlon=str(ward.max_lon))
    
    # First pass: collect nodes within ward boundaries
    ward_nodes = {}
    for node in root.findall('node'):
        lat = float(node.get('lat'))
        lon = float(node.get('lon'))
        
        if (ward.min_lat <= lat <= ward.max_lat and 
            ward.min_lon <= lon <= ward.max_lon):
            node_id = node.get('id')
            ward_nodes[node_id] = node
    
    # Second pass: collect ways that have at least one node in the ward
    ward_ways = []
    referenced_nodes = set()
    
    for way in root.findall('way'):
        way_nodes = [nd.get('ref') for nd in way.findall('nd')]
        
        # Check if any node of this way is in the ward
        has_node_in_ward = any(nd_ref in ward_nodes for nd_ref in way_nodes)
        
        if has_node_in_ward:
            ward_ways.append(way)
            referenced_nodes.update(way_nodes)
    
    # Add all referenced nodes (including those outside ward bounds but part of ways)
    for node in root.findall('node'):
        node_id = node.get('id')
        if node_id in referenced_nodes:
            osm_root.append(node)
    
    # Add ways
    for way in ward_ways:
        osm_root.append(way)
    
    # Convert to string
    osm_tree = ET.ElementTree(osm_root)
    return ET.tostring(osm_root, encoding='unicode')


def calculate_ward_statistics(osm_xml_string: str, ward: Ward) -> Dict:
    """
    Calculate statistics for a ward from its OSM data.
    Updates the Ward object with statistics.
    
    Args:
        osm_xml_string: OSM XML string for the ward
        ward: Ward instance to update
    
    Returns:
        Dictionary with statistics
    """
    from .routing_utils import OSMRoutePartitioner
    
    # Parse OSM data
    root = ET.fromstring(osm_xml_string)
    
    # Count nodes
    total_nodes = len(root.findall('node'))
    
    # Count ways and calculate total length
    ways = root.findall('way')
    total_ways = len(ways)
    total_length_m = 0.0
    
    # Build node lookup
    nodes = {}
    for node in root.findall('node'):
        node_id = node.get('id')
        lat = float(node.get('lat'))
        lon = float(node.get('lon'))
        nodes[node_id] = (lat, lon)
    
    # Calculate total road length
    for way in ways:
        way_nodes = [nd.get('ref') for nd in way.findall('nd')]
        
        for i in range(len(way_nodes) - 1):
            node1_id = way_nodes[i]
            node2_id = way_nodes[i + 1]
            
            if node1_id in nodes and node2_id in nodes:
                lat1, lon1 = nodes[node1_id]
                lat2, lon2 = nodes[node2_id]
                
                # Calculate segment length in meters
                dist_km = haversine_distance(lat1, lon1, lat2, lon2)
                total_length_m += dist_km * 1000
    
    # Update ward statistics
    ward.total_nodes = total_nodes
    ward.total_roads = total_ways
    ward.total_length_m = total_length_m
    ward.save()
    
    return {
        'total_nodes': total_nodes,
        'total_roads': total_ways,
        'total_length_m': total_length_m
    }
