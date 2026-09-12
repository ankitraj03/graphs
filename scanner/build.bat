@echo off
setlocal
echo ======================================================================
echo Building C++ FileScanner using MSVC (C++17)...
echo ======================================================================

call "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
if errorlevel 1 (
    echo Error: Could not initialize MSVC vcvars64.bat environment.
    exit /b 1
)

pushd "%~dp0"
echo Compiling scanner.exe...
cl /nologo /EHsc /std:c++17 /O2 /W4 file_scanner.cpp main.cpp /Fe:scanner.exe
if errorlevel 1 (
    echo Error compiling scanner.exe
    popd
    exit /b 1
)

echo Compiling test_scanner.exe...
cl /nologo /EHsc /std:c++17 /O2 /W4 file_scanner.cpp test_scanner.cpp /Fe:test_scanner.exe
if errorlevel 1 (
    echo Error compiling test_scanner.exe
    popd
    exit /b 1
)

echo.
echo ======================================================================
echo Build successful!
echo   Executable: scanner.exe
echo   Test runner: test_scanner.exe
echo ======================================================================
popd
exit /b 0
