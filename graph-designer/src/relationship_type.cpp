#include "relationship_type.h"

#include <algorithm>
#include <cctype>
#include <stdexcept>

namespace graphs {

std::string relationshipTypeToString(RelationshipType type) {
    switch (type) {
        case RelationshipType::INCLUDE:
            return "INCLUDE";
        case RelationshipType::IMPORT:
            return "IMPORT";
        case RelationshipType::REFERENCE:
            return "REFERENCE";
    }
    return "UNKNOWN";
}

RelationshipType stringToRelationshipType(const std::string& str) {
    std::string upper;
    upper.reserve(str.size());
    for (char c : str) {
        upper.push_back(static_cast<char>(std::toupper(static_cast<unsigned char>(c))));
    }

    if (upper == "INCLUDE") {
        return RelationshipType::INCLUDE;
    }
    if (upper == "IMPORT") {
        return RelationshipType::IMPORT;
    }
    if (upper == "REFERENCE") {
        return RelationshipType::REFERENCE;
    }

    throw std::invalid_argument("Unknown RelationshipType: " + str);
}

} // namespace graphs
