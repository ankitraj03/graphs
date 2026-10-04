#pragma once

#include <string>

namespace graphs {

/**
 * @brief Represents the kind of syntactic or architectural relationship between two nodes.
 *
 * Grounded in the Phase 4 specification:
 * - INCLUDE: Physical header or file inclusion (e.g. #include "header.h")
 * - IMPORT: Module or package import (e.g. import os, from x import y, require())
 * - REFERENCE: General symbolic or lexical cross-reference
 */
enum class RelationshipType {
    INCLUDE,
    IMPORT,
    REFERENCE,
};

/// Convert RelationshipType enum to its canonical uppercase string.
std::string relationshipTypeToString(RelationshipType type);

/// Parse canonical string to RelationshipType. Throws std::invalid_argument if unrecognized.
RelationshipType stringToRelationshipType(const std::string& str);

} // namespace graphs
