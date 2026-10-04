#include "edge.h"

#include <utility>

namespace graphs {

Edge::Edge(std::string source_id,
           std::string target_id,
           RelationshipType type,
           std::unordered_map<std::string, std::string> metadata)
    : source_id_(std::move(source_id)),
      target_id_(std::move(target_id)),
      type_(type),
      metadata_(std::move(metadata)) {}

std::string Edge::getMetadataValue(const std::string& key, const std::string& default_val) const {
    auto it = metadata_.find(key);
    if (it != metadata_.end()) {
        return it->second;
    }
    return default_val;
}

void Edge::setMetadataValue(std::string key, std::string value) {
    metadata_[std::move(key)] = std::move(value);
}

std::string Edge::toString() const {
    return source_id_ + " --" + relationshipTypeToString(type_) + "--> " + target_id_;
}

} // namespace graphs
