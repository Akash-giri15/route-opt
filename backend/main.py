# backend/main.py
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from .graph import load_graph
from .algorithms import astar_route

app = FastAPI(title="Route Optimization Engine")

# Configure CORS to allow requests from your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"], # <-- NOW ALLOWS BOTH
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Robust File Path ---
# This creates a correct, absolute path to your map file
BASE_DIR = Path(__file__).resolve().parent.parent
GRAPH_FILE_PATH = BASE_DIR / "data" / "map_graph.graphml"

# Load the graph on startup
G = load_graph(GRAPH_FILE_PATH)

@app.get("/route")
def get_route(origin: str = Query(...), destination: str = Query(...)):
    """
    Calculates the shortest route between an origin and destination.
    Expects queries like: ?origin=12.9716,77.5946&destination=12.9352,77.6245
    """
    o_lat, o_lon = map(float, origin.split(","))
    d_lat, d_lon = map(float, destination.split(","))

    path, distance_km = astar_route(G, (o_lat, o_lon), (d_lat, d_lon))

    return {
        "path": path,
        "distance_km": round(distance_km, 2)
    }