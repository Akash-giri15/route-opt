# backend/main.py
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import pickle
import os
import time
import sys

# --- Load C++ Module ---
sys.path.append(os.path.join(os.path.dirname(__file__), 'cpp_native'))
import ch_native

import networkx as nx
import osmnx as ox
from algorithms import astar_route
from graph import load_graph

app = FastAPI(title="Route Optimization Engine")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent
CH_FILE = BASE_DIR / "data" / "ch_graph.pkl"
GRAPH_FILE = BASE_DIR / "data" / "map_graph.graphml"

# Global Variables
G = None      # NetworkX Graph (for Geocoding / A*)
cpp_graph = None # C++ Graph (for High Speed CH)
USE_CH = False
node_map = {} # Map Node ID -> Array Index
index_map = {} # Map Array Index -> Node ID

@app.on_event("startup")
def startup_event():
    global G, cpp_graph, USE_CH, node_map, index_map
    
    if CH_FILE.exists():
        print(f"⚡ Loading CH Graph from {CH_FILE}...")
        with open(CH_FILE, "rb") as f:
            G = pickle.load(f)
        
        # --- POPULATE C++ ENGINE ---
        print("🚀 Hydrating C++ Engine (This takes a few seconds)...")
        nodes = list(G.nodes())
        num_nodes = len(nodes)
        
        # Create mappings (NetworkX IDs are large ints, C++ needs 0..N indices)
        for idx, node_id in enumerate(nodes):
            node_map[node_id] = idx
            index_map[idx] = node_id
            
        cpp_graph = ch_native.CHGraph(num_nodes)
        
        # Load Ranks and Edges into C++
        for idx, node_id in enumerate(nodes):
            rank = G.nodes[node_id].get('rank', -1)
            cpp_graph.set_rank(idx, rank)
            
        for u, v, data in G.edges(data=True):
            if u in node_map and v in node_map:
                u_idx = node_map[u]
                v_idx = node_map[v]
                w = data.get('weight', data.get('length', 1.0))
                is_shortcut = data.get('shortcut', False)
                
                # Safe mapping for 'via'
                via_node_id = data.get('via')
                via_idx = -1
                if via_node_id is not None and via_node_id in node_map:
                    via_idx = node_map[via_node_id]
                
                cpp_graph.add_ch_edge(u_idx, v_idx, w, is_shortcut, via_idx)
        
        USE_CH = True
        print("✅ C++ Engine Ready for Queries.")
    else:
        print("⚠️ CH file not found. Using Standard A*.")
        G = load_graph(GRAPH_FILE)
        USE_CH = False

@app.get("/route")
def get_route(origin: str = Query(...), destination: str = Query(...)):
    o_lat, o_lon = map(float, origin.split(","))
    d_lat, d_lon = map(float, destination.split(","))

    # 1. Geocode (Find nearest node IDs)
    # Standard NetworkX is fine here, it's fast enough for just 2 lookups
    origin_node = ox.distance.nearest_nodes(G, o_lon, o_lat)
    dest_node = ox.distance.nearest_nodes(G, d_lon, d_lat)

    path_coords = []
    distance_km = 0

    if USE_CH:
        # 2. QUERY C++ ENGINE
        o_idx = node_map[origin_node]
        d_idx = node_map[dest_node]
        
        # This call is now INSTANT (C++)
        path_indices, distance_km = cpp_graph.query(o_idx, d_idx)
        
        # Convert Indices back to Lat/Lon
        path_coords = [(G.nodes[index_map[i]]['y'], G.nodes[index_map[i]]['x']) for i in path_indices]
    else:
        path_coords, distance_km = astar_route(G, (o_lat, o_lon), (d_lat, d_lon))

    # Stitching
    if path_coords:
        path_coords.insert(0, (o_lat, o_lon))
        path_coords.append((d_lat, d_lon))

    return {"path": path_coords, "distance_km": round(distance_km, 2)}

@app.get("/compare")
def compare_algorithms(origin: str = Query(...), destination: str = Query(...)):
    o_lat, o_lon = map(float, origin.split(","))
    d_lat, d_lon = map(float, destination.split(","))
    
    origin_node = ox.distance.nearest_nodes(G, o_lon, o_lat)
    dest_node = ox.distance.nearest_nodes(G, d_lon, d_lat)

    # Benchmark A* (Python)
    start_astar = time.time()
    _, dist_astar = astar_route(G, (o_lat, o_lon), (d_lat, d_lon))
    time_astar = (time.time() - start_astar) * 1000 

    # Benchmark CH (C++)
    start_ch = time.time()
    o_idx = node_map[origin_node]
    d_idx = node_map[dest_node]
    _, dist_ch = cpp_graph.query(o_idx, d_idx)
    time_ch = (time.time() - start_ch) * 1000 

    if time_ch == 0: time_ch = 0.01

    return {
        "astar": { "time": round(time_astar, 2), "distance": round(dist_astar, 2) },
        "ch": { "time": round(time_ch, 2), "distance": round(dist_ch, 2) },
        "speedup": round(time_astar / time_ch, 1)
    }