# download_map.py
import osmnx as ox

# Define the place and network type
place_name = "Bengaluru, Karnataka, India"
network_type = "drive" # Can be 'drive', 'walk', 'bike', etc.

print(f"Downloading map data for {place_name}...")

# Download the graph data from OpenStreetMap
G = ox.graph_from_place(place_name, network_type=network_type)

# Save the graph to a file in the 'data' directory
filepath = "data/map_graph.graphml"
ox.save_graphml(G, filepath)

print(f"✅ Graph successfully saved to {filepath}")