# Municipal Waste Collection System - Capacitated Vehicle Routing

## Current Implementation (Phase 1: Time-Based Optimization) ✅

### What We Have Now:
- **Vehicle Speed Parameter**: Average collection speed in km/h
- **Time Window**: Maximum operation time per vehicle
- **Automatic Calculation**: System suggests optimal number of vehicles based on:
  ```
  Total Time Needed = Total Road Length (km) / Vehicle Speed (km/h)
  Vehicles Needed = ceil(Total Time / Time Window)
  ```

---

## Phase 2: Capacitated Vehicle Routing Problem (CVRP)

### Overview
Each vehicle has limited capacity, and each household/location generates waste. Need to optimize routes considering both **distance** and **capacity constraints**.

### Key Components to Add:

#### 1. **Waste Generation Data**
**Option A: Population Density-Based (Recommended)**
```python
# Add to each road segment/node
waste_per_household = 2.5  # kg per household per day
households_per_100m = 8    # average household density
road_length_m = 500

estimated_waste = (road_length_m / 100) * households_per_100m * waste_per_household
```

**Option B: OSM Building Data**
- Use OpenStreetMap building footprints
- Count buildings within buffer zone of each road
- Assign waste generation per building type

**Option C: Manual/Survey Data**
- Allow users to upload CSV with road IDs and waste amounts
- Use GIS data if available

#### 2. **Vehicle Capacity**
Add parameters:
- **Vehicle Capacity**: e.g., 2000 kg, 5000 kg (small/large trucks)
- **Collection Efficiency**: Time to collect waste at each stop (minutes)
- **Dump Time**: Time to go to landfill and return

#### 3. **Implementation Approaches**

### **Approach 1: Two-Phase Method (Simple, Recommended for MVP)**

**Phase A: Cluster roads by capacity**
```python
def cluster_by_capacity(roads, vehicle_capacity):
    clusters = []
    current_cluster = []
    current_load = 0
    
    for road in roads:
        if current_load + road.waste <= vehicle_capacity:
            current_cluster.append(road)
            current_load += road.waste
        else:
            clusters.append(current_cluster)
            current_cluster = [road]
            current_load = road.waste
    
    return clusters
```

**Phase B: Optimize route within each cluster**
- Use Chinese Postman for each cluster
- Each cluster = one vehicle route

**Advantages**:
- Easy to implement
- Works with existing Chinese Postman algorithm
- Fast computation

**Disadvantages**:
- Not globally optimal
- May need manual balancing

---

### **Approach 2: OR-Tools CVRP (Production-Ready)**

**Use Google OR-Tools** for proper CVRP:

```python
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def solve_cvrp(distance_matrix, demands, vehicle_capacities, depot_index):
    """
    distance_matrix: N×N matrix of distances between all points
    demands: List of waste amounts at each location
    vehicle_capacities: List of capacities per vehicle
    depot_index: Index of depot/starting point
    """
    # Create routing model
    manager = pywrapcp.RoutingIndexManager(
        len(distance_matrix), 
        len(vehicle_capacities), 
        depot_index
    )
    routing = pywrapcp.RoutingModel(manager)
    
    # Distance callback
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]
    
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    # Capacity constraint
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return demands[from_node]
    
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null capacity slack
        vehicle_capacities,  # vehicle maximum capacities
        True,  # start cumul to zero
        'Capacity'
    )
    
    # Solve
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    
    solution = routing.SolveWithParameters(search_parameters)
    
    return extract_routes(manager, routing, solution)
```

**Advantages**:
- Production-ready solver
- Handles multiple constraints (capacity, time windows, etc.)
- Globally optimal solutions
- Well-documented

**Disadvantages**:
- More complex
- Slower for very large networks
- Requires converting road network to node graph

---

### **Approach 3: Hybrid Chinese Postman + CVRP**

Combine strengths of both:

1. **Preprocessing**: Convert OSM roads to service points (nodes)
2. **Clustering**: Use k-means or hierarchical clustering considering:
   - Geographic proximity
   - Total waste in cluster
   - Road connectivity
3. **Route Planning**: Within each cluster, use Chinese Postman
4. **Optimization**: Use local search to improve cluster assignments

```python
def hybrid_approach(roads, num_vehicles, vehicle_capacity):
    # Step 1: Extract service points (nodes with waste)
    service_points = extract_service_points(roads)
    
    # Step 2: Cluster by capacity and geography
    clusters = capacity_aware_clustering(
        service_points, 
        num_vehicles, 
        vehicle_capacity
    )
    
    # Step 3: For each cluster, create Eulerian route
    routes = []
    for cluster in clusters:
        subgraph = build_subgraph(roads, cluster)
        eulerian_path = chinese_postman(subgraph)
        routes.append(eulerian_path)
    
    # Step 4: Improve with local search
    routes = improve_routes(routes, vehicle_capacity)
    
    return routes
```

---

## Recommended Implementation Roadmap

### **Immediate Next Steps (Phase 2a)**

1. **Add Waste Data Layer**
   - Add `waste_kg` field to UI for each road segment
   - Or: Auto-calculate based on road length × density factor
   - Store in database or calculate on-the-fly

2. **Add Vehicle Capacity Parameter**
   - Text input: "Vehicle Capacity (kg)"
   - Default: 2000 kg for small trucks

3. **Modify Route Planning View**
   ```python
   # In route_planning.html, add:
   - Waste density slider (kg per 100m)
   - Vehicle capacity input
   - Calculation shows:
     * Total waste to collect
     * Vehicles needed by capacity
     * Vehicles needed by time
     * Use max of both
   ```

4. **Backend Calculation**
   ```python
   def calculate_required_vehicles(total_length_m, total_waste_kg, 
                                   vehicle_capacity, time_window, speed_kmh):
       # By capacity
       vehicles_by_capacity = ceil(total_waste_kg / vehicle_capacity)
       
       # By time
       total_time = (total_length_m / 1000) / speed_kmh
       vehicles_by_time = ceil(total_time / time_window)
       
       # Need whichever is more
       return max(vehicles_by_capacity, vehicles_by_time)
   ```

### **Phase 2b: Proper CVRP (2-3 weeks)**

1. Install OR-Tools: `pip install ortools`
2. Convert road network to distance matrix
3. Implement CVRP solver
4. Visualize capacity utilization per route

### **Phase 3: Advanced Features**

- **Multiple dump sites**: Vehicles return to landfill when full
- **Time windows**: Some areas only accessible at certain times
- **Vehicle types**: Mix of small/large trucks with different capacities
- **Dynamic routing**: Real-time updates as vehicles complete routes
- **Multi-day scheduling**: Not all roads need daily collection

---

## Data Sources for Waste Generation

1. **OSM Building Footprints**
   ```python
   # Query OSM for buildings
   buildings = osmium.get_buildings(bbox)
   for building in buildings:
       if building.type == 'residential':
           waste += 2.5 * estimated_households
       elif building.type == 'commercial':
           waste += 10.0  # commercial generates more
   ```

2. **Population Density Rasters**
   - Use WorldPop or GPW datasets
   - Overlay on road network
   - Calculate waste per grid cell

3. **Census Data**
   - If available for your region
   - Most accurate but often coarse resolution

4. **Manual Survey**
   - Start with pilot area
   - Measure actual waste generation
   - Create model for rest of city

---

## UI Mockup for Phase 2

```
┌─ Route Planning ─────────────────────────────┐
│                                               │
│ 🚗 Vehicle Parameters                        │
│   Speed: [25] km/h                           │
│   Time Window: [4] hours                     │
│   Capacity: [2000] kg                        │
│                                               │
│ 🏘️ Waste Generation                          │
│   Density: [2.5] kg per household            │
│   Households per 100m: [8]                   │
│                                               │
│ 📊 Calculated Requirements                   │
│   Total Waste: 1,250 kg                      │
│   By Capacity: ⚠️ 1 vehicle                  │
│   By Time: ⚠️ 3 vehicles                     │
│   ➡️ Recommended: 3 vehicles                 │
│                                               │
│ [Compute Optimal Routes]                     │
└───────────────────────────────────────────────┘
```

---

## Example: Simple CVRP Addition to Existing Code

```python
# In routing_utils.py

def assign_waste_to_roads(self, waste_per_100m=20):
    """Assign waste generation to each road segment."""
    self.road_waste = {}
    
    for way in self.ways:
        way_length = 0
        for u, v in zip(way[:-1], way[1:]):
            if u in self.nodes and v in self.nodes:
                lat1, lon1 = self.nodes[u]
                lat2, lon2 = self.nodes[v]
                segment_length = haversine_m(lon1, lat1, lon2, lat2)
                way_length += segment_length
        
        # Assign waste based on length
        self.road_waste[tuple(way)] = (way_length / 100) * waste_per_100m
    
    return sum(self.road_waste.values())

def compute_capacity_aware_routes(self, k, vehicle_capacity):
    """Compute routes respecting vehicle capacity."""
    # ... existing Eulerian circuit code ...
    
    # Split circuit considering capacity
    segments = self.split_circuit_by_capacity(circuit_edges, k, vehicle_capacity)
    
    # ... rest of routing ...
```

Would you like me to implement Phase 2a (basic capacity parameters) first, or should we jump directly to OR-Tools CVRP implementation?
