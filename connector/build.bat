@echo off
setlocal
echo ======================================================================
echo Building Connector executable (connector.exe)...
echo ======================================================================

pushd "%~dp0"

where g++ >nul 2>&1
if not errorlevel 1 (
    echo Compiling connector.exe using g++...
    g++ -O2 -s main.cpp -o connector.exe
    if errorlevel 1 (
        echo Error: g++ compilation failed.
        popd
        exit /b 1
    )
    copy /y connector.exe ..\connector.exe >nul
    echo Build successful using g++!
    popd
    exit /b 0
)

where cl >nul 2>&1
if not errorlevel 1 (
    echo Compiling connector.exe using MSVC cl...
    cl /nologo /EHsc /std:c++17 /O2 main.cpp /Fe:connector.exe
    if errorlevel 1 (
        echo Error: MSVC compilation failed.
        popd
        exit /b 1
    )
    copy /y connector.exe ..\connector.exe >nul
    echo Build successful using MSVC!
    popd
    exit /b 0
)

echo Error: Neither g++ nor cl.exe compiler found in PATH.
popd
exit /b 1
