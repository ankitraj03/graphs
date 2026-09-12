#include "file_scanner.h"

#include <cassert>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>

namespace fs = std::filesystem;

int main() {
    std::cout << "Running C++ FileScanner unit test suite...\n";

    // Create a temporary sandbox directory
    const fs::path temp_root = fs::temp_directory_path() / "graphs_scanner_test_sandbox";
    std::error_code ec;
    fs::remove_all(temp_root, ec);
    fs::create_directories(temp_root, ec);

    // Build directory structure:
    // temp_root/
    // ├── src/
    // │   ├── main.cpp
    // │   ├── database.cpp
    // │   └── user.py
    // ├── include/
    // │   ├── database.h
    // │   └── user.h
    // ├── tests/
    // │   ├── test.cpp
    // │   └── UPPER.CPP          (case-insensitive test)
    // ├── frontend/
    // │   ├── app.ts
    // │   └── index.jsx
    // ├── build/                 (ignored directory)
    // │   └── output.cpp
    // ├── .git/                  (ignored directory)
    // │   └── tracked.py
    // ├── node_modules/          (ignored directory)
    // │   └── lib.js
    // ├── __pycache__/           (ignored directory)
    // │   └── cache.py
    // ├── README.md              (unsupported extension)
    // └── image.png              (unsupported extension)

    fs::create_directories(temp_root / "src", ec);
    fs::create_directories(temp_root / "include", ec);
    fs::create_directories(temp_root / "tests", ec);
    fs::create_directories(temp_root / "frontend", ec);
    fs::create_directories(temp_root / "build", ec);
    fs::create_directories(temp_root / ".git", ec);
    fs::create_directories(temp_root / "node_modules", ec);
    fs::create_directories(temp_root / "__pycache__", ec);

    // Create dummy files (empty files just to test filesystem path discovery)
    const auto touch = [](const fs::path& p) {
        std::ofstream ofs(p);
        ofs << " ";
    };

    touch(temp_root / "src" / "main.cpp");
    touch(temp_root / "src" / "database.cpp");
    touch(temp_root / "src" / "user.py");
    touch(temp_root / "include" / "database.h");
    touch(temp_root / "include" / "user.h");
    touch(temp_root / "tests" / "test.cpp");
    touch(temp_root / "tests" / "UPPER.CPP");
    touch(temp_root / "frontend" / "app.ts");
    touch(temp_root / "frontend" / "index.jsx");

    // Ignored directory files
    touch(temp_root / "build" / "output.cpp");
    touch(temp_root / ".git" / "tracked.py");
    touch(temp_root / "node_modules" / "lib.js");
    touch(temp_root / "__pycache__" / "cache.py");

    // Unsupported files
    touch(temp_root / "README.md");
    touch(temp_root / "image.png");

    graphs::FileScanner scanner;
    const auto discovered = scanner.scan(temp_root);

    std::cout << "Discovered " << discovered.size() << " source files.\n";

    // Expected exactly 9 files (main.cpp, database.cpp, user.py, database.h, user.h, test.cpp, UPPER.CPP, app.ts, index.jsx)
    if (discovered.size() != 9) {
        std::cerr << "FAIL: Expected 9 files, but got " << discovered.size() << "\n";
        for (const auto& f : discovered) {
            std::cerr << "  " << f.string() << "\n";
        }
        fs::remove_all(temp_root, ec);
        return 1;
    }

    // Verify none of the ignored or unsupported files are present
    for (const auto& path : discovered) {
        const std::string s = path.generic_string();
        assert(s.find("build") == std::string::npos && "build/ should be ignored");
        assert(s.find(".git") == std::string::npos && ".git/ should be ignored");
        assert(s.find("node_modules") == std::string::npos && "node_modules/ should be ignored");
        assert(s.find("__pycache__") == std::string::npos && "__pycache__/ should be ignored");
        assert(s.find("README.md") == std::string::npos && "README.md should not be included");
        assert(s.find("image.png") == std::string::npos && "image.png should not be included");
    }

    // Verify sorted determinism
    for (size_t i = 1; i < discovered.size(); ++i) {
        assert(discovered[i - 1] < discovered[i] && "Results must be strictly sorted");
    }

    // Test non-existent path error handling
    const auto missing_results = scanner.scan(temp_root / "does_not_exist_at_all");
    assert(missing_results.empty() && "Non-existent path must return empty vector");

    // Clean up temporary sandbox
    fs::remove_all(temp_root, ec);

    std::cout << "ALL C++ SCANNER TESTS PASSED SUCCESSFULLY! [OK]\n";
    return 0;
}
