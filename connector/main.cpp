#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#endif

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

    // Build command to invoke python -m connector
    std::string cmd = "python -m connector \"" + path_str + "\"";
    for (int i = 2; i < argc; ++i) {
        cmd += " ";
        cmd += argv[i];
    }

    int result = std::system(cmd.c_str());
    return result;
}
