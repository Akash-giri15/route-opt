# backend/preprocess_map.py
import sys
import os
from pathlib import Path

# --- Configuration to find C++ Module ---
# This ensures Python looks inside the 'cpp_native' folder for the compiled extension
sys.path.append(os.path.join(os.path.dirname(__file__), 'cpp_native'))

try:
    import ch_native
except ImportError as e:
    print(f"CRITICAL ERROR: Could not import 'ch_native'. Make sure you compiled the C++ code.")
    print(f"Run 'python setup.py build_ext --inplace' inside backend/cpp_native/")
    sys.exit(1)

import osmnx as ox
import networkx as nx
import pickle

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_GRAPH = BASE_DIR / "data" / "map_graph.graphml"
OUTPUT_CH = BASE_DIR / "data" / "ch_graph.pkl"

def preprocess():
    print(f"Loading raw graph from {INPUT_GRAPH}...")
    
    if not INPUT_GRAPH.exists():
        print(f"Error: {INPUT_GRAPH} not found. Run download_map.py first.")
        return

    # 1. Load and Standardize Graph
    G_raw = ox.load_graphml(INPUT_GRAPH)
    
    # Handle OSMnx version differences (v2.0+ vs older)
    try:
        G = ox.convert.to_digraph(G_raw, weight='length')
    except AttributeError:
        G = ox.utils_graph.get_digraph(G_raw, weight='length')

    # 2. Prepare Data for C++
    print("Preparing graph data for C++ engine...")
    node_list = list(G.nodes())
    node_to_idx = {node: i for i, node in enumerate(node_list)}
    idx_to_node = {i: node for i, node in enumerate(node_list)}
    
    # Initialize C++ Graph
    cpp_graph = ch_native.CHGraph(len(node_list))
    
    # Transfer Edges
    for u, v, data in G.edges(data=True):
        u_idx = node_to_idx[u]
        v_idx = node_to_idx[v]
        # Default weight to 1.0 if missing, ensure float
        w = float(data.get('weight', data.get('length', 1.0)))
        cpp_graph.add_edge(u_idx, v_idx, w)

    # 3. Calculate Node Importance (Heuristic)
    print("Sorting nodes by importance (Degree Heuristic)...")
    # Sort by degree (contract simple nodes first, keep hubs for last)
    nodes_sorted = sorted(node_list, key=lambda n: G.degree(n))
    order_indices = [node_to_idx[n] for n in nodes_sorted]

    # 4. Run Contraction Hierarchies (C++)
    print("🚀 Running Contraction Hierarchies (C++ Accelerator)...")
    cpp_graph.build_ch(order_indices)

    # 5. Retrieve & Save Results
    print("Retrieving optimized graph data...")
    data = cpp_graph.get_graph_data()
    
    ranks = data["ranks"]
    edges = data["edges"]
    
    # Update Graph with Ranks
    for i, r in enumerate(ranks):
        G.nodes[idx_to_node[i]]['rank'] = r
        
    # Add Shortcuts to Graph
    shortcut_count = 0
    for u_idx, v_idx, w, is_shortcut, via_idx in edges:
        if is_shortcut:
            u = idx_to_node[u_idx]
            v = idx_to_node[v_idx]
            # Map the 'via' index back to the real OSM Node ID
            via_node = idx_to_node[via_idx] if via_idx != -1 else None
            
            G.add_edge(u, v, weight=w, shortcut=True, via=via_node)
            shortcut_count += 1
            
    print(f"✅ Optimization Complete. Added {shortcut_count} shortcuts.")
    
    print(f"Saving CH graph to {OUTPUT_CH}...")
    with open(OUTPUT_CH, "wb") as f:
        pickle.dump(G, f)
    
    print("Done! Backend is ready.")

if __name__ == "__main__":
    preprocess()