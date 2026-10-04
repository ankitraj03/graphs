@echo off
setlocal
echo ======================================================================
echo Building Graph Designer...
echo ======================================================================

pushd "%~dp0"

where g++ >nul 2>&1
if not errorlevel 1 (
    echo Compiling test_graph.exe using g++...
    g++ -std=c++14 -O2 -Iinclude src\relationship_type.cpp src\node.cpp src\edge.cpp src\graph.cpp tests\test_graph.cpp -o test_graph.exe
    if errorlevel 1 (
        echo Error compiling test_graph.exe with g++
        popd
        exit /b 1
    )

    echo Compiling basic_graph.exe using g++...
    g++ -std=c++14 -O2 -Iinclude src\relationship_type.cpp src\node.cpp src\edge.cpp src\graph.cpp examples\basic_graph.cpp -o basic_graph.exe
    if errorlevel 1 (
        echo Error compiling basic_graph.exe with g++
        popd
        exit /b 1
    )

    echo Compiling graph_designer.exe using g++...
    g++ -std=c++14 -O2 -Iinclude src\relationship_type.cpp src\node.cpp src\edge.cpp src\graph.cpp main.cpp -o graph_designer.exe
    if errorlevel 1 (
        echo Error compiling graph_designer.exe with g++
        popd
        exit /b 1
    )
    copy /y graph_designer.exe ..\graph_designer.exe >nul

    echo.
    echo ======================================================================
    echo Build successful using g++!
    echo   Test runner: test_graph.exe
    echo   CLI tool:    graph_designer.exe
    echo   Example:     basic_graph.exe
    echo ======================================================================
    popd
    exit /b 0
)

where cl >nul 2>&1
if errorlevel 1 (
    if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
        call "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
    )
)

where cl >nul 2>&1
if not errorlevel 1 (
    echo Compiling test_graph.exe using MSVC cl...
    cl /nologo /EHsc /std:c++17 /O2 /W4 /Iinclude src\relationship_type.cpp src\node.cpp src\edge.cpp src\graph.cpp tests\test_graph.cpp /Fe:test_graph.exe
    if errorlevel 1 (
        echo Error compiling test_graph.exe with MSVC
        popd
        exit /b 1
    )

    echo Compiling basic_graph.exe using MSVC cl...
    cl /nologo /EHsc /std:c++17 /O2 /W4 /Iinclude src\relationship_type.cpp src\node.cpp src\edge.cpp src\graph.cpp examples\basic_graph.cpp /Fe:basic_graph.exe
    if errorlevel 1 (
        echo Error compiling basic_graph.exe with MSVC
        popd
        exit /b 1
    )

    echo Compiling graph_designer.exe using MSVC cl...
    cl /nologo /EHsc /std:c++17 /O2 /W4 /Iinclude src\relationship_type.cpp src\node.cpp src\edge.cpp src\graph.cpp main.cpp /Fe:graph_designer.exe
    if errorlevel 1 (
        echo Error compiling graph_designer.exe with MSVC
        popd
        exit /b 1
    )

    echo.
    echo ======================================================================
    echo Build successful using MSVC!
    echo   Test runner: test_graph.exe
    echo   CLI tool:    graph_designer.exe
    echo   Example:     basic_graph.exe
    echo ======================================================================
    popd
    exit /b 0
)

echo Error: Neither g++ nor cl compiler found in PATH.
popd
exit /b 1
