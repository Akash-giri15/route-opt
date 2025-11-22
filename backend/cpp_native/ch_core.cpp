// backend/cpp_native/ch_core.cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <vector>
#include <queue>
#include <tuple>
#include <limits>
#include <iostream>

namespace py = pybind11;

struct Edge {
    int target;
    double weight;
    bool is_shortcut;
    int via_node; 
};

class CHGraph {
public:
    int num_nodes;
    std::vector<std::vector<Edge>> adj_out;
    std::vector<std::vector<Edge>> adj_in;
    std::vector<bool> contracted;
    std::vector<int> rank;
    std::vector<int> node_order;

    CHGraph(int n) : num_nodes(n) {
        adj_out.resize(n);
        adj_in.resize(n);
        contracted.assign(n, false);
        rank.assign(n, -1);
    }

    void add_edge(int u, int v, double weight) {
        adj_out[u].push_back({v, weight, false, -1});
        adj_in[v].push_back({u, weight, false, -1});
    }

    void add_ch_edge(int u, int v, double weight, bool is_shortcut, int via) {
        adj_out[u].push_back({v, weight, is_shortcut, via});
        adj_in[v].push_back({u, weight, is_shortcut, via});
    }

    void set_rank(int u, int r) {
        if (u >= 0 && u < num_nodes) rank[u] = r;
    }

    // --- BUILD LOGIC (Same as before) ---
    bool witness_search(int u, int v, double max_dist, int exclude_node, int hop_limit) {
        for (const auto& edge : adj_out[u]) {
            if (edge.target == v && edge.weight <= max_dist) return true;
        }
        std::priority_queue<std::tuple<double, int, int>, std::vector<std::tuple<double, int, int>>, std::greater<>> pq;
        pq.push({0.0, u, 0});

        while (!pq.empty()) {
            auto [d, curr, h] = pq.top();
            pq.pop();
            if (d > max_dist) return false;
            if (curr == v) return true;
            if (h >= hop_limit) continue;

            for (const auto& edge : adj_out[curr]) {
                if (contracted[edge.target] && edge.target != v) continue;
                if (edge.target == exclude_node) continue;
                double new_dist = d + edge.weight;
                if (new_dist <= max_dist) pq.push({new_dist, edge.target, h + 1});
            }
        }
        return false;
    }

    int contract_node(int node) {
        contracted[node] = true;
        int shortcuts_added = 0;
        std::vector<Edge> in_neighbors;
        for (const auto& e : adj_in[node]) { if (!contracted[e.target]) in_neighbors.push_back(e); }
        std::vector<Edge> out_neighbors;
        for (const auto& e : adj_out[node]) { if (!contracted[e.target]) out_neighbors.push_back(e); }

        long long complexity = (long long)in_neighbors.size() * out_neighbors.size();
        bool skip_witness = complexity > 500; 
        int max_shortcuts = 100;

        for (const auto& in_edge : in_neighbors) {
            int u = in_edge.target;
            double d_uv = in_edge.weight;
            for (const auto& out_edge : out_neighbors) {
                int w = out_edge.target;
                if (u == w) continue;
                if (shortcuts_added >= max_shortcuts) return shortcuts_added;
                
                double d_vw = out_edge.weight;
                double total = d_uv + d_vw;
                bool needed = true;
                if (!skip_witness) {
                    if (witness_search(u, w, total, node, 3)) needed = false;
                } else {
                    if (witness_search(u, w, total, node, 1)) needed = false;
                }

                if (needed) {
                    adj_out[u].push_back({w, total, true, node});
                    adj_in[w].push_back({u, total, true, node});
                    shortcuts_added++;
                }
            }
        }
        return shortcuts_added;
    }

    void build_ch(std::vector<int> order) {
        node_order = order;
        int r = 0;
        for (int node : node_order) {
            rank[node] = r++;
            contract_node(node);
            if (r % 5000 == 0) std::cout << "Progress: " << r << "/" << node_order.size() << std::endl;
        }
    }

    py::dict get_graph_data() {
        py::list edges;
        for (int u = 0; u < num_nodes; ++u) {
            for (const auto& e : adj_out[u]) {
                edges.append(py::make_tuple(u, e.target, e.weight, e.is_shortcut, e.via_node));
            }
        }
        py::dict result;
        result["edges"] = edges;
        result["ranks"] = rank;
        return result;
    }

    // --- QUERY ENGINE FIX ---
    
    void unpack(int u, int v, std::vector<int>& path) {
        // FIX: Iterate through ALL edges to find a valid shortcut.
        // Do not just return the first edge you see.
        for (const auto& e : adj_out[u]) {
            if (e.target == v) {
                if (e.is_shortcut && e.via_node != -1) {
                    // Found a shortcut! Recurse immediately.
                    unpack(u, e.via_node, path);
                    unpack(e.via_node, v, path);
                    return; 
                }
            }
        }
        // If we finish the loop and found no shortcuts, 
        // it means u->v is a real base edge.
        path.push_back(v);
    }

    py::tuple query(int origin, int dest) {
        if (origin < 0 || origin >= num_nodes || dest < 0 || dest >= num_nodes) {
            return py::make_tuple(py::list(), 0.0);
        }

        std::priority_queue<std::pair<double, int>, std::vector<std::pair<double, int>>, std::greater<>> fwd_pq, bwd_pq;
        std::vector<double> fwd_dist(num_nodes, std::numeric_limits<double>::infinity());
        std::vector<double> bwd_dist(num_nodes, std::numeric_limits<double>::infinity());
        std::vector<int> fwd_parent(num_nodes, -1);
        std::vector<int> bwd_parent(num_nodes, -1);

        fwd_pq.push({0.0, origin});
        fwd_dist[origin] = 0.0;
        bwd_pq.push({0.0, dest});
        bwd_dist[dest] = 0.0;

        double mu = std::numeric_limits<double>::infinity();
        int meet_node = -1;

        while (!fwd_pq.empty() || !bwd_pq.empty()) {
            if (!fwd_pq.empty()) {
                auto [d, u] = fwd_pq.top(); fwd_pq.pop();
                if (d <= mu) {
                    for (const auto& e : adj_out[u]) {
                        if (rank[e.target] > rank[u]) {
                            double new_dist = d + e.weight;
                            if (new_dist < fwd_dist[e.target]) {
                                fwd_dist[e.target] = new_dist;
                                fwd_parent[e.target] = u;
                                fwd_pq.push({new_dist, e.target});
                                if (bwd_dist[e.target] != std::numeric_limits<double>::infinity()) {
                                    double total = new_dist + bwd_dist[e.target];
                                    if (total < mu) { mu = total; meet_node = e.target; }
                                }
                            }
                        }
                    }
                }
            }
            if (!bwd_pq.empty()) {
                auto [d, u] = bwd_pq.top(); bwd_pq.pop();
                if (d <= mu) {
                    for (const auto& e : adj_in[u]) {
                        if (rank[e.target] > rank[u]) {
                            double new_dist = d + e.weight;
                            if (new_dist < bwd_dist[e.target]) {
                                bwd_dist[e.target] = new_dist;
                                bwd_parent[e.target] = u;
                                bwd_pq.push({new_dist, e.target});
                                if (fwd_dist[e.target] != std::numeric_limits<double>::infinity()) {
                                    double total = new_dist + fwd_dist[e.target];
                                    if (total < mu) { mu = total; meet_node = e.target; }
                                }
                            }
                        }
                    }
                }
            }
        }

        if (meet_node == -1) return py::make_tuple(py::list(), 0.0);

        std::vector<int> path;
        
        // Trace Origin -> Meet
        std::vector<int> up_path;
        int curr = meet_node;
        while (curr != origin) {
            int p = fwd_parent[curr];
            up_path.push_back(curr);
            curr = p;
        }
        path.push_back(origin);
        
        // Unpack Upward
        curr = origin;
        for (int i = up_path.size() - 1; i >= 0; --i) {
            int next_node = up_path[i];
            unpack(curr, next_node, path);
            curr = next_node;
        }

        // Trace Meet -> Dest
        curr = meet_node;
        while (curr != dest) {
            int next_node = bwd_parent[curr];
            unpack(curr, next_node, path);
            curr = next_node;
        }

        py::list res_path;
        for (int n : path) res_path.append(n);

        return py::make_tuple(res_path, mu / 1000.0);
    }
};

PYBIND11_MODULE(ch_native, m) {
    py::class_<CHGraph>(m, "CHGraph")
        .def(py::init<int>())
        .def("add_edge", &CHGraph::add_edge)
        .def("add_ch_edge", &CHGraph::add_ch_edge)
        .def("set_rank", &CHGraph::set_rank)
        .def("build_ch", &CHGraph::build_ch)
        .def("get_graph_data", &CHGraph::get_graph_data)
        .def("query", &CHGraph::query);
}