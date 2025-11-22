# backend/algorithms.py
import heapq
import networkx as nx
from geopy.distance import geodesic

# Try to import osmnx, fallback if not available (though it should be)
try:
    import osmnx as ox
except ImportError:
    ox = None

def get_nearest_node_robust(G, lat, lon):
    """Finds nearest node safely for both Graph types."""
    if ox:
        return ox.distance.nearest_nodes(G, lon, lat)
    else:
        # Basic fallback if OSMnx isn't loaded (rare)
        # This assumes G nodes have 'x' and 'y'
        return min(G.nodes, key=lambda n: (G.nodes[n]['y'] - lat)**2 + (G.nodes[n]['x'] - lon)**2)

def haversine_heuristic(a, b):
    """Calculates the distance between two (lat, lon) points in km."""
    return geodesic(a, b).km

def astar_route(G, origin_coords, dest_coords):
    """Finds the shortest path using the A* algorithm."""
    
    origin_node = get_nearest_node_robust(G, origin_coords[0], origin_coords[1])
    destination_node = get_nearest_node_robust(G, dest_coords[0], dest_coords[1])

    pq = [(0, origin_node)]
    came_from = {origin_node: None}
    cost_so_far = {origin_node: 0}

    while pq:
        _, current = heapq.heappop(pq)

        if current == destination_node:
            break

        for neighbor in G.neighbors(current):
            # --- FIX: Robust Edge Access (DiGraph vs MultiDiGraph) ---
            if G.is_multigraph():
                # MultiDiGraph: Access first edge key (usually 0)
                edge_data = G[current][neighbor][0]
            else:
                # DiGraph: Access dict directly
                edge_data = G[current][neighbor]

            # --- FIX: Robust Weight Access ---
            # Use 'weight' (CH) or 'length' (OSM)
            length_m = edge_data.get('weight', edge_data.get('length', 1))
            edge_weight = length_m / 1000.0  # Convert to km
            
            new_cost = cost_so_far[current] + edge_weight
            
            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                
                # Heuristic
                priority = new_cost + haversine_heuristic(
                    (G.nodes[neighbor]['y'], G.nodes[neighbor]['x']),
                    dest_coords
                )
                heapq.heappush(pq, (priority, neighbor))
                came_from[neighbor] = current

    if destination_node not in came_from:
        return [], 0 # Path not found

    # Reconstruct path
    node = destination_node
    path = []
    while node is not None:
        path.append((G.nodes[node]['y'], G.nodes[node]['x']))
        node = came_from.get(node)
    path.reverse()

    distance_km = cost_so_far.get(destination_node, 0)
    return path, distance_km