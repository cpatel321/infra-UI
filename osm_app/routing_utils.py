"""
Routing utilities for OSM road network partitioning.
Chinese Postman Problem solution with k-vehicle route optimization.
"""

import networkx as nx
import math
import json
import numpy as np
from xml.etree import ElementTree as ET


def haversine_m(lon1, lat1, lon2, lat2):
    """Calculate haversine distance in meters between two lat/lon points."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2.0)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2.0)**2
    return 2 * R * math.asin(math.sqrt(a))


class OSMRoutePartitioner:
    """Partition OSM road network into k vehicle routes using Chinese Postman algorithm."""
    
    def __init__(self, osm_file_path):
        self.osm_file_path = osm_file_path
        self.nodes = {}  # node_id -> (lat, lon)
        self.ways = []   # list of ways as list of node ids
        self.G = None    # NetworkX graph
        self.Gc = None   # Connected component graph
        self.depot = None
        self.centroid = None
        self.depot_lat = None
        self.depot_lon = None
        
    def parse_osm(self):
        """Parse OSM XML file and extract nodes and ways."""
        tree = ET.parse(self.osm_file_path)
        root = tree.getroot()
        
        # Parse nodes
        for node in root.findall('node'):
            node_id = node.get('id')
            lat = float(node.get('lat'))
            lon = float(node.get('lon'))
            self.nodes[node_id] = (lat, lon)
        
        # Parse ways (roads)
        for way in root.findall('way'):
            node_refs = []
            for nd in way.findall('nd'):
                ref = nd.get('ref')
                if ref in self.nodes:
                    node_refs.append(ref)
            if len(node_refs) >= 2:
                self.ways.append(node_refs)
        
        print(f"Parsed {len(self.nodes)} nodes and {len(self.ways)} ways")
        
    def build_graph(self):
        """Build NetworkX undirected graph from nodes and ways."""
        G = nx.MultiGraph()
        
        # Add nodes with lat/lon attributes
        for nid, (lat, lon) in self.nodes.items():
            G.add_node(nid, lat=lat, lon=lon)
        
        # Add edges between consecutive nodes in ways
        for way in self.ways:
            for u, v in zip(way[:-1], way[1:]):
                if u in self.nodes and v in self.nodes:
                    lat1, lon1 = self.nodes[u]
                    lat2, lon2 = self.nodes[v]
                    length = haversine_m(lon1, lat1, lon2, lat2)
                    G.add_edge(u, v, length=length)
        
        # Convert to simple graph (keep shortest edge between nodes)
        Gsimple = nx.Graph()
        for u, v, data in G.edges(data=True):
            length = data.get('length', 0.0)
            if Gsimple.has_edge(u, v):
                if length < Gsimple[u][v]['length']:
                    Gsimple[u][v]['length'] = length
            else:
                Gsimple.add_edge(u, v, length=length)
        
        # Copy node attributes only for nodes that exist in Gsimple
        for n in Gsimple.nodes():
            if n in G.nodes:
                Gsimple.nodes[n]['lat'] = G.nodes[n]['lat']
                Gsimple.nodes[n]['lon'] = G.nodes[n]['lon']
        
        self.G = Gsimple
        print(f"Built graph with {self.G.number_of_nodes()} nodes and {self.G.number_of_edges()} edges")
        
    def find_centroid_depot(self):
        """Find geometric centroid and nearest node as depot."""
        lats = np.array([lat for lat, lon in self.nodes.values()])
        lons = np.array([lon for lat, lon in self.nodes.values()])
        c_lat = float(lats.mean())
        c_lon = float(lons.mean())
        
        # Find nearest node to centroid
        best_node = None
        best_dist = float('inf')
        for nid, (lat, lon) in self.nodes.items():
            dist = haversine_m(lon, lat, c_lon, c_lat)
            if dist < best_dist:
                best_dist = dist
                best_node = nid
        
        self.depot = best_node
        self.centroid = (c_lat, c_lon)
        self.depot_lat = c_lat  # For easier access
        self.depot_lon = c_lon  # For easier access
        print(f"Centroid: ({c_lat:.6f}, {c_lon:.6f}), Depot node: {best_node}")
        
    def get_connected_component(self):
        """Get the largest connected component containing depot."""
        if self.depot is None:
            self.find_centroid_depot()
        
        # Find component containing depot
        for comp in nx.connected_components(self.G):
            if self.depot in comp:
                self.Gc = self.G.subgraph(comp).copy()
                self.G = self.Gc  # Keep reference for backward compatibility
                
                # Update self.nodes to only contain nodes in the connected component
                component_nodes = set(self.Gc.nodes())
                self.nodes = {nid: coords for nid, coords in self.nodes.items() if nid in component_nodes}
                
                print(f"Using connected component with {self.Gc.number_of_nodes()} nodes")
                return
        
        raise ValueError("Depot not in any connected component")
        
    def make_eulerian(self):
        """Make graph Eulerian using Chinese Postman algorithm."""
        # Find odd-degree nodes
        odd_nodes = [n for n in self.G.nodes() if (self.G.degree(n) % 2) == 1]
        
        if not odd_nodes:
            print("Graph is already Eulerian")
            return nx.MultiGraph(self.G), []
        
        print(f"Found {len(odd_nodes)} odd-degree nodes")
        
        # Create complete graph of odd nodes with shortest path distances
        K = nx.Graph()
        lengths = {}
        for n in odd_nodes:
            try:
                lengths[n] = nx.single_source_dijkstra_path_length(self.G, n, weight='length')
            except:
                lengths[n] = {}
        
        for i, u in enumerate(odd_nodes):
            for v in odd_nodes[i+1:]:
                length = lengths[u].get(v, float('inf'))
                if length < float('inf'):
                    K.add_edge(u, v, weight=length)
        
        # Find minimum weight perfect matching
        matching = nx.algorithms.matching.min_weight_matching(K, weight='weight')
        pairs = [tuple(e) for e in matching]
        
        print(f"Matched {len(pairs)} pairs of odd nodes")
        
        # Create multigraph with duplicate edges along shortest paths
        MG = nx.MultiGraph()
        for u, v, data in self.G.edges(data=True):
            MG.add_edge(u, v, **data)
        
        # Add duplicate edges for matched pairs
        for u, v in pairs:
            try:
                path = nx.shortest_path(self.G, u, v, weight='length')
                for a, b in zip(path[:-1], path[1:]):
                    length = self.G[a][b]['length']
                    MG.add_edge(a, b, length=length, duplicated=True)
            except:
                pass
        
        return MG, pairs
        
    def eulerian_circuit_edges(self, MG):
        """Extract Eulerian circuit starting from depot."""
        if not nx.is_eulerian(MG):
            raise ValueError("Graph is not Eulerian")
        
        circuit = list(nx.eulerian_circuit(MG, source=self.depot))
        
        # Handle different networkx versions
        seq = []
        for item in circuit:
            if len(item) == 3:
                u, v, _ = item
            else:
                u, v = item
            seq.append((u, v))
        
        return seq
        
    def split_circuit_into_k(self, circuit_edges, k):
        """Split Eulerian circuit into k balanced segments."""
        # Calculate edge lengths
        lengths = []
        for u, v in circuit_edges:
            if self.G.has_edge(u, v):
                lengths.append(self.G[u][v]['length'])
            else:
                lengths.append(0.0)
        
        total_length = sum(lengths)
        target_length = total_length / k
        
        segments = []
        current_segment = []
        current_length = 0.0
        
        for i, (u, v) in enumerate(circuit_edges):
            current_segment.append((u, v))
            current_length += lengths[i]
            
            remaining_segments = k - len(segments) - 1
            remaining_edges = len(circuit_edges) - (i + 1)
            
            if (current_length >= target_length and remaining_segments >= 0 and 
                remaining_edges >= remaining_segments) or (remaining_edges < remaining_segments):
                segments.append(current_segment)
                current_segment = []
                current_length = 0.0
        
        if current_segment:
            segments.append(current_segment)
        
        # Balance segments to exactly k
        while len(segments) < k:
            largest_idx = max(range(len(segments)), 
                            key=lambda i: sum(lengths[circuit_edges.index(e)] for e in segments[i]))
            seg = segments.pop(largest_idx)
            if len(seg) >= 2:
                mid = len(seg) // 2
                segments.insert(largest_idx, seg[:mid])
                segments.insert(largest_idx + 1, seg[mid:])
            else:
                segments.append([])
        
        while len(segments) > k:
            a = segments.pop()
            segments[-1].extend(a)
        
        return segments
        
    def build_vehicle_route(self, segment_edges):
        """Build complete route for vehicle: depot -> segment -> depot."""
        if not segment_edges:
            return [self.depot]
        
        start_node = segment_edges[0][0]
        end_node = segment_edges[-1][1]
        
        # Path from depot to segment start
        try:
            path_to_start = nx.shortest_path(self.G, self.depot, start_node, weight='length')
        except:
            path_to_start = [self.depot, start_node]
        
        # Segment nodes
        seg_nodes = [segment_edges[0][0]]
        for u, v in segment_edges:
            seg_nodes.append(v)
        
        # Path from segment end back to depot
        try:
            path_back = nx.shortest_path(self.G, end_node, self.depot, weight='length')
        except:
            path_back = [end_node, self.depot]
        
        # Combine paths
        full_nodes = path_to_start + seg_nodes[1:]  # Avoid duplicate start
        
        if path_back and path_back[0] == end_node:
            full_nodes.extend(path_back[1:])
        else:
            full_nodes.extend(path_back)
        
        # Remove consecutive duplicates
        final_nodes = [full_nodes[0]]
        for n in full_nodes[1:]:
            if n != final_nodes[-1]:
                final_nodes.append(n)
        
        return final_nodes
        
    def nodes_to_geojson_route(self, node_seq, vehicle_id):
        """Convert node sequence to GeoJSON LineString with length."""
        coords = []
        for nid in node_seq:
            if nid in self.nodes:
                lat, lon = self.nodes[nid]
                coords.append([lon, lat])  # GeoJSON order: [lon, lat]
            elif nid in self.G.nodes:
                # Fallback: get from graph node attributes
                lat = self.G.nodes[nid]['lat']
                lon = self.G.nodes[nid]['lon']
                coords.append([lon, lat])
            else:
                print(f"Warning: Node {nid} not found in nodes dict or graph")
        
        # Calculate route length
        total_length = 0.0
        for a, b in zip(node_seq[:-1], node_seq[1:]):
            if self.G.has_edge(a, b):
                total_length += self.G[a][b]['length']
            else:
                # Fallback
                try:
                    if a in self.nodes and b in self.nodes:
                        lat1, lon1 = self.nodes[a]
                        lat2, lon2 = self.nodes[b]
                    else:
                        lat1 = self.G.nodes[a]['lat']
                        lon1 = self.G.nodes[a]['lon']
                        lat2 = self.G.nodes[b]['lat']
                        lon2 = self.G.nodes[b]['lon']
                    total_length += haversine_m(lon1, lat1, lon2, lat2)
                except Exception as e:
                    print(f"Warning: Could not compute distance between {a} and {b}: {e}")
                    pass
        
        return {
            'type': 'Feature',
            'geometry': {
                'type': 'LineString',
                'coordinates': coords
            },
            'properties': {
                'vehicle_id': vehicle_id,
                'length_m': round(total_length, 2),
                'num_nodes': len(node_seq)
            }
        }
        
    def compute_routes(self, k):
        """Main function to compute k vehicle routes."""
        print(f"\n{'='*60}")
        print(f"🚗 ROUTE COMPUTATION STARTED")
        print(f"   Vehicles requested: {k}")
        print(f"{'='*60}")
        
        # Parse and build graph
        print(f"📖 Step 1: Parsing OSM data...")
        self.parse_osm()
        print(f"   ✓ Nodes: {len(self.nodes)}, Ways: {len(self.ways)}")
        
        print(f"🔨 Step 2: Building graph...")
        self.build_graph()
        print(f"   ✓ Graph nodes: {self.G.number_of_nodes()}, edges: {self.G.number_of_edges()}")
        
        # Find depot
        print(f"📍 Step 3: Finding centroid depot...")
        self.find_centroid_depot()
        print(f"   ✓ Depot at: ({self.depot_lat:.6f}, {self.depot_lon:.6f})")
        
        # Work with largest connected component
        print(f"🔗 Step 4: Extracting connected component...")
        self.get_connected_component()
        print(f"   ✓ Component nodes: {self.Gc.number_of_nodes()}, edges: {self.Gc.number_of_edges()}")
        
        # Make Eulerian
        print(f"⚡ Step 5: Making graph Eulerian...")
        MG, pairs = self.make_eulerian()
        print(f"   ✓ Eulerian graph edges: {MG.number_of_edges()}")
        print(f"   ✓ Added {len(pairs)} edge pairs to balance odd-degree nodes")
        
        # Extract Eulerian circuit
        print(f"🔄 Step 6: Extracting Eulerian circuit...")
        circuit_edges = self.eulerian_circuit_edges(MG)
        print(f"   ✓ Circuit contains {len(circuit_edges)} edges")
        
        # Split into k segments
        print(f"✂️  Step 7: Splitting circuit into {k} segments...")
        segments = self.split_circuit_into_k(circuit_edges, k)
        print(f"   ✓ Segments created: {len(segments)}")
        for i, seg in enumerate(segments, 1):
            print(f"      Vehicle {i}: {len(seg)} edges")
        
        # Build routes
        print(f"🗺️  Step 8: Building vehicle routes...")
        features = []
        for vid, seg in enumerate(segments, start=1):
            print(f"   Building route for Vehicle {vid}...")
            node_seq = self.build_vehicle_route(seg)
            route_feature = self.nodes_to_geojson_route(node_seq, vid)
            features.append(route_feature)
            print(f"   ✓ Vehicle {vid}: {len(node_seq)} nodes, {route_feature['properties']['length_m']:.2f} m")
        
        print(f"\n✅ ROUTE COMPUTATION COMPLETED")
        print(f"   Total routes: {len(features)}")
        print(f"{'='*60}\n")
        
        geojson_data = {
            'type': 'FeatureCollection',
            'features': features
        }
        
        return geojson_data
        
    def get_statistics(self):
        """Get road network statistics based on original OSM data (not augmented graph)."""
        # Count nodes that are in the connected component
        if self.G is None:
            return {}
        
        # Get nodes in the connected component
        component_nodes = set(self.G.nodes())
        
        # Filter ways to only include those with all nodes in component
        component_ways = []
        for way in self.ways:
            way_nodes = [nid for nid in way if nid in component_nodes]
            if len(way_nodes) >= 2:
                component_ways.append(way_nodes)
        
        # Calculate total length by summing all way segments
        total_length = 0.0
        for way in component_ways:
            for u, v in zip(way[:-1], way[1:]):
                if u in self.nodes and v in self.nodes:
                    lat1, lon1 = self.nodes[u]
                    lat2, lon2 = self.nodes[v]
                    total_length += haversine_m(lon1, lat1, lon2, lat2)
        
        # Count unique nodes actually used in ways
        used_nodes = set()
        for way in component_ways:
            used_nodes.update(way)
        
        total_ways = len(component_ways)
        total_nodes = len(used_nodes)
        
        return {
            'total_nodes': total_nodes,
            'total_roads': total_ways,
            'total_length_m': round(total_length, 2),
            'total_length_km': round(total_length / 1000, 2),
            'avg_road_length_m': round(total_length / total_ways, 2) if total_ways > 0 else 0,
            'depot_node': self.depot,
            'centroid': self.centroid
        }
