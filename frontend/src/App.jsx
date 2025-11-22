// src/App.jsx
import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap, useMapEvents } from 'react-leaflet';
import axios from 'axios';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

function LocationSelector({ setOrigin, setDestination, origin, destination }) {
  useMapEvents({
    click(e) {
      const { lat, lng } = e.latlng;
      if (!origin) {
        setOrigin({ lat, lng });
      } else if (!destination) {
        setDestination({ lat, lng });
      }
    },
  });
  return null;
}

function ChangeView({ bounds }) {
  const map = useMap();
  useEffect(() => {
    if (bounds && bounds.length > 0) {
      map.fitBounds(bounds);
    }
  }, [bounds, map]);
  return null;
}

export default function App() {
  const [origin, setOrigin] = useState(null);
  const [destination, setDestination] = useState(null);
  const [route, setRoute] = useState([]);
  const [distance, setDistance] = useState(null);
  const [loading, setLoading] = useState(false);
  const [benchmarking, setBenchmarking] = useState(false); // NEW
  const [stats, setStats] = useState(null); // NEW
  const [error, setError] = useState(null);

  const handleReset = () => {
    setOrigin(null);
    setDestination(null);
    setRoute([]);
    setDistance(null);
    setStats(null);
    setError(null);
  };

  const fetchRoute = async () => {
    if (!origin || !destination) return;
    setLoading(true);
    setStats(null); // Clear old stats
    try {
      const originStr = `${origin.lat},${origin.lng}`;
      const destStr = `${destination.lat},${destination.lng}`;
      const res = await axios.get(`http://localhost:8000/route`, {
        params: { origin: originStr, destination: destStr }
      });
      setRoute(res.data.path);
      setDistance(res.data.distance_km);
    } catch (err) {
      console.error(err);
      setError("Failed to fetch route.");
    } finally {
      setLoading(false);
    }
  };

  // --- NEW FUNCTION: Run Benchmark ---
  const runBenchmark = async () => {
    if (!origin || !destination) return;
    setBenchmarking(true);
    try {
      const originStr = `${origin.lat},${origin.lng}`;
      const destStr = `${destination.lat},${destination.lng}`;
      
      // Call the new compare endpoint
      const res = await axios.get(`http://localhost:8000/compare`, {
        params: { origin: originStr, destination: destStr }
      });
      
      setStats(res.data);
    } catch (err) {
      console.error(err);
      setError("Benchmark failed.");
    } finally {
      setBenchmarking(false);
    }
  };

  return (
    <div className="flex h-screen w-full flex-col md:flex-row font-sans">
      
      {/* Sidebar */}
      <div className="w-full md:w-1/3 lg:w-1/4 bg-gray-900 text-white p-6 flex flex-col gap-4 shadow-2xl z-20 overflow-y-auto">
        <div>
          <h1 className="text-2xl font-bold text-blue-400">Route Opt Engine</h1>
          <p className="text-gray-400 text-xs mt-1">Resume Project • Contraction Hierarchies</p>
        </div>

        {/* Selection Status */}
        <div className="space-y-2">
            <div className={`p-3 rounded text-sm border ${origin ? 'border-green-500 bg-green-900/20' : 'border-gray-700'}`}>
                <span className="font-bold text-green-400">START</span>
                <div className="text-xs text-gray-300 font-mono mt-1">
                    {origin ? `${origin.lat.toFixed(4)}, ${origin.lng.toFixed(4)}` : 'Select on map'}
                </div>
            </div>
            <div className={`p-3 rounded text-sm border ${destination ? 'border-red-500 bg-red-900/20' : 'border-gray-700'}`}>
                <span className="font-bold text-red-400">DESTINATION</span>
                <div className="text-xs text-gray-300 font-mono mt-1">
                    {destination ? `${destination.lat.toFixed(4)}, ${destination.lng.toFixed(4)}` : 'Select on map'}
                </div>
            </div>
        </div>

        {/* Main Actions */}
        <div className="flex flex-col gap-2">
            <button
                onClick={fetchRoute}
                disabled={!origin || !destination || loading}
                className="py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 rounded font-bold transition-colors shadow-lg"
            >
                {loading ? 'Calculating...' : 'Find Best Route'}
            </button>
            
            {/* --- NEW: Compare Button --- */}
            <button
                onClick={runBenchmark}
                disabled={!origin || !destination || benchmarking}
                className="py-3 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 rounded font-bold transition-colors shadow-lg"
            >
                {benchmarking ? 'Running Benchmark...' : '⚔️ Compare A* vs CH'}
            </button>

            <button onClick={handleReset} className="py-2 border border-gray-600 text-gray-400 hover:bg-gray-800 rounded text-sm">
                Reset
            </button>
        </div>

        {/* Errors */}
        {error && <div className="text-red-400 text-xs bg-red-900/20 p-2 rounded border border-red-900">{error}</div>}
        
        {/* Distance Result */}
        {distance && !stats && (
             <div className="mt-2 p-4 bg-gray-800 rounded border border-gray-700 text-center animate-fade-in">
                <span className="text-gray-400 text-xs uppercase tracking-wider">Total Distance</span>
                <div className="text-3xl font-bold text-white">{distance} <span className="text-lg text-gray-500">km</span></div>
             </div>
        )}

        {/* --- NEW: Comparison Results Card --- */}
        {stats && (
            <div className="mt-2 p-4 bg-gray-800 rounded border border-purple-500/50 animate-fade-in">
                <h3 className="text-purple-400 font-bold text-center mb-3 text-sm uppercase tracking-widest">Performance Benchmark</h3>
                
                <div className="grid grid-cols-2 gap-2 mb-4">
                    <div className="bg-gray-900 p-2 rounded text-center">
                        <div className="text-gray-500 text-xs">Standard A*</div>
                        <div className="text-lg font-mono text-red-400">{stats.astar.time} ms</div>
                    </div>
                    <div className="bg-gray-900 p-2 rounded text-center border border-green-500/30">
                        <div className="text-green-400 text-xs font-bold">Your CH Engine</div>
                        <div className="text-lg font-mono text-green-400">{stats.ch.time} ms</div>
                    </div>
                </div>

                <div className="bg-green-900/30 p-3 rounded text-center border border-green-500">
                    <div className="text-gray-300 text-xs uppercase">Speed Improvement</div>
                    <div className="text-2xl font-black text-white">
                        {stats.speedup}x <span className="text-sm font-normal text-green-400">FASTER</span>
                    </div>
                </div>
            </div>
        )}
      </div>

      {/* Map */}
      <div className="flex-1 relative z-10">
        <MapContainer center={[12.9716, 77.5946]} zoom={12} style={{ height: "100%", width: "100%" }}>
          <TileLayer 
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" 
            attribution='&copy; OpenStreetMap &copy; CARTO'
          />
          <LocationSelector setOrigin={setOrigin} setDestination={setDestination} origin={origin} destination={destination} />
          {origin && <Marker position={[origin.lat, origin.lng]}><Popup>Start</Popup></Marker>}
          {destination && <Marker position={[destination.lat, destination.lng]}><Popup>Destination</Popup></Marker>}
          {route.length > 0 && <Polyline positions={route} color="#4ade80" weight={6} opacity={0.8} />}
          <ChangeView bounds={route.length > 0 ? route : null} />
        </MapContainer>
      </div>
    </div>
  );
}