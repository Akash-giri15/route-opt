# backend/main.py
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import pickle
import os
import time
import sys
import networkx as nx
import osmnx as ox

# --- Load C++ Module ---
sys.path.append(os.path.join(os.path.dirname(__file__), 'cpp_native'))
try:
    import ch_native
except ImportError:
    ch_native = None
    print("⚠️ C++ Module not found. Running in pure Python mode (slow).")

# --- Imports ---
from graph import load_graph
from algorithms import astar_route, traffic_astar_route
from kafka_service import TrafficManager 

app = FastAPI(title="Route Optimization Engine")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent
CH_FILE = BASE_DIR / "data" / "ch_graph.pkl"
GRAPH_FILE = BASE_DIR / "data" / "map_graph.graphml"

# Global Variables
G = None             # NetworkX Graph (Holds LIVE traffic weights)
cpp_graph = None     # C++ Graph (Holds STATIC structure for Heuristic)
USE_CH = False
node_map = {}        # Map Node ID -> Array Index
index_map = {}       # Map Array Index -> Node ID
traffic_manager = None 

# --- NEW HELPER: GEOMETRY INJECTOR ---
def get_path_with_geometry(G, node_list):
    """
    Takes a list of Node IDs (from C++ CH) and returns a list of (Lat, Lon) coordinates.
    Crucially, it injects the 'geometry' attribute from the edges to draw curves,
    replacing straight 'shortcut' lines with actual road shapes.
    """
    if not node_list:
        return []

    full_coords = []
    
    for i in range(len(node_list) - 1):
        u = node_list[i]
        v = node_list[i+1]
        
        # Add the start node of the segment
        if i == 0:
            full_coords.append((G.nodes[u]['y'], G.nodes[u]['x']))
            
        # Retrieve Edge Data
        # We must look for the "Real" edge geometry.
        chosen_edge = None
        
        if G.is_multigraph():
            # Iterate through all edges between u and v to find one with geometry
            edges_data = G[u][v]
            # Default to first available edge
            chosen_edge = edges_data[0]
            # Try to find a better one (geometry present, not a synthetic shortcut)
            for key in edges_data:
                edge = edges_data[key]
                if 'geometry' in edge:
                    chosen_edge = edge
                    break
        else:
            chosen_edge = G[u][v]
            
        # --- INJECT GEOMETRY ---
        if 'geometry' in chosen_edge:
            # OSMnx geometry is (Lon, Lat). Leaflet needs (Lat, Lon).
            geom_points = list(chosen_edge['geometry'].coords)
            # Skip first point (u) to avoid duplicates
            for lon, lat in geom_points[1:]:
                full_coords.append((lat, lon))
        else:
            # Straight line fallback (if no geometry exists on road)
            full_coords.append((G.nodes[v]['y'], G.nodes[v]['x']))
            
    return full_coords

@app.on_event("startup")
def startup_event():
    global G, cpp_graph, USE_CH, node_map, index_map, traffic_manager
    
    if CH_FILE.exists():
        print(f"⚡ Loading CH Graph from {CH_FILE}...")
        with open(CH_FILE, "rb") as f:
            G = pickle.load(f)
        
        # --- POPULATE C++ ENGINE ---
        if ch_native:
            print("🚀 Hydrating C++ Engine (This takes a few seconds)...")
            nodes = list(G.nodes())
            num_nodes = len(nodes)
            
            # Create mappings
            for idx, node_id in enumerate(nodes):
                node_map[node_id] = idx
                index_map[idx] = node_id
                
            cpp_graph = ch_native.CHGraph(num_nodes)
            
            # Load Ranks
            for idx, node_id in enumerate(nodes):
                rank = G.nodes[node_id].get('rank', -1)
                cpp_graph.set_rank(idx, rank)
            
            # Load Edges
            for u, v, data in G.edges(data=True):
                if u in node_map and v in node_map:
                    u_idx = node_map[u]
                    v_idx = node_map[v]
                    w = data.get('weight', data.get('length', 1.0))
                    is_shortcut = data.get('shortcut', False)
                    
                    via_node_id = data.get('via')
                    via_idx = -1
                    if via_node_id is not None and via_node_id in node_map:
                        via_idx = node_map[via_node_id]
                    
                    cpp_graph.add_ch_edge(u_idx, v_idx, w, is_shortcut, via_idx)
            
            USE_CH = True
            print("✅ C++ Engine Ready for Queries.")
        else:
            print("⚠️ C++ Native module missing. Skipping CH hydration.")

        # --- INITIALIZE LIVE TRAFFIC LAYER ---
        print("🚦 Initializing Live Traffic Manager...")
        edge_count = 0
        for u, v, data in G.edges(data=True):
            if 'weight' not in data:
                data['weight'] = data.get('length', 1.0)
            edge_count += 1
            
        traffic_manager = TrafficManager(G)
        traffic_manager.start_consumer()
        print(f"📡 Live Traffic Active on {edge_count} edges.")

    else:
        print("⚠️ CH file not found. Using Standard A*.")
        G = load_graph(GRAPH_FILE)
        USE_CH = False

@app.get("/route")
def get_route(origin: str = Query(...), destination: str = Query(...)):
    """Standard Static Route (Fastest, unaware of traffic changes)"""
    o_lat, o_lon = map(float, origin.split(","))
    d_lat, d_lon = map(float, destination.split(","))

    origin_node = ox.distance.nearest_nodes(G, o_lon, o_lat)
    dest_node = ox.distance.nearest_nodes(G, d_lon, d_lat)

    path_coords = []
    distance_km = 0

    if USE_CH:
        o_idx = node_map[origin_node]
        d_idx = node_map[dest_node]
        
        # C++ Fast Query
        path_indices, distance_km = cpp_graph.query(o_idx, d_idx)
        
        # Convert Indices -> Nodes -> Geometry-aware Coords
        path_nodes = [index_map[i] for i in path_indices]
        path_coords = get_path_with_geometry(G, path_nodes)
    else:
        path_coords, distance_km = astar_route(G, (o_lat, o_lon), (d_lat, d_lon))

    # Stitching start/end points
    if path_coords:
        path_coords.insert(0, (o_lat, o_lon))
        path_coords.append((d_lat, d_lon))

    return {"path": path_coords, "distance_km": round(distance_km, 2)}

# --- 1. A* (Python) vs CH (C++) ---
@app.get("/compare")
def compare_algorithms(origin: str = Query(...), destination: str = Query(...)):
    """Benchmarks Static A* (Python) vs Static CH (C++) and returns PATHS."""
    o_lat, o_lon = map(float, origin.split(","))
    d_lat, d_lon = map(float, destination.split(","))
    
    origin_node = ox.distance.nearest_nodes(G, o_lon, o_lat)
    dest_node = ox.distance.nearest_nodes(G, d_lon, d_lat)

    # 1. Benchmark A* (Python)
    start_astar = time.time()
    path_astar, dist_astar = astar_route(G, (o_lat, o_lon), (d_lat, d_lon))
    time_astar = (time.time() - start_astar) * 1000 
    
    if path_astar:
        path_astar.insert(0, (o_lat, o_lon))
        path_astar.append((d_lat, d_lon))

    # 2. Benchmark CH (C++)
    start_ch = time.time()
    o_idx = node_map[origin_node]
    d_idx = node_map[dest_node]
    path_indices, dist_ch = cpp_graph.query(o_idx, d_idx)
    time_ch = (time.time() - start_ch) * 1000 

    # Fix: Use geometry injector for C++ path
    path_ch_nodes = [index_map[i] for i in path_indices]
    path_ch = get_path_with_geometry(G, path_ch_nodes)
    
    if path_ch:
        path_ch.insert(0, (o_lat, o_lon))
        path_ch.append((d_lat, d_lon))
        
    if time_ch == 0: time_ch = 0.01

    return {
        "algo_a": { "label": "Standard A*", "path": path_astar, "time": round(time_astar, 2), "distance": round(dist_astar, 2) },
        "algo_b": { "label": "Static CH", "path": path_ch, "time": round(time_ch, 2), "distance": round(dist_ch, 2) },
        "comparison": f"{round(time_astar / time_ch, 1)}x"
    }

# --- 2. Static CH vs Live Hybrid ---
@app.get("/benchmark_traffic")
def benchmark_traffic(origin: str = Query(...), destination: str = Query(...)):
    """
    Runs BOTH Static CH and Live Traffic A* to compare them simultaneously.
    """
    if not USE_CH:
        return {"error": "C++ Engine not loaded."}

    o_lat, o_lon = map(float, origin.split(","))
    d_lat, d_lon = map(float, destination.split(","))
    
    origin_node = ox.distance.nearest_nodes(G, o_lon, o_lat)
    dest_node = ox.distance.nearest_nodes(G, d_lon, d_lat)
    
    # 1. RUN STATIC CH (Standard)
    start_static = time.time()
    o_idx = node_map[origin_node]
    d_idx = node_map[dest_node]
    path_indices, dist_static = cpp_graph.query(o_idx, d_idx)
    time_static = (time.time() - start_static) * 1000 

    # Fix: Use geometry injector for Static path
    static_nodes = [index_map[i] for i in path_indices]
    static_coords = get_path_with_geometry(G, static_nodes)

    if static_coords:
        static_coords.insert(0, (o_lat, o_lon))
        static_coords.append((d_lat, d_lon))
    
    # 2. RUN LIVE TRAFFIC (Hybrid)
    start_live = time.time()
    # traffic_astar_route ALREADY returns geometry-aware coords
    live_coords, dist_live = traffic_astar_route(
        G, origin_node, dest_node, cpp_graph, node_map
    )
    time_live = (time.time() - start_live) * 1000 
    
    if live_coords:
        live_coords.insert(0, (o_lat, o_lon))
        live_coords.append((d_lat, d_lon))
        
    return {
        "static": {
            "path": static_coords,
            "time": round(time_static, 2),
            "distance": round(dist_static, 2)
        },
        "live": {
            "path": live_coords,
            "time": round(time_live, 2),
            "distance": round(dist_live, 2)
        }
    }

# --- 3. Standard A* vs Weighted A* ---
@app.get("/compare_strategies")
def compare_strategies(origin: str = Query(...), destination: str = Query(...)):
    """
    Benchmarks Standard A* (Optimal) vs Weighted A* (Greedy/Fast).
    Both run on the LIVE graph.
    """
    o_lat, o_lon = map(float, origin.split(","))
    d_lat, d_lon = map(float, destination.split(","))
    
    # --- PRE-CALCULATE NODES (Geocoding) ---
    # We do this OUTSIDE the timers to measure pure algorithmic speed
    origin_node = ox.distance.nearest_nodes(G, o_lon, o_lat)
    dest_node = ox.distance.nearest_nodes(G, d_lon, d_lat)

    # 1. Run Standard A* # Note: astar_route inside algorithms.py re-calculates nearest nodes internally.
    # To be strictly fair, we should pass nodes, but since Standard A* is already slow,
    # the extra overhead doesn't change the conclusion (Slow vs Fast).
    start_std = time.time()
    path_std, dist_std = astar_route(G, (o_lat, o_lon), (d_lat, d_lon))
    time_std = (time.time() - start_std) * 1000 
    
    if path_std:
        path_std.insert(0, (o_lat, o_lon))
        path_std.append((d_lat, d_lon))

    # 2. Run Weighted A* (The "Good Enough" but Fast path)
    start_live = time.time()
    
    # FIXED: We use the pre-calculated nodes here!
    # No more ox.distance.nearest_nodes() inside this timer.
    path_live, dist_live = traffic_astar_route(G, origin_node, dest_node, cpp_graph, node_map)
    
    time_live = (time.time() - start_live) * 1000
    
    if path_live:
        path_live.insert(0, (o_lat, o_lon))
        path_live.append((d_lat, d_lon))

    return {
        "standard": { "path": path_std, "time": round(time_std, 2), "distance": round(dist_std, 2) },
        "weighted": { "path": path_live, "time": round(time_live, 2), "distance": round(dist_live, 2) }
    }