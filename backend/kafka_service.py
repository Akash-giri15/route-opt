import threading
import time
import random
import networkx as nx

class TrafficManager:
    def __init__(self, G):
        self.G = G
        self.running = False
        self.lock = threading.Lock() # Thread safety for graph updates

    def start_consumer(self):
        self.running = True
        # Start background thread to simulate/consume Kafka
        t = threading.Thread(target=self._consume_loop)
        t.daemon = True
        t.start()
        print("📡 Live Traffic Consumer Started...")

    def _consume_loop(self):
        """Simulates consuming messages from a Kafka topic 'traffic_updates'"""
        while self.running:
            # SIMULATION: In real life, use: msg = consumer.poll(1.0)
            time.sleep(2) # New traffic data every 2 seconds
            
            # Simulate a "Traffic Jam" event on a random edge
            if self.G.number_of_edges() > 0:
                edges = list(self.G.edges(data=True))
                # Pick 5 random edges to update
                affected = random.sample(edges, 5)
                
                with self.lock:
                    for u, v, data in affected:
                        # TRAFFIC LOGIC: Increase weight (slow down)
                        # In OSMnx, 'length' is static meters. 'weight' is used for routing.
                        base_len = data.get('length', 100)
                        
                        # Apply congestion factor (e.g., 5x slower)
                        current_factor = data.get('traffic_factor', 1.0)
                        new_factor = random.choice([1.0, 2.0, 5.0, 10.0]) # 1.0 is clear, 10.0 is gridlock
                        
                        # Update the graph
                        if self.G.is_multigraph():
                            self.G[u][v][0]['weight'] = base_len * new_factor
                            self.G[u][v][0]['traffic_factor'] = new_factor
                        else:
                            self.G[u][v]['weight'] = base_len * new_factor
                            self.G[u][v]['traffic_factor'] = new_factor
                            
                        # print(f"⚠️ Traffic update on edge {u}->{v}: Factor {new_factor}x")

    def stop(self):
        self.running = False