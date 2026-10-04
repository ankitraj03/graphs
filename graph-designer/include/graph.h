#pragma once

#include <cstddef>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include "edge.h"
#include "node.h"
#include "relationship_type.h"

namespace graphs {

/**
 * @brief In-memory directed graph representing repository files and their dependencies.
 *
 * Grounded in Phase 4 specifications:
 * - Directed edges (A -> B does not imply B -> A)
 * - Fast access to both outgoing and incoming relationships
 * - Strict non-duplication: duplicate edges with identical (source, target, type) are rejected
 * - Multi-type support: A --IMPORT--> B and A --INCLUDE--> B are preserved as distinct edges
 * - Self-edges (A -> A) are strictly disallowed and rejected
 * - Safe cycle handling during BFS / DFS traversals
 * - Safe disconnected subgraphs and empty graph handling
 */
class Graph {
public:
    Graph() = default;

    // --- Node Operations ---

    /**
     * @brief Add a node to the graph.
     * @return true if inserted, false if a node with this ID already exists.
     */
    bool addNode(const Node& node);

    /**
     * @brief Add a node by moving.
     */
    bool addNode(Node&& node);

    /**
     * @brief Check whether a node with the given ID exists.
     */
    bool hasNode(const std::string& node_id) const;

    /**
     * @brief Retrieve pointer to a Node by ID. Returns nullptr if not found.
     */
    const Node* getNode(const std::string& node_id) const;
    Node* getNode(const std::string& node_id);

    /**
     * @brief Get read-only reference to all nodes map.
     */
    const std::unordered_map<std::string, Node>& getAllNodes() const noexcept {
        return nodes_;
    }

    // --- Edge Operations ---

    /**
     * @brief Add a directed Edge.
     * Rejects self-edges (source == target) by returning false.
     * Rejects duplicate edges (source, target, type identical) by returning false.
     * Automatically registers endpoints as default FILE nodes if not already present.
     * @return true if added, false if rejected (self-edge or duplicate).
     */
    bool addEdge(const Edge& edge);

    /**
     * @brief Convenient relationship builder accepting paths or URIs.
     * Normalizes inputs to canonical "file:<path>" URIs automatically.
     * @param source_path_or_uri Source file path or URI (e.g. "main.cpp" or "file:main.cpp").
     * @param target_path_or_uri Target file path or URI (e.g. "user.h" or "file:user.h").
     * @param type Relationship kind (INCLUDE, IMPORT, REFERENCE).
     * @param metadata Optional key-value metadata map.
     * @return true if edge successfully added, false if self-edge or duplicate.
     */
    bool addRelationship(const std::string& source_path_or_uri,
                         const std::string& target_path_or_uri,
                         RelationshipType type,
                         const std::unordered_map<std::string, std::string>& metadata = {});

    /**
     * @brief Check if an exact edge exists matching (source_id, target_id, type).
     */
    bool hasEdge(const std::string& source_id,
                 const std::string& target_id,
                 RelationshipType type) const;

    /**
     * @brief Check if any directed edge exists between source_id and target_id.
     */
    bool hasAnyEdge(const std::string& source_id, const std::string& target_id) const;

    // --- Relationship Accessors ---

    /**
     * @brief Retrieve all outgoing edges originating from node_id by const reference (zero copies).
     */
    const std::vector<Edge>& getOutgoingEdges(const std::string& node_id) const;

    /**
     * @brief Retrieve all incoming edges pointing to node_id by const reference (zero copies).
     */
    const std::vector<Edge>& getIncomingEdges(const std::string& node_id) const;

    /**
     * @brief Retrieve unique node IDs directly reached from node_id.
     */
    std::vector<std::string> getOutgoingNeighbors(const std::string& node_id) const;

    /**
     * @brief Retrieve unique node IDs that point directly to node_id.
     */
    std::vector<std::string> getIncomingNeighbors(const std::string& node_id) const;

    // --- Graph Metrics & Lifecycle ---

    size_t nodeCount() const noexcept { return nodes_.size(); }
    size_t edgeCount() const noexcept { return edges_.size(); }
    bool empty() const noexcept { return nodes_.empty(); }
    void clear() noexcept;

    // --- Traversal Algorithms ---

    /**
     * @brief Breadth-First Search reachable nodes from start_node_id.
     * Safe against cycles (nodes visited at most once).
     * @return List of reachable node IDs in BFS discovery order (including start node).
     */
    std::vector<std::string> bfs(const std::string& start_node_id) const;

    /**
     * @brief Depth-First Search reachable nodes from start_node_id.
     * Safe against cycles (nodes visited at most once).
     * @return List of reachable node IDs in DFS discovery order (including start node).
     */
    std::vector<std::string> dfs(const std::string& start_node_id) const;

    // --- Formatted Visualization ---

    /**
     * @brief Render formatted human-readable graph representation.
     */
    std::string toString() const;

private:
    std::unordered_map<std::string, Node> nodes_;
    std::unordered_set<Edge, EdgeHash> edges_;

    // Adjacency lists for fast O(1) edge retrieval
    std::unordered_map<std::string, std::vector<Edge>> outgoing_edges_;
    std::unordered_map<std::string, std::vector<Edge>> incoming_edges_;

    void ensureNodeExists(const std::string& node_id);
};

} // namespace graphs
