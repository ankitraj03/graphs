#include "file_scanner.h"

#include <algorithm>
#include <cctype>
#include <iostream>

namespace graphs {

FileScanner::FileScanner()
    : supported_extensions_{
          // Python
          ".py",
          ".pyi",
          // C / C++
          ".c",
          ".cpp",
          ".cc",
          ".cxx",
          ".h",
          ".hpp",
          ".hxx",
          // JavaScript / TypeScript
          ".js",
          ".jsx",
          ".ts",
          ".tsx",
          ".mjs",
          ".cjs",
      },
      ignored_directories_{
          ".git",
          ".vscode",
          "node_modules",
          "build",
          "dist",
          "bin",
          "obj",
          "__pycache__",
      } {}

FileScanner::FileScanner(std::unordered_set<std::string> supported_extensions,
                         std::unordered_set<std::string> ignored_directories) {
    for (const auto& ext : supported_extensions) {
        supported_extensions_.insert(normalize_extension(ext));
    }
    for (const auto& dir : ignored_directories) {
        ignored_directories_.insert(to_lower(dir));
    }
}

std::vector<std::filesystem::path> FileScanner::scan(const std::filesystem::path& root) const {
    std::vector<std::filesystem::path> results;
    std::error_code ec;

    // 1. Verify existence of root path
    if (!std::filesystem::exists(root, ec) || ec) {
        std::cerr << "FileScanner error: Root path does not exist: " << root.string() << '\n';
        return results;
    }

    // 2. Verify root is a directory
    if (!std::filesystem::is_directory(root, ec) || ec) {
        std::cerr << "FileScanner error: Root path is not a directory: " << root.string() << '\n';
        return results;
    }

    // 3. Recursive directory traversal with permission skipping
    const auto opts = std::filesystem::directory_options::skip_permission_denied;
    auto it = std::filesystem::recursive_directory_iterator(root, opts, ec);
    if (ec) {
        std::cerr << "FileScanner error: Cannot access root directory: " << root.string()
                  << " (" << ec.message() << ")\n";
        return results;
    }

    const auto end = std::filesystem::recursive_directory_iterator();
    while (it != end) {
        const auto& entry = *it;

        std::error_code entry_ec;
        const bool is_dir = entry.is_directory(entry_ec);

        if (entry_ec) {
            // Inaccessible entry, advance iterator and clear error
            it.increment(ec);
            if (ec) {
                ec.clear();
            }
            continue;
        }

        if (is_dir) {
            // Prune ignored directories immediately to avoid recursing into them
            if (is_ignored_directory(entry.path())) {
                it.disable_recursion_pending();
            }
        } else {
            const bool is_reg = entry.is_regular_file(entry_ec);
            if (!entry_ec && is_reg) {
                if (is_supported_extension(entry.path())) {
                    results.push_back(entry.path());
                }
            }
        }

        it.increment(ec);
        if (ec) {
            // Skip inaccessible children or transient filesystem changes
            ec.clear();
        }
    }

    // 4. Sort results lexicographically for deterministic output
    std::sort(results.begin(), results.end());

    return results;
}

bool FileScanner::is_supported_extension(const std::filesystem::path& path) const {
    std::string ext = normalize_extension(path.extension().string());
    return supported_extensions_.find(ext) != supported_extensions_.end();
}

bool FileScanner::is_ignored_directory(const std::filesystem::path& dir_path) const {
    std::string name = to_lower(dir_path.filename().string());
    return ignored_directories_.find(name) != ignored_directories_.end();
}

const std::unordered_set<std::string>& FileScanner::get_supported_extensions() const noexcept {
    return supported_extensions_;
}

const std::unordered_set<std::string>& FileScanner::get_ignored_directories() const noexcept {
    return ignored_directories_;
}

void FileScanner::add_supported_extension(std::string extension) {
    supported_extensions_.insert(normalize_extension(extension));
}

void FileScanner::remove_supported_extension(const std::string& extension) {
    supported_extensions_.erase(normalize_extension(extension));
}

void FileScanner::add_ignored_directory(std::string dir_name) {
    ignored_directories_.insert(to_lower(dir_name));
}

void FileScanner::remove_ignored_directory(const std::string& dir_name) {
    ignored_directories_.erase(to_lower(dir_name));
}

std::string FileScanner::to_lower(std::string_view str) {
    std::string lower;
    lower.reserve(str.size());
    for (const char c : str) {
        lower.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
    }
    return lower;
}

std::string FileScanner::normalize_extension(std::string_view ext) {
    std::string normalized = to_lower(ext);
    if (!normalized.empty() && normalized.front() != '.') {
        normalized.insert(normalized.begin(), '.');
    }
    return normalized;
}

} // namespace graphs
