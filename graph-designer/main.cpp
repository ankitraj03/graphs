#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

#include "graph.h"
#include "node.h"
#include "edge.h"
#include "relationship_type.h"

namespace {

// ============================================================================
// Lightweight, dependency-free JSON Parser
// ============================================================================

struct JsonValue {
    enum Type { NUL, BOOL, NUM, STR, ARR, OBJ } type = NUL;
    bool b = false;
    double n = 0.0;
    std::string s;
    std::vector<std::shared_ptr<JsonValue>> arr;
    std::vector<std::pair<std::string, std::shared_ptr<JsonValue>>> obj;

    bool isObject() const noexcept { return type == OBJ; }
    bool isArray() const noexcept { return type == ARR; }
    bool isString() const noexcept { return type == STR; }

    std::shared_ptr<JsonValue> get(const std::string& key) const {
        for (const auto& kv : obj) {
            if (kv.first == key) return kv.second;
        }
        return nullptr;
    }

    std::string getString(const std::string& key, const std::string& def = "") const {
        auto val = get(key);
        if (val && val->type == STR) {
            return val->s;
        }
        return def;
    }
};

class JsonParser {
public:
    explicit JsonParser(const std::string& src) : src_(src), pos_(0) {}

    bool parse(JsonValue& out, std::string& err) {
        skipWhitespace();
        if (!parseValue(out, err)) {
            return false;
        }
        skipWhitespace();
        if (pos_ < src_.size()) {
            err = "Extra trailing characters after JSON root at offset " + std::to_string(pos_);
            return false;
        }
        return true;
    }

private:
    const std::string& src_;
    size_t pos_;

    void skipWhitespace() {
        while (pos_ < src_.size() && (std::isspace(static_cast<unsigned char>(src_[pos_])))) {
            ++pos_;
        }
    }

    char peek() const {
        return pos_ < src_.size() ? src_[pos_] : '\0';
    }

    char get() {
        return pos_ < src_.size() ? src_[pos_++] : '\0';
    }

    bool parseValue(JsonValue& val, std::string& err) {
        skipWhitespace();
        char c = peek();
        if (c == '"') {
            return parseString(val, err);
        } else if (c == '{') {
            return parseObject(val, err);
        } else if (c == '[') {
            return parseArray(val, err);
        } else if (c == 't' || c == 'f') {
            return parseBool(val, err);
        } else if (c == 'n') {
            return parseNull(val, err);
        } else if (c == '-' || std::isdigit(static_cast<unsigned char>(c))) {
            return parseNumber(val, err);
        }
        err = std::string("Unexpected character '") + c + "' at position " + std::to_string(pos_);
        return false;
    }

    bool parseString(JsonValue& val, std::string& err) {
        if (get() != '"') {
            err = "Expected '\"' at start of string";
            return false;
        }
        std::string s;
        while (pos_ < src_.size()) {
            char c = get();
            if (c == '"') {
                val.type = JsonValue::STR;
                val.s = std::move(s);
                return true;
            }
            if (c == '\\') {
                if (pos_ >= src_.size()) {
                    err = "Unterminated escape sequence";
                    return false;
                }
                char esc = get();
                switch (esc) {
                    case '"':  s.push_back('"'); break;
                    case '\\': s.push_back('\\'); break;
                    case '/':  s.push_back('/'); break;
                    case 'b':  s.push_back('\b'); break;
                    case 'f':  s.push_back('\f'); break;
                    case 'n':  s.push_back('\n'); break;
                    case 'r':  s.push_back('\r'); break;
                    case 't':  s.push_back('\t'); break;
                    case 'u': {
                        for (int i = 0; i < 4 && pos_ < src_.size(); ++i) {
                            get();
                        }
                        s.push_back('?');
                        break;
                    }
                    default:
                        s.push_back(esc);
                        break;
                }
            } else {
                s.push_back(c);
            }
        }
        err = "Unterminated string literal";
        return false;
    }

    bool parseObject(JsonValue& val, std::string& err) {
        if (get() != '{') {
            err = "Expected '{'";
            return false;
        }
        val.type = JsonValue::OBJ;
        skipWhitespace();
        if (peek() == '}') {
            get();
            return true;
        }

        while (pos_ < src_.size()) {
            skipWhitespace();
            if (peek() != '"') {
                err = "Expected string key in object";
                return false;
            }
            JsonValue keyVal;
            if (!parseString(keyVal, err)) {
                return false;
            }
            skipWhitespace();
            if (get() != ':') {
                err = "Expected ':' after key in object";
                return false;
            }
            auto memberVal = std::make_shared<JsonValue>();
            if (!parseValue(*memberVal, err)) {
                return false;
            }
            val.obj.emplace_back(std::move(keyVal.s), std::move(memberVal));

            skipWhitespace();
            char c = get();
            if (c == '}') {
                return true;
            }
            if (c != ',') {
                err = "Expected ',' or '}' in object";
                return false;
            }
        }
        err = "Unterminated object";
        return false;
    }

    bool parseArray(JsonValue& val, std::string& err) {
        if (get() != '[') {
            err = "Expected '['";
            return false;
        }
        val.type = JsonValue::ARR;
        skipWhitespace();
        if (peek() == ']') {
            get();
            return true;
        }

        while (pos_ < src_.size()) {
            auto elem = std::make_shared<JsonValue>();
            if (!parseValue(*elem, err)) {
                return false;
            }
            val.arr.push_back(std::move(elem));
            skipWhitespace();
            char c = get();
            if (c == ']') {
                return true;
            }
            if (c != ',') {
                err = "Expected ',' or ']' in array";
                return false;
            }
        }
        err = "Unterminated array";
        return false;
    }

    bool parseBool(JsonValue& val, std::string& err) {
        if (src_.compare(pos_, 4, "true") == 0) {
            pos_ += 4;
            val.type = JsonValue::BOOL;
            val.b = true;
            return true;
        }
        if (src_.compare(pos_, 5, "false") == 0) {
            pos_ += 5;
            val.type = JsonValue::BOOL;
            val.b = false;
            return true;
        }
        err = "Invalid boolean literal";
        return false;
    }

    bool parseNull(JsonValue& val, std::string& err) {
        if (src_.compare(pos_, 4, "null") == 0) {
            pos_ += 4;
            val.type = JsonValue::NUL;
            return true;
        }
        err = "Invalid null literal";
        return false;
    }

    bool parseNumber(JsonValue& val, std::string& err) {
        size_t start = pos_;
        if (peek() == '-') ++pos_;
        while (pos_ < src_.size() && std::isdigit(static_cast<unsigned char>(src_[pos_]))) {
            ++pos_;
        }
        if (pos_ < src_.size() && src_[pos_] == '.') {
            ++pos_;
            while (pos_ < src_.size() && std::isdigit(static_cast<unsigned char>(src_[pos_]))) {
                ++pos_;
            }
        }
        if (pos_ < src_.size() && (src_[pos_] == 'e' || src_[pos_] == 'E')) {
            ++pos_;
            if (pos_ < src_.size() && (src_[pos_] == '+' || src_[pos_] == '-')) ++pos_;
            while (pos_ < src_.size() && std::isdigit(static_cast<unsigned char>(src_[pos_]))) {
                ++pos_;
            }
        }
        try {
            val.type = JsonValue::NUM;
            val.n = std::stod(src_.substr(start, pos_ - start));
            return true;
        } catch (...) {
            err = "Invalid number format";
            return false;
        }
    }
};

std::string escapeJson(const std::string& s) {
    std::ostringstream o;
    for (char c : s) {
        if (c == '"') o << "\\\"";
        else if (c == '\\') o << "\\\\";
        else if (c == '\b') o << "\\b";
        else if (c == '\f') o << "\\f";
        else if (c == '\n') o << "\\n";
        else if (c == '\r') o << "\\r";
        else if (c == '\t') o << "\\t";
        else o << c;
    }
    return o.str();
}

} // namespace

int main(int argc, char* argv[]) {
    bool output_json = false;
    bool output_to_string = false;
    std::string input_file;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--json") {
            output_json = true;
        } else if (arg == "--to-string") {
            output_to_string = true;
        } else if (arg == "--file" && i + 1 < argc) {
            input_file = argv[++i];
        } else if (arg == "-h" || arg == "--help") {
            std::cout << "Usage: graph_designer [options]\n"
                      << "Options:\n"
                      << "  --json         Output graph in JSON format\n"
                      << "  --to-string    Output raw graph.toString() format\n"
                      << "  --file <path>  Read JSON input from file instead of stdin\n"
                      << "  -h, --help     Display this help message\n";
            return 0;
        }
    }

    // Read JSON payload from stdin or file
    std::string json_content;
    if (!input_file.empty()) {
        std::ifstream ifs(input_file);
        if (!ifs) {
            std::cerr << "Error: Cannot open input file: " << input_file << "\n";
            return 1;
        }
        std::ostringstream ss;
        ss << ifs.rdbuf();
        json_content = ss.str();
    } else {
        std::ostringstream ss;
        ss << std::cin.rdbuf();
        json_content = ss.str();
    }

    if (json_content.empty()) {
        std::cerr << "Error: Empty input provided to Graph Designer.\n";
        return 1;
    }

    JsonValue root;
    std::string err;
    JsonParser parser(json_content);
    if (!parser.parse(root, err)) {
        std::cerr << "Error parsing JSON payload: " << err << "\n";
        return 1;
    }

    if (!root.isObject()) {
        std::cerr << "Error: Root JSON payload must be an object with 'nodes' and 'relationships'.\n";
        return 1;
    }

    graphs::Graph graph;

    // 1. Mandatory Node Registration: Register ALL scanned files as nodes
    auto nodes_val = root.get("nodes");
    if (nodes_val && nodes_val->isArray()) {
        for (const auto& item : nodes_val->arr) {
            if (item->isString()) {
                graph.addNode(graphs::Node::createFileNode(item->s));
            } else if (item->isObject()) {
                std::string path = item->getString("path");
                std::string lang = item->getString("language");
                if (!path.empty()) {
                    graph.addNode(graphs::Node::createFileNode(path, lang));
                }
            }
        }
    }

    // 2. Register Resolved Relationships
    auto rels_val = root.get("relationships");
    if (rels_val && rels_val->isArray()) {
        for (const auto& item : rels_val->arr) {
            if (!item->isObject()) continue;

            std::string src = item->getString("source");
            std::string tgt = item->getString("target");
            std::string type_str = item->getString("type", "REFERENCE");

            if (src.empty() || tgt.empty()) continue;

            graphs::RelationshipType rel_type = graphs::RelationshipType::REFERENCE;
            try {
                rel_type = graphs::stringToRelationshipType(type_str);
            } catch (...) {
                rel_type = graphs::RelationshipType::REFERENCE;
            }

            std::unordered_map<std::string, std::string> metadata;
            auto meta_val = item->get("metadata");
            if (meta_val && meta_val->isObject()) {
                for (const auto& kv : meta_val->obj) {
                    if (kv.second->isString()) {
                        metadata[kv.first] = kv.second->s;
                    }
                }
            }

            graph.addRelationship(src, tgt, rel_type, metadata);
        }
    }

    // 3. Render Output
    if (output_json) {
        std::cout << "{\n"
                  << "  \"node_count\": " << graph.nodeCount() << ",\n"
                  << "  \"edge_count\": " << graph.edgeCount() << ",\n"
                  << "  \"nodes\": [\n";

        std::vector<std::string> sorted_ids;
        sorted_ids.reserve(graph.getAllNodes().size());
        for (const auto& pair : graph.getAllNodes()) {
            sorted_ids.push_back(pair.first);
        }
        std::sort(sorted_ids.begin(), sorted_ids.end());

        for (size_t i = 0; i < sorted_ids.size(); ++i) {
            const auto* n = graph.getNode(sorted_ids[i]);
            std::cout << "    {\"id\": \"" << escapeJson(sorted_ids[i]) << "\", \"path\": \""
                      << escapeJson(n ? n->getFilePath() : "") << "\"}";
            if (i + 1 < sorted_ids.size()) std::cout << ",";
            std::cout << "\n";
        }
        std::cout << "  ],\n  \"edges\": [\n";

        size_t edge_idx = 0;
        size_t total_edges = graph.edgeCount();
        for (const auto& id : sorted_ids) {
            for (const auto& edge : graph.getOutgoingEdges(id)) {
                std::cout << "    {\n"
                          << "      \"source\": \"" << escapeJson(edge.getSourceId()) << "\",\n"
                          << "      \"target\": \"" << escapeJson(edge.getTargetId()) << "\",\n"
                          << "      \"type\": \"" << escapeJson(graphs::relationshipTypeToString(edge.getType())) << "\"";
                const auto& meta = edge.getMetadata();
                if (!meta.empty()) {
                    std::cout << ",\n      \"metadata\": {";
                    size_t m_idx = 0;
                    for (const auto& m : meta) {
                        std::cout << "\"" << escapeJson(m.first) << "\": \"" << escapeJson(m.second) << "\"";
                        if (++m_idx < meta.size()) std::cout << ", ";
                    }
                    std::cout << "}";
                }
                std::cout << "\n    }";
                if (++edge_idx < total_edges) std::cout << ",";
                std::cout << "\n";
            }
        }
        std::cout << "  ]\n}\n";
    } else if (output_to_string) {
        std::cout << graph.toString();
    } else {
        // Human-readable format matching Section 9 specification
        std::cout << "========================================\n"
                  << "GRAPH BUILDER\n"
                  << "========================================\n\n"
                  << "Graph contains " << graph.nodeCount() << " nodes and "
                  << graph.edgeCount() << " edges.\n\n";

        std::vector<std::string> sorted_ids;
        sorted_ids.reserve(graph.getAllNodes().size());
        for (const auto& pair : graph.getAllNodes()) {
            sorted_ids.push_back(pair.first);
        }
        std::sort(sorted_ids.begin(), sorted_ids.end());

        std::vector<std::string> isolated_nodes;

        for (const auto& id : sorted_ids) {
            const auto& outgoing = graph.getOutgoingEdges(id);
            const auto& incoming = graph.getIncomingEdges(id);

            if (!outgoing.empty()) {
                std::cout << id << "\n";
                for (const auto& edge : outgoing) {
                    std::cout << "    --" << graphs::relationshipTypeToString(edge.getType())
                              << "--> " << edge.getTargetId() << "\n";
                }
                std::cout << "\n";
            } else if (incoming.empty()) {
                isolated_nodes.push_back(id);
            }
        }

        if (!isolated_nodes.empty()) {
            std::cout << "Isolated nodes (no incoming/outgoing dependencies):\n";
            for (const auto& id : isolated_nodes) {
                std::cout << "  " << id << "\n";
            }
            std::cout << "\n";
        }
    }

    return 0;
}
