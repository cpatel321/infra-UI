"""
Utility functions for processing OSM files
"""
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os


class OSMProcessor:
    """Process OSM files to extract only roads"""
    
    # Highway types that represent roads
    ROAD_TYPES = {
        'motorway', 'trunk', 'primary', 'secondary', 'tertiary',
        'unclassified', 'residential', 'service',
        'motorway_link', 'trunk_link', 'primary_link', 'secondary_link', 'tertiary_link',
        'living_street', 'pedestrian', 'track', 'road'
    }
    
    def __init__(self, input_file):
        self.input_file = input_file
        self.tree = None
        self.root = None
        
    def parse(self):
        """Parse the OSM file"""
        try:
            self.tree = ET.parse(self.input_file)
            self.root = self.tree.getroot()
            return True
        except Exception as e:
            print(f"Error parsing OSM file: {e}")
            return False
    
    def filter_roads_only(self):
        """Remove all elements except roads"""
        if self.root is None:
            return False
        
        # Keep track of node IDs that are used by road ways
        used_node_ids = set()
        
        # First pass: identify ways that are roads and collect their node references
        ways_to_keep = []
        for way in self.root.findall('way'):
            is_road = False
            for tag in way.findall('tag'):
                if tag.get('k') == 'highway' and tag.get('v') in self.ROAD_TYPES:
                    is_road = True
                    break
            
            if is_road:
                ways_to_keep.append(way)
                # Collect node references
                for nd in way.findall('nd'):
                    used_node_ids.add(nd.get('ref'))
        
        # Remove all ways
        for way in self.root.findall('way'):
            self.root.remove(way)
        
        # Add back only road ways
        for way in ways_to_keep:
            self.root.append(way)
        
        # Second pass: keep only nodes that are referenced by roads
        nodes_to_keep = []
        for node in self.root.findall('node'):
            if node.get('id') in used_node_ids:
                nodes_to_keep.append(node)
        
        # Remove all nodes
        for node in self.root.findall('node'):
            self.root.remove(node)
        
        # Add back only used nodes
        for node in nodes_to_keep:
            self.root.append(node)
        
        # Remove all relations (typically not needed for simple road display)
        for relation in self.root.findall('relation'):
            self.root.remove(relation)
        
        return True
    
    def crop_to_bbox(self, min_lat, max_lat, min_lon, max_lon):
        """Crop the OSM data to a bounding box"""
        if self.root is None:
            return False
        
        # Update the bounds element if it exists
        bounds = self.root.find('bounds')
        if bounds is not None:
            bounds.set('minlat', str(min_lat))
            bounds.set('maxlat', str(max_lat))
            bounds.set('minlon', str(min_lon))
            bounds.set('maxlon', str(max_lon))
        else:
            # Create bounds element
            bounds = ET.Element('bounds', {
                'minlat': str(min_lat),
                'maxlat': str(max_lat),
                'minlon': str(min_lon),
                'maxlon': str(max_lon)
            })
            self.root.insert(0, bounds)
        
        # Filter nodes within bounding box
        nodes_in_bbox = {}
        for node in self.root.findall('node'):
            try:
                lat = float(node.get('lat'))
                lon = float(node.get('lon'))
                node_id = node.get('id')
                
                if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                    nodes_in_bbox[node_id] = node
            except (ValueError, TypeError):
                pass
        
        # Remove all nodes
        for node in self.root.findall('node'):
            self.root.remove(node)
        
        # Add back only nodes in bbox
        for node in nodes_in_bbox.values():
            self.root.append(node)
        
        # Filter ways - keep only ways that have at least 2 nodes in bbox
        ways_to_keep = []
        for way in self.root.findall('way'):
            nodes_in_way = [nd.get('ref') for nd in way.findall('nd')]
            valid_nodes = [nid for nid in nodes_in_way if nid in nodes_in_bbox]
            
            if len(valid_nodes) >= 2:
                # Update way to only include valid nodes
                for nd in way.findall('nd'):
                    way.remove(nd)
                for nid in valid_nodes:
                    nd_elem = ET.Element('nd', {'ref': nid})
                    way.append(nd_elem)
                ways_to_keep.append(way)
        
        # Remove all ways
        for way in self.root.findall('way'):
            self.root.remove(way)
        
        # Add back valid ways
        for way in ways_to_keep:
            self.root.append(way)
        
        return True
    
    def save(self, output_file):
        """Save the processed OSM file"""
        if self.root is None:
            return False
        
        try:
            # Convert to string with pretty formatting
            xml_str = ET.tostring(self.root, encoding='unicode')
            
            # Parse and prettify
            dom = minidom.parseString(xml_str)
            pretty_xml = dom.toprettyxml(indent='  ')
            
            # Remove extra blank lines
            lines = [line for line in pretty_xml.split('\n') if line.strip()]
            pretty_xml = '\n'.join(lines)
            
            # Write to file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(pretty_xml)
            
            return True
        except Exception as e:
            print(f"Error saving OSM file: {e}")
            return False
    
    def get_bounds(self):
        """Get the bounding box of the OSM data"""
        if self.root is None:
            return None
        
        # Check for existing bounds element
        bounds = self.root.find('bounds')
        if bounds is not None:
            try:
                return {
                    'min_lat': float(bounds.get('minlat')),
                    'max_lat': float(bounds.get('maxlat')),
                    'min_lon': float(bounds.get('minlon')),
                    'max_lon': float(bounds.get('maxlon'))
                }
            except (ValueError, TypeError):
                pass
        
        # Calculate bounds from nodes
        min_lat = min_lon = float('inf')
        max_lat = max_lon = float('-inf')
        
        for node in self.root.findall('node'):
            try:
                lat = float(node.get('lat'))
                lon = float(node.get('lon'))
                min_lat = min(min_lat, lat)
                max_lat = max(max_lat, lat)
                min_lon = min(min_lon, lon)
                max_lon = max(max_lon, lon)
            except (ValueError, TypeError):
                pass
        
        if min_lat == float('inf'):
            return None
        
        return {
            'min_lat': min_lat,
            'max_lat': max_lat,
            'min_lon': min_lon,
            'max_lon': max_lon
        }
    
    def get_geojson(self):
        """Convert OSM data to GeoJSON for map display"""
        if self.root is None:
            return None
        
        # Build node lookup
        nodes = {}
        for node in self.root.findall('node'):
            node_id = node.get('id')
            try:
                nodes[node_id] = {
                    'lat': float(node.get('lat')),
                    'lon': float(node.get('lon'))
                }
            except (ValueError, TypeError):
                pass
        
        # Build features from ways
        features = []
        for way in self.root.findall('way'):
            # Get way properties
            properties = {'id': way.get('id')}
            for tag in way.findall('tag'):
                properties[tag.get('k')] = tag.get('v')
            
            # Get coordinates
            coordinates = []
            for nd in way.findall('nd'):
                node_id = nd.get('ref')
                if node_id in nodes:
                    node = nodes[node_id]
                    coordinates.append([node['lon'], node['lat']])
            
            if len(coordinates) >= 2:
                feature = {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': coordinates
                    },
                    'properties': properties
                }
                features.append(feature)
        
        return {
            'type': 'FeatureCollection',
            'features': features
        }
