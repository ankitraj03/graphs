#pragma once

#include <string>
#include <unordered_map>

namespace graphs {

/**
 * @brief Primary entity type for a graph node.
 * For Phase 4, the initial canonical node type is FILE.
 */
enum class NodeType {
    FILE,
};

/// Convert NodeType enum to canonical string.
std::string nodeTypeToString(NodeType type);

/**
 * @brief Represents a repository entity (initially a source or header file) in the graph.
 *
 * Implements deterministic URI-based identity per Phase 4 specification:
 * Canonical scheme: "file:<normalized-repository-relative-path>"
 * Example: "file:src/main.cpp"
 */
class Node {
public:
    /// Default constructor creating an empty uninitialized node.
    Node() = default;

    /**
     * @brief Direct constructor with explicit URI id.
     * @param id The unique URI identifier (e.g. "file:src/main.cpp").
     * @param file_path The normalized repository-relative file path (e.g. "src/main.cpp").
     * @param type The entity type (e.g. NodeType::FILE).
     * @param language Optional language identifier (e.g. "cpp", "python", "typescript").
     * @param metadata Optional key-value metadata map.
     */
    Node(std::string id,
         std::string file_path,
         NodeType type = NodeType::FILE,
         std::string language = "",
         std::unordered_map<std::string, std::string> metadata = {});

    /**
     * @brief Factory method creating a canonical FILE node from a repository-relative path.
     * Normalizes backslashes to forward slashes, trims leading slashes, and prefixes "file:".
     */
    static Node createFileNode(
        const std::string& relative_path,
        const std::string& language = "",
        const std::unordered_map<std::string, std::string>& metadata = {});

    /**
     * @brief Construct a deterministic URI string from a repository-relative path.
     * @return "file:<normalized-relative-path>"
     */
    static std::string makeFileUri(const std::string& relative_path);

    /**
     * @brief Normalize a filesystem path to uniform forward-slash repository-relative format.
     */
    static std::string normalizePath(const std::string& path);

    // Getters
    const std::string& getId() const noexcept { return id_; }
    const std::string& getFilePath() const noexcept { return file_path_; }
    NodeType getType() const noexcept { return type_; }
    const std::string& getLanguage() const noexcept { return language_; }
    const std::unordered_map<std::string, std::string>& getMetadata() const noexcept { return metadata_; }

    // Metadata access
    std::string getMetadataValue(const std::string& key, const std::string& default_val = "") const;
    void setMetadataValue(std::string key, std::string value);

    // Equality based on unique node URI id
    bool operator==(const Node& other) const noexcept {
        return id_ == other.id_;
    }

    bool operator!=(const Node& other) const noexcept {
        return !(*this == other);
    }

private:
    std::string id_;
    std::string file_path_;
    NodeType type_{NodeType::FILE};
    std::string language_;
    std::unordered_map<std::string, std::string> metadata_;
};

} // namespace graphs
