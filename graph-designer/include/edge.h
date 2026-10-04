#pragma once

#include <cstddef>
#include <functional>
#include <string>
#include <unordered_map>

#include "relationship_type.h"

namespace graphs {

/**
 * @brief Represents a directed dependency edge linking a source node to a target node.
 *
 * Grounded in Option A:
 * Edge identity is strictly defined by: (source_node, target_node, relationship_type)
 * Therefore:
 *   A --IMPORT--> B
 *   A --INCLUDE--> B
 * are two distinct valid edges.
 * But re-inserting A --IMPORT--> B is an identical duplicate.
 */
class Edge {
public:
    Edge() = default;

    /**
     * @brief Construct a directed Edge between two nodes.
     * @param source_id The source node URI (e.g. "file:main.cpp").
     * @param target_id The target node URI (e.g. "file:user.h").
     * @param type The relationship type (e.g. RelationshipType::INCLUDE).
     * @param metadata Optional key-value metadata map.
     */
    Edge(std::string source_id,
         std::string target_id,
         RelationshipType type,
         std::unordered_map<std::string, std::string> metadata = {});

    // Getters
    const std::string& getSourceId() const noexcept { return source_id_; }
    const std::string& getTargetId() const noexcept { return target_id_; }
    RelationshipType getType() const noexcept { return type_; }
    const std::unordered_map<std::string, std::string>& getMetadata() const noexcept { return metadata_; }

    // Metadata access
    std::string getMetadataValue(const std::string& key, const std::string& default_val = "") const;
    void setMetadataValue(std::string key, std::string value);

    // Human-readable format
    std::string toString() const;

    // Strict identity equality comparison
    bool operator==(const Edge& other) const noexcept {
        return source_id_ == other.source_id_ &&
               target_id_ == other.target_id_ &&
               type_ == other.type_;
    }

    bool operator!=(const Edge& other) const noexcept {
        return !(*this == other);
    }

private:
    std::string source_id_;
    std::string target_id_;
    RelationshipType type_{RelationshipType::REFERENCE};
    std::unordered_map<std::string, std::string> metadata_;
};

/**
 * @brief Hash functor for Edge based on (source_id, target_id, type).
 */
struct EdgeHash {
    size_t operator()(const Edge& edge) const noexcept {
        size_t h1 = std::hash<std::string>{}(edge.getSourceId());
        size_t h2 = std::hash<std::string>{}(edge.getTargetId());
        size_t h3 = std::hash<int>{}(static_cast<int>(edge.getType()));

        // Boost/standard hash combine formula
        size_t seed = h1;
        seed ^= h2 + 0x9e3779b9 + (seed << 6) + (seed >> 2);
        seed ^= h3 + 0x9e3779b9 + (seed << 6) + (seed >> 2);
        return seed;
    }
};

} // namespace graphs
