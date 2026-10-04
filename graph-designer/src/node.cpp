#include "node.h"

#include <utility>

namespace graphs {

std::string nodeTypeToString(NodeType type) {
    switch (type) {
        case NodeType::FILE:
            return "FILE";
    }
    return "UNKNOWN";
}

std::string Node::normalizePath(const std::string& path) {
    std::string normalized;
    normalized.reserve(path.size());

    // Replace Windows backslashes with forward slashes
    for (char c : path) {
        if (c == '\\') {
            normalized.push_back('/');
        } else {
            normalized.push_back(c);
        }
    }

    // Strip leading "./" if present
    while (normalized.rfind("./", 0) == 0) {
        normalized.erase(0, 2);
    }

    // Strip leading "/" if present
    while (!normalized.empty() && normalized.front() == '/') {
        normalized.erase(0, 1);
    }

    return normalized;
}

std::string Node::makeFileUri(const std::string& relative_path) {
    std::string norm = normalizePath(relative_path);
    // If already prefixed with "file:", avoid duplicating
    if (norm.rfind("file:", 0) == 0) {
        return norm;
    }
    return "file:" + norm;
}

Node::Node(std::string id,
           std::string file_path,
           NodeType type,
           std::string language,
           std::unordered_map<std::string, std::string> metadata)
    : id_(std::move(id)),
      file_path_(std::move(file_path)),
      type_(type),
      language_(std::move(language)),
      metadata_(std::move(metadata)) {}

Node Node::createFileNode(
    const std::string& relative_path,
    const std::string& language,
    const std::unordered_map<std::string, std::string>& metadata) {
    std::string norm_path = normalizePath(relative_path);
    std::string uri = makeFileUri(norm_path);
    return Node(std::move(uri), std::move(norm_path), NodeType::FILE, language, metadata);
}

std::string Node::getMetadataValue(const std::string& key, const std::string& default_val) const {
    auto it = metadata_.find(key);
    if (it != metadata_.end()) {
        return it->second;
    }
    return default_val;
}

void Node::setMetadataValue(std::string key, std::string value) {
    metadata_[std::move(key)] = std::move(value);
}

} // namespace graphs
