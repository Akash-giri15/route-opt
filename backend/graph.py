# backend/graph.py
import osmnx as ox

def load_graph(filepath: str):
    """Loads a graph from a .graphml file."""
    return ox.load_graphml(filepath)

def get_nearest_node(G, lat, lon):
    """Finds the nearest network node to a given lat/lon point."""
    return ox.distance.nearest_nodes(G, lon, lat)