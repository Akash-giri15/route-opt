# backend/algorithms.py
import heapq
import math
import networkx as nx

try:
    import osmnx as ox
except ImportError:
    ox = None

def get_nearest_node_robust(G, lat, lon):
    if ox:
        return ox.distance.nearest_nodes(G, lon, lat)
    return min(G.nodes, key=lambda n: (G.nodes[n]['y'] - lat)**2 + (G.nodes[n]['x'] - lon)**2)

def haversine_heuristic(node_coords, dest_coords):
    """Fast Math-only Haversine (km)."""
    lat1, lon1 = node_coords
    lat2, lon2 = dest_coords
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def reconstruct_path(came_from, dest_id, G):
    node_path = []
    curr = dest_id
    while curr is not None:
        node_path.append(curr)
        curr = came_from.get(curr)
    node_path.reverse()

    if not node_path: return []

    full_coords = []
    for i in range(len(node_path) - 1):
        u = node_path[i]
        v = node_path[i+1]
        
        if i == 0:
            full_coords.append((G.nodes[u]['y'], G.nodes[u]['x']))
        
        if G.is_multigraph():
            edge = G[u][v][0]
        else:
            edge = G[u][v]
            
        if 'geometry' in edge:
            geom_points = list(edge['geometry'].coords)
            for lon, lat in geom_points[1:]:
                full_coords.append((lat, lon))
        else:
            full_coords.append((G.nodes[v]['y'], G.nodes[v]['x']))
            
    return full_coords

def astar_route(G, origin_coords, dest_coords):
    """Standard Static A*."""
    origin_node = get_nearest_node_robust(G, origin_coords[0], origin_coords[1])
    destination_node = get_nearest_node_robust(G, dest_coords[0], dest_coords[1])

    pq = [(0, origin_node)]
    came_from = {origin_node: None}
    cost_so_far = {origin_node: 0}
    dest_lat = G.nodes[destination_node]['y']
    dest_lon = G.nodes[destination_node]['x']

    while pq:
        _, current = heapq.heappop(pq)
        if current == destination_node: break

        for neighbor in G.neighbors(current):
            edge = G[current][neighbor][0] if G.is_multigraph() else G[current][neighbor]
            
            # --- FIX: Ignore Shortcuts in Python Traversal ---
            if edge.get('shortcut'): continue 
            
            w = edge.get('weight', edge.get('length', 1.0)) / 1000.0
            new_cost = cost_so_far[current] + w
            
            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                h = haversine_heuristic((G.nodes[neighbor]['y'], G.nodes[neighbor]['x']), (dest_lat, dest_lon))
                heapq.heappush(pq, (new_cost + h, neighbor))
                came_from[neighbor] = current

    if destination_node not in came_from: return [], 0
    return reconstruct_path(came_from, destination_node, G), cost_so_far[destination_node]

def traffic_astar_route(G, origin_id, dest_id, ch_engine, node_map):
    """
    Weighted A* (Greedy) that IGNORES shortcuts to ensure geometry is correct.
    """
    if dest_id not in node_map: return [], 0
    
    dest_coords = (G.nodes[dest_id]['y'], G.nodes[dest_id]['x'])
    
    # Epsilon 2.0 balances Speed vs Accuracy perfectly.
    epsilon = 2.0 

    pq = [(0, origin_id)]
    came_from = {origin_id: None}
    cost_so_far = {origin_id: 0}

    while pq:
        _, current = heapq.heappop(pq)
        if current == dest_id: break

        for neighbor in G.neighbors(current):
            edge = G[current][neighbor][0] if G.is_multigraph() else G[current][neighbor]
            
            # --- THE CRITICAL FIX: SKIP SHORTCUTS ---
            # Shortcuts have no geometry. We must force the path onto real roads.
            if edge.get('shortcut'): continue

            w = edge.get('weight', edge.get('length', 1.0)) / 1000.0
            new_cost = cost_so_far[current] + w

            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                h = haversine_heuristic((G.nodes[neighbor]['y'], G.nodes[neighbor]['x']), dest_coords)
                
                # Greedy Search
                priority = new_cost + (epsilon * h)
                heapq.heappush(pq, (priority, neighbor))
                came_from[neighbor] = current

    if dest_id not in came_from: return [], 0
    return reconstruct_path(came_from, dest_id, G), cost_so_far[dest_id]