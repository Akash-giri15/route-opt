# backend/algorithms.py
import heapq
from geopy.distance import geodesic
from .graph import get_nearest_node

def haversine_heuristic(a, b):
    """Calculates the distance between two (lat, lon) points in km."""
    return geodesic(a, b).km

def astar_route(G, origin_coords, dest_coords):
    """Finds the shortest path using the A* algorithm."""
    origin_node = get_nearest_node(G, *origin_coords)
    destination_node = get_nearest_node(G, *dest_coords)

    pq = [(0, origin_node)]
    came_from = {origin_node: None}
    cost_so_far = {origin_node: 0}

    while pq:
        _, current = heapq.heappop(pq)
        if current == destination_node:
            break
        for neighbor in G.neighbors(current):
            edge_data = G[current][neighbor][0]
            edge_weight = edge_data.get('length', 1) / 1000  # Convert to km
            new_cost = cost_so_far[current] + edge_weight
            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
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