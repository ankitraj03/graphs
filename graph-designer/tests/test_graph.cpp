#include <cassert>
#include <chrono>
#include <iostream>
#include <string>
#include <vector>

#include "graph.h"
#include "node.h"
#include "edge.h"
#include "relationship_type.h"

using namespace graphs;

void test_1_empty_graph() {
    std::cout << "[Test 1] Empty graph (0 nodes, 0 edges)... ";
    Graph g;
    assert(g.nodeCount() == 0);
    assert(g.edgeCount() == 0);
    assert(g.empty());
    assert(!g.hasNode("file:nonexistent.cpp"));
    assert(g.getNode("file:nonexistent.cpp") == nullptr);
    assert(g.getOutgoingEdges("file:nonexistent.cpp").empty());
    assert(g.getIncomingEdges("file:nonexistent.cpp").empty());
    assert(g.bfs("file:nonexistent.cpp").empty());
    assert(g.dfs("file:nonexistent.cpp").empty());
    std::cout << "PASSED\n";
}

void test_2_single_node() {
    std::cout << "[Test 2] Single node... ";
    Graph g;
    Node n = Node::createFileNode("src/main.cpp", "cpp");
    assert(n.getId() == "file:src/main.cpp");
    assert(n.getFilePath() == "src/main.cpp");
    assert(n.getLanguage() == "cpp");

    bool added = g.addNode(n);
    assert(added);
    assert(g.nodeCount() == 1);
    assert(g.edgeCount() == 0);
    assert(!g.empty());
    assert(g.hasNode("file:src/main.cpp"));

    const Node* found = g.getNode("file:src/main.cpp");
    assert(found != nullptr);
    assert(found->getId() == "file:src/main.cpp");
    assert(found->getFilePath() == "src/main.cpp");

    // Adding same node again returns false
    bool added_duplicate = g.addNode(n);
    assert(!added_duplicate);
    assert(g.nodeCount() == 1);
    std::cout << "PASSED\n";
}

void test_3_two_nodes_one_edge() {
    std::cout << "[Test 3] Two nodes and one edge (A -> B)... ";
    Graph g;
    bool edge_added = g.addRelationship("main.cpp", "user.h", RelationshipType::INCLUDE);
    assert(edge_added);
    assert(g.nodeCount() == 2);
    assert(g.edgeCount() == 1);
    assert(g.hasNode("file:main.cpp"));
    assert(g.hasNode("file:user.h"));
    assert(g.hasEdge("file:main.cpp", "file:user.h", RelationshipType::INCLUDE));
    assert(!g.hasEdge("file:user.h", "file:main.cpp", RelationshipType::INCLUDE)); // Directed!

    // Verify neighbors
    auto out = g.getOutgoingNeighbors("file:main.cpp");
    assert(out.size() == 1);
    assert(out[0] == "file:user.h");

    auto in = g.getIncomingNeighbors("file:user.h");
    assert(in.size() == 1);
    assert(in[0] == "file:main.cpp");
    std::cout << "PASSED\n";
}

void test_4_multiple_outgoing_edges() {
    std::cout << "[Test 4] Multiple outgoing edges (A -> B, A -> C)... ";
    Graph g;
    g.addRelationship("main.cpp", "user.h", RelationshipType::INCLUDE);
    g.addRelationship("main.cpp", "database.h", RelationshipType::INCLUDE);

    assert(g.nodeCount() == 3);
    assert(g.edgeCount() == 2);

    const auto& out_edges = g.getOutgoingEdges("file:main.cpp");
    assert(out_edges.size() == 2);

    auto out_neighbors = g.getOutgoingNeighbors("file:main.cpp");
    assert(out_neighbors.size() == 2);

    assert(g.getIncomingNeighbors("file:user.h").size() == 1);
    assert(g.getIncomingNeighbors("file:database.h").size() == 1);
    assert(g.getOutgoingNeighbors("file:user.h").empty());
    std::cout << "PASSED\n";
}

void test_5_incoming_relationship_lookup() {
    std::cout << "[Test 5] Incoming relationship lookup (A -> B, C -> B)... ";
    Graph g;
    g.addRelationship("main.cpp", "common.h", RelationshipType::INCLUDE);
    g.addRelationship("service.cpp", "common.h", RelationshipType::INCLUDE);

    assert(g.nodeCount() == 3);
    assert(g.edgeCount() == 2);

    const auto& in_edges = g.getIncomingEdges("file:common.h");
    assert(in_edges.size() == 2);

    auto in_neighbors = g.getIncomingNeighbors("file:common.h");
    assert(in_neighbors.size() == 2);

    bool has_main = false;
    bool has_service = false;
    for (const auto& nid : in_neighbors) {
        if (nid == "file:main.cpp") has_main = true;
        if (nid == "file:service.cpp") has_service = true;
    }
    assert(has_main && has_service);
    std::cout << "PASSED\n";
}

void test_6_duplicate_edge() {
    std::cout << "[Test 6] Duplicate edge deduplication (A -> B twice)... ";
    Graph g;
    bool first = g.addRelationship("main.cpp", "user.h", RelationshipType::INCLUDE);
    assert(first);
    assert(g.edgeCount() == 1);

    // Re-inserting exact identical edge
    bool second = g.addRelationship("main.cpp", "user.h", RelationshipType::INCLUDE);
    assert(!second); // Must be rejected
    assert(g.edgeCount() == 1); // Edge count remains exactly 1

    const auto& out_edges = g.getOutgoingEdges("file:main.cpp");
    assert(out_edges.size() == 1);
    std::cout << "PASSED\n";
}

void test_7_different_relationship_types() {
    std::cout << "[Test 7] Different relationship types (Option A: distinct edges)... ";
    Graph g;
    // Edge identity is (source, target, type)
    bool add_include = g.addRelationship("module.py", "types.py", RelationshipType::INCLUDE);
    bool add_import = g.addRelationship("module.py", "types.py", RelationshipType::IMPORT);
    assert(add_include);
    assert(add_import);
    assert(g.edgeCount() == 2); // Both are distinct valid edges

    assert(g.hasEdge("file:module.py", "file:types.py", RelationshipType::INCLUDE));
    assert(g.hasEdge("file:module.py", "file:types.py", RelationshipType::IMPORT));
    assert(!g.hasEdge("file:module.py", "file:types.py", RelationshipType::REFERENCE));

    // Inserting import again should be rejected
    bool re_add_import = g.addRelationship("module.py", "types.py", RelationshipType::IMPORT);
    assert(!re_add_import);
    assert(g.edgeCount() == 2);
    std::cout << "PASSED\n";
}

void test_8_disconnected_components() {
    std::cout << "[Test 8] Disconnected components (A -> B, C -> D)... ";
    Graph g;
    g.addRelationship("a.cpp", "b.h", RelationshipType::INCLUDE);
    g.addRelationship("c.py", "d.py", RelationshipType::IMPORT);

    assert(g.nodeCount() == 4);
    assert(g.edgeCount() == 2);

    // Reachability from A should not reach C or D
    auto bfs_a = g.bfs("file:a.cpp");
    assert(bfs_a.size() == 2);
    assert(bfs_a[0] == "file:a.cpp");
    assert(bfs_a[1] == "file:b.h");

    auto bfs_c = g.bfs("file:c.py");
    assert(bfs_c.size() == 2);
    assert(bfs_c[0] == "file:c.py");
    assert(bfs_c[1] == "file:d.py");
    std::cout << "PASSED\n";
}

void test_9_cycle_safe_traversal() {
    std::cout << "[Test 9] Cycle handling (A -> B -> C -> A safe BFS/DFS)... ";
    Graph g;
    g.addRelationship("a.cpp", "b.cpp", RelationshipType::INCLUDE);
    g.addRelationship("b.cpp", "c.cpp", RelationshipType::INCLUDE);
    g.addRelationship("c.cpp", "a.cpp", RelationshipType::INCLUDE);

    assert(g.nodeCount() == 3);
    assert(g.edgeCount() == 3);

    // BFS must terminate cleanly without infinite loop
    auto bfs_res = g.bfs("file:a.cpp");
    assert(bfs_res.size() == 3);

    // DFS must terminate cleanly without infinite loop
    auto dfs_res = g.dfs("file:a.cpp");
    assert(dfs_res.size() == 3);
    std::cout << "PASSED\n";
}

void test_10_self_relationship_disallowed() {
    std::cout << "[Test 10] Self-relationship (Option B: A -> A disallowed)... ";
    Graph g;
    g.addNode(Node::createFileNode("self.cpp"));

    // Attempting to add A -> A
    bool self_edge = g.addRelationship("self.cpp", "self.cpp", RelationshipType::INCLUDE);
    assert(!self_edge); // Disallowed: must be rejected!
    assert(g.edgeCount() == 0); // No edge added
    assert(g.getOutgoingEdges("file:self.cpp").empty());
    assert(g.getIncomingEdges("file:self.cpp").empty());
    assert(!g.hasEdge("file:self.cpp", "file:self.cpp", RelationshipType::INCLUDE));
    std::cout << "PASSED\n";
}

void test_11_larger_synthetic_graph() {
    std::cout << "[Test 11] Larger synthetic graph (1,000 nodes, 2,000 edges)... ";
    Graph g;
    const int N = 1000;

    auto t0 = std::chrono::high_resolution_clock::now();

    // Create 1000 nodes
    for (int i = 0; i < N; ++i) {
        std::string path = "src/file_" + std::to_string(i) + ".cpp";
        g.addNode(Node::createFileNode(path, "cpp"));
    }
    assert(g.nodeCount() == 1000);

    // Create 2000 directed edges: i -> (i+1)%N and i -> (i+2)%N
    for (int i = 0; i < N; ++i) {
        std::string src = "src/file_" + std::to_string(i) + ".cpp";
        std::string tgt1 = "src/file_" + std::to_string((i + 1) % N) + ".cpp";
        std::string tgt2 = "src/file_" + std::to_string((i + 2) % N) + ".cpp";

        g.addRelationship(src, tgt1, RelationshipType::INCLUDE);
        g.addRelationship(src, tgt2, RelationshipType::REFERENCE);
    }
    assert(g.edgeCount() == 2000);

    // Verify BFS reachable from node 0
    auto bfs_all = g.bfs("file:src/file_0.cpp");
    assert(bfs_all.size() == 1000);

    auto t1 = std::chrono::high_resolution_clock::now();
    double ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

    std::cout << "PASSED (" << ms << " ms)\n";
}

int main() {
    std::cout << "========================================\n";
    std::cout << "Graph Designer — Unit Test Suite\n";
    std::cout << "========================================\n\n";

    test_1_empty_graph();
    test_2_single_node();
    test_3_two_nodes_one_edge();
    test_4_multiple_outgoing_edges();
    test_5_incoming_relationship_lookup();
    test_6_duplicate_edge();
    test_7_different_relationship_types();
    test_8_disconnected_components();
    test_9_cycle_safe_traversal();
    test_10_self_relationship_disallowed();
    test_11_larger_synthetic_graph();

    std::cout << "\n========================================\n";
    std::cout << "ALL 11 GRAPH DESIGNER TESTS PASSED! [OK]\n";
    std::cout << "========================================\n";
    return 0;
}
