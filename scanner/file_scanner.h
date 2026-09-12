#pragma once

#include <filesystem>
#include <string>
#include <string_view>
#include <unordered_set>
#include <vector>

namespace graphs {

/**
 * @brief High-throughput recursive file scanner for Phase 2.
 *
 * Traverses a repository root directory, skips ignored directories (e.g. .git,
 * build, node_modules, __pycache__), and collects paths of supported source files
 * based on case-insensitive extension matching.
 *
 * Architectural constraints:
 * - Discovers and returns paths ONLY.
 * - Does NOT read, parse, or tokenize file contents.
 * - Does NOT perform multithreading or caching (baseline implementation).
 * - Guarantees deterministic, sorted output.
 */
class FileScanner {
public:
    /// Default constructor with standard source extensions and ignored directories.
    FileScanner();

    /// Constructor with caller-customized extensions and ignored directories.
    FileScanner(std::unordered_set<std::string> supported_extensions,
                std::unordered_set<std::string> ignored_directories);

    /**
     * @brief Recursively scan a directory tree and discover supported source files.
     * @param root The root directory path to scan.
     * @return Sorted vector of discovered matching file paths.
     */
    std::vector<std::filesystem::path> scan(const std::filesystem::path& root) const;

    /// Checks if a given file path has a supported source extension (case-insensitive).
    bool is_supported_extension(const std::filesystem::path& path) const;

    /// Checks if a directory filename should be ignored and pruned from traversal.
    bool is_ignored_directory(const std::filesystem::path& dir_path) const;

    /// Returns the read-only set of supported extensions (e.g. ".cpp", ".py", ".ts").
    const std::unordered_set<std::string>& get_supported_extensions() const noexcept;

    /// Returns the read-only set of ignored directory names (e.g. ".git", "node_modules").
    const std::unordered_set<std::string>& get_ignored_directories() const noexcept;

    /// Adds a supported file extension (normalized to lowercase with leading dot).
    void add_supported_extension(std::string extension);

    /// Removes a supported file extension.
    void remove_supported_extension(const std::string& extension);

    /// Adds a directory name to the ignore set (normalized to lowercase).
    void add_ignored_directory(std::string dir_name);

    /// Removes a directory name from the ignore set.
    void remove_ignored_directory(const std::string& dir_name);

private:
    std::unordered_set<std::string> supported_extensions_;
    std::unordered_set<std::string> ignored_directories_;

    static std::string to_lower(std::string_view str);
    static std::string normalize_extension(std::string_view ext);
};

} // namespace graphs

// Convenience alias for top-level usage
using graphs::FileScanner;
