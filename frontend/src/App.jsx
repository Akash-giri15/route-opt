import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap, useMapEvents } from 'react-leaflet';
import axios from 'axios';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({ iconUrl: icon, shadowUrl: iconShadow, iconSize: [25, 41], iconAnchor: [12, 41] });
L.Marker.prototype.options.icon = DefaultIcon;

// --- UTILITY COMPONENTS ---
function LocationSelector({ setOrigin, setDestination, origin, destination }) {
  useMapEvents({
    click(e) {
      const { lat, lng } = e.latlng;
      if (!origin) setOrigin({ lat, lng });
      else if (!destination) setDestination({ lat, lng });
    },
  });
  return null;
}

function ChangeView({ bounds }) {
  const map = useMap();
  useEffect(() => {
    if (bounds && bounds.length > 0) map.fitBounds(bounds);
  }, [bounds, map]);
  return null;
}

// --- MAIN COMPONENT ---
export default function App() {
  const [origin, setOrigin] = useState(null);
  const [destination, setDestination] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Unified State for Comparison
  const [comparison, setComparison] = useState(null);
  // Structure: { 
  //   type: 'ALGO' | 'TRAFFIC' | 'STRATEGY',
  //   dataA: { label, time, distance, path, color },
  //   dataB: { label, time, distance, path, color },
  //   tagline: "100x Faster"
  // }

  const handleReset = () => {
    setOrigin(null); setDestination(null);
    setComparison(null); setError(null);
  };

  const runBenchmark = async (type) => {
    if (!origin || !destination) return;
    setLoading(true); setComparison(null); setError(null);
    
    const params = { origin: `${origin.lat},${origin.lng}`, destination: `${destination.lat},${destination.lng}` };
    
    try {
      let res;
      let data = {};

      if (type === 'ALGO') {
        res = await axios.get(`http://localhost:8000/compare`, { params });
        data = {
            type: 'ALGO',
            tagline: `${res.data.comparison} SPEEDUP`,
            dataA: { ...res.data.algo_a, color: "#ef4444" }, // Red
            dataB: { ...res.data.algo_b, color: "#22c55e" }  // Green
        };
      } 
      else if (type === 'TRAFFIC') {
        res = await axios.get(`http://localhost:8000/benchmark_traffic`, { params });
        // Normalize keys from backend
        const tStatic = res.data.static;
        const tLive = res.data.live;
        data = {
            type: 'TRAFFIC',
            tagline: "TRAFFIC IMPACT ANALYSIS",
            dataA: { label: "Static CH", ...tStatic, color: "#22c55e" }, // Green
            dataB: { label: "Live Hybrid", ...tLive, color: "#f97316" }  // Orange
        };
      } 
      else if (type === 'STRATEGY') {
        res = await axios.get(`http://localhost:8000/compare_strategies`, { params });
        const sStd = res.data.standard;
        const sWei = res.data.weighted;
        const speedup = (sStd.time / sWei.time).toFixed(1);
        data = {
            type: 'STRATEGY',
            tagline: `${speedup}x FASTER STRATEGY`,
            dataA: { label: "Standard A*", ...sStd, color: "#ef4444" }, // Red
            dataB: { label: "Weighted A*", ...sWei, color: "#f97316" }  // Orange
        };
      }

      setComparison(data);
    } catch (err) {
      console.error(err);
      setError("Benchmark failed. Backend might be offline.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full flex-col md:flex-row font-sans text-gray-100 bg-gray-900">
      
      {/* SIDEBAR */}
      <div className="w-full md:w-1/3 lg:w-1/4 bg-gray-900 p-6 flex flex-col gap-4 shadow-2xl z-20 overflow-y-auto border-r border-gray-800">
        <div>
          <h1 className="text-2xl font-bold text-blue-400">Route Opt Engine</h1>
          <p className="text-gray-500 text-xs mt-1">Advanced Pathfinding Benchmarks</p>
        </div>

        {/* CONTROLS */}
        <div className="flex flex-col gap-2 mt-4">
            <button onClick={() => runBenchmark('ALGO')} disabled={loading || !origin} 
                className="py-3 px-4 bg-gray-800 border border-gray-700 hover:border-purple-500 hover:text-purple-400 rounded transition-all text-sm font-bold text-left flex justify-between items-center group">
                <span>1. A* (Python) vs CH (C++)</span>
                <span className="text-xs bg-purple-900/30 text-purple-400 px-2 py-1 rounded group-hover:bg-purple-500 group-hover:text-white transition-colors">Raw Speed</span>
            </button>
            
            <button onClick={() => runBenchmark('TRAFFIC')} disabled={loading || !origin} 
                className="py-3 px-4 bg-gray-800 border border-gray-700 hover:border-green-500 hover:text-green-400 rounded transition-all text-sm font-bold text-left flex justify-between items-center group">
                <span>2. Static vs Live Traffic</span>
                <span className="text-xs bg-green-900/30 text-green-400 px-2 py-1 rounded group-hover:bg-green-500 group-hover:text-white transition-colors">Utility</span>
            </button>
            
            <button onClick={() => runBenchmark('STRATEGY')} disabled={loading || !origin} 
                className="py-3 px-4 bg-gray-800 border border-gray-700 hover:border-orange-500 hover:text-orange-400 rounded transition-all text-sm font-bold text-left flex justify-between items-center group">
                <span>3. Standard vs Weighted A*</span>
                <span className="text-xs bg-orange-900/30 text-orange-400 px-2 py-1 rounded group-hover:bg-orange-500 group-hover:text-white transition-colors">Heuristic</span>
            </button>

            <button onClick={handleReset} className="mt-2 py-2 text-gray-500 hover:text-white text-xs uppercase tracking-widest border border-dashed border-gray-700 hover:border-gray-500 rounded">
                Reset Map
            </button>
        </div>

        {/* LOADING & ERROR */}
        {loading && <div className="text-center p-4 text-blue-400 animate-pulse">Running Benchmark...</div>}
        {error && <div className="p-3 bg-red-900/20 border border-red-800 text-red-400 text-xs rounded">{error}</div>}

        {/* STANDARDIZED RESULTS PANEL */}
        {comparison && (
            <div className="mt-4 animate-fade-in">
                <div className="text-center text-xs font-bold text-gray-500 uppercase tracking-widest mb-2 border-b border-gray-800 pb-2">
                    {comparison.tagline}
                </div>

                {/* Card A */}
                <div className="mb-3 p-3 bg-gray-800/50 rounded border-l-4" style={{ borderColor: comparison.dataA.color }}>
                    <div className="flex justify-between items-center mb-1">
                        <span className="font-bold text-sm" style={{ color: comparison.dataA.color }}>{comparison.dataA.label}</span>
                        <span className="text-[10px] text-gray-500 bg-gray-900 px-1 rounded">CASE A</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs font-mono text-gray-300">
                        <div>⏱ {comparison.dataA.time} ms</div>
                        <div>📏 {comparison.dataA.distance} km</div>
                    </div>
                </div>

                {/* Card B */}
                <div className="p-3 bg-gray-800/50 rounded border-l-4" style={{ borderColor: comparison.dataB.color }}>
                    <div className="flex justify-between items-center mb-1">
                        <span className="font-bold text-sm" style={{ color: comparison.dataB.color }}>{comparison.dataB.label}</span>
                        <span className="text-[10px] text-gray-500 bg-gray-900 px-1 rounded">CASE B</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs font-mono text-gray-300">
                        <div>⏱ {comparison.dataB.time} ms</div>
                        <div>📏 {comparison.dataB.distance} km</div>
                    </div>
                </div>
            </div>
        )}
      </div>

      {/* MAP */}
      <div className="flex-1 relative z-10">
        <MapContainer center={[12.9716, 77.5946]} zoom={13} style={{ height: "100%", width: "100%" }}>
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" attribution='&copy; CARTO' />
          <LocationSelector setOrigin={setOrigin} setDestination={setDestination} origin={origin} destination={destination} />
          
          {origin && <Marker position={[origin.lat, origin.lng]}><Popup>Start</Popup></Marker>}
          {destination && <Marker position={[destination.lat, destination.lng]}><Popup>Dest</Popup></Marker>}

          {/* DYNAMIC PATH RENDERING */}
          {comparison && (
              <>
                  {/* Path A (Usually Baseline - Thicker, Transparent) */}
                  {comparison.dataA.path.length > 0 && (
                      <Polyline 
                        positions={comparison.dataA.path} 
                        color={comparison.dataA.color} 
                        weight={8} 
                        opacity={0.4} 
                      />
                  )}
                  {/* Path B (Usually Comparison - Thinner, Solid) */}
                  {comparison.dataB.path.length > 0 && (
                      <Polyline 
                        positions={comparison.dataB.path} 
                        color={comparison.dataB.color} 
                        weight={4} 
                        opacity={1.0} 
                      />
                  )}
                  <ChangeView bounds={comparison.dataA.path} />
              </>
          )}
        </MapContainer>
        
        {/* Floating Legend for Map */}
        {comparison && (
            <div className="absolute top-4 right-4 bg-gray-900/90 p-3 rounded shadow-xl border border-gray-700 z-[1000] text-xs">
                <div className="font-bold text-gray-400 mb-2 uppercase text-[10px]">Graph Legend</div>
                <div className="flex items-center gap-2 mb-1">
                    <div className="w-4 h-1 rounded" style={{ backgroundColor: comparison.dataA.color }}></div>
                    <span className="text-gray-200">{comparison.dataA.label}</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-1 rounded" style={{ backgroundColor: comparison.dataB.color }}></div>
                    <span className="text-gray-200">{comparison.dataB.label}</span>
                </div>
            </div>
        )}
      </div>
    </div>
  );
}