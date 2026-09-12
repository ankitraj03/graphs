#include "file_scanner.h"

#include <iostream>
#include <string>

int main(int argc, char* argv[]) {
    std::string path_str;

    if (argc > 1) {
        path_str = argv[1];
    } else {
        std::cout << "Enter repository path: ";
        if (!std::getline(std::cin, path_str) || path_str.empty()) {
            std::cerr << "\nError: No path provided.\n";
            return 1;
        }
    }

    // Strip surrounding quotes if the user pasted a quoted path
    if (!path_str.empty() && (path_str.front() == '"' || path_str.front() == '\'')) {
        path_str.erase(0, 1);
    }
    if (!path_str.empty() && (path_str.back() == '"' || path_str.back() == '\'')) {
        path_str.pop_back();
    }

    const std::filesystem::path root(path_str);
    graphs::FileScanner scanner;

    const auto files = scanner.scan(root);

    std::cout << "\nFound files:\n\n";
    for (const auto& file : files) {
        // Output with forward slashes for clean, uniform formatting
        std::cout << file.generic_string() << "\n";
    }

    std::cout << "\nTotal files: " << files.size() << "\n";
    return 0;
}
