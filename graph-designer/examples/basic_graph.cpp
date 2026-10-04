#include <iostream>

#include "graph.h"
#include "node.h"
#include "edge.h"
#include "relationship_type.h"

using namespace graphs;

int main() {
    std::cout << "========================================\n";
    std::cout << "Graph Designer — Basic Graph Demonstration\n";
    std::cout << "========================================\n\n";

    Graph graph;

    // 1. Programmatically construct graph using clean API
    graph.addRelationship("src/main.cpp", "include/user.h", RelationshipType::INCLUDE);
    graph.addRelationship("src/main.cpp", "include/database.h", RelationshipType::INCLUDE);
    graph.addRelationship("src/user.cpp", "include/user.h", RelationshipType::INCLUDE);
    graph.addRelationship("src/database.cpp", "include/database.h", RelationshipType::INCLUDE);
    graph.addRelationship("src/app.py", "src/models.py", RelationshipType::IMPORT);

    // 2. Query basic metrics
    std::cout << "Graph contains " << graph.nodeCount() << " nodes and "
              << graph.edgeCount() << " edges.\n\n";

    // 3. Print human-readable graph representation
    std::cout << graph.toString() << "\n";

    // 4. Test neighbor queries
    std::string target = "file:include/user.h";
    std::cout << "Who depends on " << target << "? (Incoming neighbors):\n";
    for (const auto& in_id : graph.getIncomingNeighbors(target)) {
        std::cout << "  <- " << in_id << "\n";
    }

    // 5. Test BFS traversal
    std::string root = "file:src/main.cpp";
    std::cout << "\nBFS traversal starting at " << root << ":\n";
    for (const auto& node_id : graph.bfs(root)) {
        std::cout << "  -> " << node_id << "\n";
    }

    return 0;
}
