cmake_minimum_required(VERSION 3.14)
project(graph_designer CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(include)

set(GRAPH_SOURCES
    src/relationship_type.cpp
    src/node.cpp
    src/edge.cpp
    src/graph.cpp
)

# Test suite executable
add_executable(test_graph tests/test_graph.cpp ${GRAPH_SOURCES})

# Basic example executable
add_executable(basic_graph examples/basic_graph.cpp ${GRAPH_SOURCES})

# Standalone CLI tool
add_executable(graph_designer main.cpp ${GRAPH_SOURCES})
