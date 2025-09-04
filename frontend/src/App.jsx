// src/App.jsx
import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Polyline, useMap } from 'react-leaflet';
import axios from 'axios';
import 'leaflet/dist/leaflet.css';

// --- NEW HELPER COMPONENT ---
// This component will adjust the map view to fit the route
function ChangeView({ route }) {
  const map = useMap();
  useEffect(() => {
    if (route && route.length > 0) {
      // fitBounds is a Leaflet method to adjust the map's view
      map.fitBounds(route);
    }
  }, [route, map]); // Rerun this effect when the route or map instance changes
  return null; // This component doesn't render anything itself
}


export default function App() {
  const [route, setRoute] = useState([]);
  const [loading, setLoading] = useState(false);
  const [distance, setDistance] = useState(null); // <-- NEW: State for distance

  const fetchRoute = async () => {
    setLoading(true);
    setRoute([]);
    setDistance(null); // <-- NEW: Clear previous distance
    try {
      const origin = "12.9716,77.5946";
      const destination = "12.9352,77.6245";
      const res = await axios.get(`http://localhost:8000/route?origin=${origin}&destination=${destination}`);
      
      setRoute(res.data.path);
      setDistance(res.data.distance_km); // <-- NEW: Set the distance from the API response
    } catch (error) {
      console.error("Failed to fetch route:", error);
      alert("Could not fetch the route. Check the console for errors.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative w-full h-screen">
      <div className="absolute top-4 left-4 z-[1000] flex flex-col gap-4">
        <button
          onClick={fetchRoute}
          disabled={loading}
          className="p-3 bg-blue-600 text-white font-bold rounded-lg shadow-lg hover:bg-blue-700 disabled:bg-gray-400"
        >
          {loading ? 'Calculating...' : 'Calculate Route in Bengaluru'}
        </button>
        
        {/* --- NEW: Display Distance --- */}
        {distance && (
          <div className="p-3 bg-white text-black font-bold rounded-lg shadow-lg">
            <p>Distance: {distance} km</p>
          </div>
        )}
      </div>

      <MapContainer center={[12.97, 77.59]} zoom={12} style={{ height: "100%", width: "100%" }}>
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        
        {/* The Polyline component draws the red line on the map */}
        {route.length > 0 && <Polyline positions={route} color="red" weight={5} />}
        
        {/* --- NEW: Add the ChangeView component --- */}
        <ChangeView route={route} />
      </MapContainer>
    </div>
  );
}