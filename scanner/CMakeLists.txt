cmake_minimum_required(VERSION 3.15)
project(graphs_scanner CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(file_scanner STATIC
    file_scanner.h
    file_scanner.cpp
)
target_include_directories(file_scanner PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(scanner
    main.cpp
)
target_link_libraries(scanner PRIVATE file_scanner)

add_executable(test_scanner
    test_scanner.cpp
)
target_link_libraries(test_scanner PRIVATE file_scanner)
