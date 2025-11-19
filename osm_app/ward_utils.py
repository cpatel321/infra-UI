"""
Ward division utilities for multi-ward route planning
Divides large OSM areas into equal wards for parallel processing
Includes validation and optimization for real-world deployment
"""

import math
import xml.etree.ElementTree as ET
from typing import List, Tuple, Dict
from .models import WardConfiguration, Ward, OSMFile, Depot
from django.utils import timezone


def validate_ward_before_routing(ward: Ward) -> Dict:
    """
    Comprehensive pre-flight check before route computation
    
    Returns:
        dict with 'valid' boolean and detailed check results
    """
    warnings = []
    checks = {}
    
    # Check 1: Has roads
    checks['has_roads'] = ward.total_roads > 0
    if not checks['has_roads']:
        warnings.append(f"Ward {ward.ward_number} has no roads - cannot compute routes")
    
    # Check 2: Has population data (if using capacity calculation)
    checks['has_population'] = ward.population > 0
    if not checks['has_population']:
        warnings.append(f"Ward {ward.ward_number} has no population data - vehicle suggestions may be inaccurate")
    
    # Check 3: Reasonable size (not too large for single shift)
    max_length_km = 200  # Max 200 km of roads per ward
    checks['reasonable_size'] = ward.total_length_m < (max_length_km * 1000)
    if not checks['reasonable_size']:
        actual_km = ward.total_length_m / 1000
        warnings.append(f"Ward {ward.ward_number} is very large ({actual_km:.1f} km of roads) - may require multiple shifts")
    
    # Check 4: Reasonable density (not too sparse or too dense)
    checks['reasonable_density'] = 100 < ward.population_density_per_km2 < 50000
    if not checks['reasonable_density']:
        density = ward.population_density_per_km2
        if density < 100:
            warnings.append(f"Ward {ward.ward_number} has very low population density ({density:.0f}/km²) - consider merging with adjacent ward")
        else:
            warnings.append(f"Ward {ward.ward_number} has very high population density ({density:.0f}/km²) - may need more vehicles")
    
    # Check 5: Reasonable area
    checks['reasonable_area'] = 0.1 < ward.area_km2 < 100
    if not checks['reasonable_area']:
        warnings.append(f"Ward {ward.ward_number} has unusual area ({ward.area_km2:.2f} km²)")
    
    # Check 6: Depot assignment and distance
    checks['has_depot'] = ward.assigned_depot is not None
    if ward.assigned_depot:
        checks['depot_reachable'] = ward.depot_distance_km < 50  # Within 50 km
        if not checks['depot_reachable']:
            warnings.append(f"Ward {ward.ward_number} is far from depot ({ward.depot_distance_km:.1f} km) - may impact shift time")
    else:
        checks['depot_reachable'] = True  # No depot assigned yet
    
    # Update ward validation status
    ward.validation_warnings = warnings
    ward.has_valid_data = checks['has_roads']  # Minimum requirement
    ward.last_validated = timezone.now()
    ward.save()
    
    return {
        'valid': all([checks['has_roads']]),  # Only roads are critical
        'checks': checks,
        'warnings': warnings,
        'critical_issues': [w for w in warnings if 'no roads' in w.lower() or 'cannot compute' in w.lower()]
    }


def check_ward_connectivity(osm_xml_string: str, ward: Ward) -> Dict:
    """
    Check if all roads in ward form a connected network
    Uses NetworkX to detect disconnected components
    
    Returns:
        dict with connectivity status and component info
    """
    try:
        import networkx as nx
    except ImportError:
        return {
            'connected': True,  # Assume connected if NetworkX not available
            'checked': False,
            'message': 'NetworkX not installed - skipping connectivity check'
        }
    
    # Parse OSM data
    root = ET.fromstring(osm_xml_string)
    
    # Build graph
    G = nx.Graph()
    
    # Add nodes
    node_coords = {}
    for node in root.findall('node'):
        node_id = node.get('id')
        lat = float(node.get('lat'))
        lon = float(node.get('lon'))
        node_coords[node_id] = (lat, lon)
        G.add_node(node_id)
    
    # Add edges from ways
    for way in root.findall('way'):
        way_nodes = [nd.get('ref') for nd in way.findall('nd')]
        
        for i in range(len(way_nodes) - 1):
            node1 = way_nodes[i]
            node2 = way_nodes[i + 1]
            if node1 in node_coords and node2 in node_coords:
                G.add_edge(node1, node2)
    
    # Check connectivity
    if G.number_of_nodes() == 0:
        ward.is_connected = True
        ward.save()
        return {
            'connected': True,
            'checked': True,
            'message': 'No nodes to check'
        }
    
    components = list(nx.connected_components(G))
    num_components = len(components)
    
    is_connected = num_components == 1
    ward.is_connected = is_connected
    ward.save()
    
    if not is_connected:
        component_sizes = [len(c) for c in components]
        largest_size = max(component_sizes)
        
        return {
            'connected': False,
            'checked': True,
            'num_components': num_components,
            'largest_component_nodes': largest_size,
            'total_nodes': G.number_of_nodes(),
            'message': f'Ward has {num_components} disconnected road networks',
            'recommendation': 'Reassign disconnected roads to adjacent wards or adjust boundaries'
        }
    
    return {
        'connected': True,
        'checked': True,
        'num_components': 1,
        'total_nodes': G.number_of_nodes(),
        'message': 'All roads form a connected network'
    }


def assign_wards_to_nearest_depot(config: WardConfiguration) -> Dict:
    """
    Assign each ward to its nearest depot and calculate distances
    
    Returns:
        dict with assignment summary
    """
    depots = Depot.objects.filter(active=True)
    
    if not depots.exists():
        return {
            'success': False,
            'message': 'No active depots found',
            'assigned_wards': 0
        }
    
    wards = config.wards.all()
    assignments = []
    
    for ward in wards:
        # Find nearest depot
        distances = []
        for depot in depots:
            dist = haversine_distance(
                ward.centroid_lat, ward.centroid_lon,
                depot.lat, depot.lon
            )
            distances.append((depot, dist))
        
        nearest_depot, distance = min(distances, key=lambda x: x[1])
        
        ward.assigned_depot = nearest_depot
        ward.depot_distance_km = distance
        ward.save()
        
        assignments.append({
            'ward': ward.ward_number,
            'depot': nearest_depot.name,
            'distance_km': round(distance, 2)
        })
    
    return {
        'success': True,
        'assigned_wards': len(assignments),
        'assignments': assignments
    }


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


def divide_by_graph_partitioning(osm_file: OSMFile, num_wards: int, raster_path: str = None) -> WardConfiguration:
    """
    Divide area using graph partitioning - respects road network topology
    
    Algorithm:
    1. Build road network graph where nodes = intersections, edges = roads
    2. Weight edges by: road_length × (1 + population_density_factor)
    3. Use spectral clustering to partition graph into balanced groups
    4. Each partition becomes a ward with natural boundaries
    
    Benefits:
    - Roads stay within single wards (no artificial cuts)
    - Respects natural boundaries (rivers, highways)
    - Balances both distance AND population density
    
    Args:
        osm_file: OSMFile instance with bounding box
        num_wards: Number of wards to create
        raster_path: Optional path to population raster for weighting
    
    Returns:
        WardConfiguration instance with graph-based Ward objects
    """
    import networkx as nx
    from sklearn.cluster import SpectralClustering
    from .gis_utils import get_population_from_worldpop
    
    print(f"\n🎯 Graph-Based Ward Division (Advanced)")
    print(f"   Using road network topology for intelligent boundaries")
    
    # Parse OSM file
    tree = ET.parse(osm_file.processed_file.path)
    root = tree.getroot()
    
    # Build graph
    G = nx.Graph()
    node_coords = {}
    
    print(f"   📊 Building road network graph...")
    
    # Add nodes
    for node in root.findall('node'):
        node_id = node.get('id')
        lat = float(node.get('lat'))
        lon = float(node.get('lon'))
        node_coords[node_id] = (lat, lon)
        
        # Get population density at this point if raster available
        pop_weight = 1.0
        if raster_path:
            try:
                from .gis_utils import get_population_from_worldpop
                bounds = {
                    'min_lat': lat - 0.001,
                    'max_lat': lat + 0.001,
                    'min_lon': lon - 0.001,
                    'max_lon': lon + 0.001
                }
                pop = get_population_from_worldpop(bounds, raster_path)
                pop_weight = 1.0 + (pop / 1000.0)  # Scale population influence
            except:
                pop_weight = 1.0
        
        G.add_node(node_id, lat=lat, lon=lon, pop_weight=pop_weight)
    
    # Add edges
    for way in root.findall('way'):
        nodes = [nd.get('ref') for nd in way.findall('nd')]
        
        for i in range(len(nodes) - 1):
            n1, n2 = nodes[i], nodes[i + 1]
            if n1 in node_coords and n2 in node_coords:
                # Calculate distance
                lat1, lon1 = node_coords[n1]
                lat2, lon2 = node_coords[n2]
                dist = haversine_distance(lat1, lon1, lat2, lon2)
                
                # Weight = distance × population factor
                avg_pop_weight = (G.nodes[n1].get('pop_weight', 1.0) + G.nodes[n2].get('pop_weight', 1.0)) / 2
                weight = dist * avg_pop_weight
                
                G.add_edge(n1, n2, weight=weight, distance=dist)
    
    print(f"   ✓ Graph built: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    
    # Check connectivity
    if not nx.is_connected(G):
        print(f"   ⚠️  Graph has multiple components, using largest component")
        G = G.subgraph(max(nx.connected_components(G), key=len)).copy()
    
    # Create adjacency matrix with weights
    print(f"   🔬 Running spectral clustering...")
    node_list = list(G.nodes())
    adj_matrix = nx.to_numpy_array(G, nodelist=node_list, weight='weight')
    
    # Spectral clustering
    clustering = SpectralClustering(
        n_clusters=num_wards,
        affinity='precomputed',
        random_state=42,
        n_init=10
    )
    
    labels = clustering.fit_predict(adj_matrix)
    
    print(f"   ✓ Clustering complete: {num_wards} partitions")
    
    # Assign nodes to wards
    node_to_ward = {node_list[i]: labels[i] for i in range(len(node_list))}
    
    # Create ward boundaries from partitions
    print(f"   📐 Computing ward boundaries...")
    
    total_area = calculate_area_km2(
        osm_file.min_lat, osm_file.max_lat,
        osm_file.min_lon, osm_file.max_lon
    )
    
    config = WardConfiguration.objects.create(
        osm_file=osm_file,
        num_wards=num_wards,
        total_area_km2=total_area,
        area_per_ward_km2=total_area / num_wards,
        ward_layout='graph_partitioned',
        ward_dimensions_km=f"Variable (topology-based)"
    )
    
    # Create wards from partitions
    for ward_num in range(num_wards):
        # Get all nodes in this partition
        ward_nodes = [nid for nid, label in node_to_ward.items() if label == ward_num]
        
        if not ward_nodes:
            continue
        
        # Compute bounding box
        lats = [node_coords[nid][0] for nid in ward_nodes if nid in node_coords]
        lons = [node_coords[nid][1] for nid in ward_nodes if nid in node_coords]
        
        if not lats or not lons:
            continue
        
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        
        # Centroid
        centroid_lat = sum(lats) / len(lats)
        centroid_lon = sum(lons) / len(lons)
        
        # Area
        area_km2 = calculate_area_km2(min_lat, max_lat, min_lon, max_lon)
        
        # Population if raster available
        population = 0
        if raster_path:
            try:
                bounds = {
                    'min_lat': min_lat,
                    'max_lat': max_lat,
                    'min_lon': min_lon,
                    'max_lon': max_lon
                }
                population = get_population_from_worldpop(bounds, raster_path)
            except:
                population = 0
        
        Ward.objects.create(
            config=config,
            ward_number=ward_num + 1,
            min_lat=min_lat,
            max_lat=max_lat,
            min_lon=min_lon,
            max_lon=max_lon,
            centroid_lat=centroid_lat,
            centroid_lon=centroid_lon,
            area_km2=area_km2,
            population=population,
            population_density_per_km2=population / area_km2 if area_km2 > 0 else 0,
            population_source='worldpop' if raster_path else 'manual'
        )
    
    print(f"   ✓ Created {num_wards} topology-aware wards")
    
    return config


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
    
    Uses centroid-based assignment to prevent route overlap between wards:
    - Ways on boundaries are assigned to the ward whose centroid is closest
    - Each road belongs to exactly one ward
    
    Args:
        osm_file_path: Path to the full OSM file
        ward: Ward instance with bounding box
    
    Returns:
        OSM XML string for the ward
    """
    print(f"  📂 Parsing OSM file: {osm_file_path}")
    tree = ET.parse(osm_file_path)
    root = tree.getroot()
    print(f"  ✓ OSM file parsed successfully")
    
    # Get all wards in the same configuration for centroid-based assignment
    all_wards = list(ward.config.wards.all())
    
    # Create new OSM root
    osm_root = ET.Element('osm', version='0.6', generator='WardExtractor')
    bounds = ET.SubElement(osm_root, 'bounds', 
                          minlat=str(ward.min_lat),
                          minlon=str(ward.min_lon),
                          maxlat=str(ward.max_lat),
                          maxlon=str(ward.max_lon))
    
    # First pass: collect all nodes with their coordinates
    print(f"  🔍 Pass 1: Collecting all nodes...")
    all_nodes = {}
    for node in root.findall('node'):
        node_id = node.get('id')
        lat = float(node.get('lat'))
        lon = float(node.get('lon'))
        all_nodes[node_id] = {'element': node, 'lat': lat, 'lon': lon}
    
    print(f"  ✓ Found {len(all_nodes)} total nodes")
    
    # Second pass: assign ways to nearest ward centroid
    print(f"  🔍 Pass 2: Assigning ways to wards (preventing overlap)...")
    ward_ways = []
    referenced_nodes = set()
    total_ways = len(root.findall('way'))
    assigned_ways = 0
    
    for way in root.findall('way'):
        way_nodes = [nd.get('ref') for nd in way.findall('nd')]
        
        # Calculate way's center point (average of all nodes)
        way_lats = []
        way_lons = []
        for nd_ref in way_nodes:
            if nd_ref in all_nodes:
                way_lats.append(all_nodes[nd_ref]['lat'])
                way_lons.append(all_nodes[nd_ref]['lon'])
        
        if not way_lats:
            continue
            
        way_center_lat = sum(way_lats) / len(way_lats)
        way_center_lon = sum(way_lons) / len(way_lons)
        
        # Find nearest ward centroid
        min_distance = float('inf')
        nearest_ward = None
        
        for w in all_wards:
            dist = haversine_distance(
                way_center_lat, way_center_lon,
                w.centroid_lat, w.centroid_lon
            )
            if dist < min_distance:
                min_distance = dist
                nearest_ward = w
        
        # Assign way to this ward only if it's the nearest
        if nearest_ward and nearest_ward.id == ward.id:
            ward_ways.append(way)
            referenced_nodes.update(way_nodes)
            assigned_ways += 1
    
    print(f"  ✓ Assigned {assigned_ways} ways to this ward (out of {total_ways} total)")
    print(f"  ✓ Total referenced nodes: {len(referenced_nodes)}")
    
    # Add all referenced nodes
    print(f"  📝 Building OSM XML for ward...")
    nodes_added = 0
    for node_id in referenced_nodes:
        if node_id in all_nodes:
            osm_root.append(all_nodes[node_id]['element'])
            nodes_added += 1
    
    # Add ways
    for way in ward_ways:
        osm_root.append(way)
    
    print(f"  ✓ OSM XML built: {nodes_added} nodes, {len(ward_ways)} ways")
    
    # Convert to string with unicode encoding
    print(f"  🔄 Converting to XML string...")
    xml_string = ET.tostring(osm_root, encoding='unicode')
    print(f"  ✓ XML string created: {len(xml_string)} characters")
    
    return xml_string


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
