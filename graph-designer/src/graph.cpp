#include "graph.h"

#include <algorithm>
#include <queue>
#include <sstream>
#include <stack>

namespace graphs {

bool Graph::addNode(const Node& node) {
    if (node.getId().empty()) {
        return false;
    }
    auto result = nodes_.emplace(node.getId(), node);
    return result.second;
}

bool Graph::addNode(Node&& node) {
    if (node.getId().empty()) {
        return false;
    }
    std::string id = node.getId();
    auto result = nodes_.emplace(std::move(id), std::move(node));
    return result.second;
}

bool Graph::hasNode(const std::string& node_id) const {
    return nodes_.find(node_id) != nodes_.end();
}

const Node* Graph::getNode(const std::string& node_id) const {
    auto it = nodes_.find(node_id);
    if (it != nodes_.end()) {
        return &(it->second);
    }
    return nullptr;
}

Node* Graph::getNode(const std::string& node_id) {
    auto it = nodes_.find(node_id);
    if (it != nodes_.end()) {
        return &(it->second);
    }
    return nullptr;
}

void Graph::ensureNodeExists(const std::string& node_id) {
    if (nodes_.find(node_id) == nodes_.end()) {
        // Derive clean relative path from URI if it starts with "file:"
        std::string rel_path = node_id;
        if (rel_path.rfind("file:", 0) == 0) {
            rel_path = rel_path.substr(5);
        }
        nodes_.emplace(node_id, Node::createFileNode(rel_path));
    }
}

bool Graph::addEdge(const Edge& edge) {
    // 1. Enforce Self-Edge Rule (Option B: Disallow self-edges)
    if (edge.getSourceId() == edge.getTargetId()) {
        return false;
    }

    // 2. Enforce Duplicate Edge Rule (Option A: Unique by (source, target, type))
    if (edges_.find(edge) != edges_.end()) {
        return false;
    }

    // 3. Auto-register endpoint nodes if not already present
    ensureNodeExists(edge.getSourceId());
    ensureNodeExists(edge.getTargetId());

    // 4. Insert into primary edge set and adjacency maps
    edges_.insert(edge);
    outgoing_edges_[edge.getSourceId()].push_back(edge);
    incoming_edges_[edge.getTargetId()].push_back(edge);

    return true;
}

bool Graph::addRelationship(const std::string& source_path_or_uri,
                            const std::string& target_path_or_uri,
                            RelationshipType type,
                            const std::unordered_map<std::string, std::string>& metadata) {
    std::string src_uri = Node::makeFileUri(source_path_or_uri);
    std::string tgt_uri = Node::makeFileUri(target_path_or_uri);
    return addEdge(Edge(std::move(src_uri), std::move(tgt_uri), type, metadata));
}

bool Graph::hasEdge(const std::string& source_id,
                    const std::string& target_id,
                    RelationshipType type) const {
    Edge dummy(source_id, target_id, type);
    return edges_.find(dummy) != edges_.end();
}

bool Graph::hasAnyEdge(const std::string& source_id, const std::string& target_id) const {
    auto it = outgoing_edges_.find(source_id);
    if (it == outgoing_edges_.end()) {
        return false;
    }
    for (const auto& edge : it->second) {
        if (edge.getTargetId() == target_id) {
            return true;
        }
    }
    return false;
}

namespace {
// Thread-safe empty vector returned when a node has no incident edges
const std::vector<Edge> EMPTY_EDGE_LIST{};
} // namespace

const std::vector<Edge>& Graph::getOutgoingEdges(const std::string& node_id) const {
    auto it = outgoing_edges_.find(node_id);
    if (it != outgoing_edges_.end()) {
        return it->second;
    }
    return EMPTY_EDGE_LIST;
}

const std::vector<Edge>& Graph::getIncomingEdges(const std::string& node_id) const {
    auto it = incoming_edges_.find(node_id);
    if (it != incoming_edges_.end()) {
        return it->second;
    }
    return EMPTY_EDGE_LIST;
}

std::vector<std::string> Graph::getOutgoingNeighbors(const std::string& node_id) const {
    std::vector<std::string> neighbors;
    std::unordered_set<std::string> seen;

    auto it = outgoing_edges_.find(node_id);
    if (it != outgoing_edges_.end()) {
        for (const auto& edge : it->second) {
            if (seen.insert(edge.getTargetId()).second) {
                neighbors.push_back(edge.getTargetId());
            }
        }
    }
    return neighbors;
}

std::vector<std::string> Graph::getIncomingNeighbors(const std::string& node_id) const {
    std::vector<std::string> neighbors;
    std::unordered_set<std::string> seen;

    auto it = incoming_edges_.find(node_id);
    if (it != incoming_edges_.end()) {
        for (const auto& edge : it->second) {
            if (seen.insert(edge.getSourceId()).second) {
                neighbors.push_back(edge.getSourceId());
            }
        }
    }
    return neighbors;
}

void Graph::clear() noexcept {
    nodes_.clear();
    edges_.clear();
    outgoing_edges_.clear();
    incoming_edges_.clear();
}

std::vector<std::string> Graph::bfs(const std::string& start_node_id) const {
    if (!hasNode(start_node_id)) {
        return {};
    }

    std::vector<std::string> traversal_order;
    std::unordered_set<std::string> visited;
    std::queue<std::string> queue;

    visited.insert(start_node_id);
    queue.push(start_node_id);

    while (!queue.empty()) {
        std::string current = queue.front();
        queue.pop();
        traversal_order.push_back(current);

        auto it = outgoing_edges_.find(current);
        if (it != outgoing_edges_.end()) {
            for (const auto& edge : it->second) {
                const std::string& neighbor = edge.getTargetId();
                if (visited.insert(neighbor).second) {
                    queue.push(neighbor);
                }
            }
        }
    }

    return traversal_order;
}

std::vector<std::string> Graph::dfs(const std::string& start_node_id) const {
    if (!hasNode(start_node_id)) {
        return {};
    }

    std::vector<std::string> traversal_order;
    std::unordered_set<std::string> visited;
    std::stack<std::string> stack;

    stack.push(start_node_id);

    while (!stack.empty()) {
        std::string current = stack.top();
        stack.pop();

        if (visited.find(current) != visited.end()) {
            continue;
        }

        visited.insert(current);
        traversal_order.push_back(current);

        auto it = outgoing_edges_.find(current);
        if (it != outgoing_edges_.end()) {
            // Push neighbors in reverse order so first neighbor is popped first
            const auto& edge_list = it->second;
            for (auto r_it = edge_list.rbegin(); r_it != edge_list.rend(); ++r_it) {
                const std::string& neighbor = r_it->getTargetId();
                if (visited.find(neighbor) == visited.end()) {
                    stack.push(neighbor);
                }
            }
        }
    }

    return traversal_order;
}

std::string Graph::toString() const {
    std::ostringstream oss;
    oss << "Graph (" << nodeCount() << " nodes, " << edgeCount() << " edges):\n";

    if (nodes_.empty()) {
        oss << "  (empty)\n";
        return oss.str();
    }

    // Sort node IDs for deterministic rendering
    std::vector<std::string> sorted_ids;
    sorted_ids.reserve(nodes_.size());
    for (const auto& pair : nodes_) {
        sorted_ids.push_back(pair.first);
    }
    std::sort(sorted_ids.begin(), sorted_ids.end());

    for (const auto& id : sorted_ids) {
        oss << "  " << id << "\n";
        auto it = outgoing_edges_.find(id);
        if (it != outgoing_edges_.end() && !it->second.empty()) {
            for (const auto& edge : it->second) {
                oss << "    --" << relationshipTypeToString(edge.getType())
                    << "--> " << edge.getTargetId() << "\n";
            }
        } else {
            oss << "    (no outgoing dependencies)\n";
        }
    }

    return oss.str();
}

} // namespace graphs
