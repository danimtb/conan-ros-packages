@echo off
chcp 65001 > nul
@echo off


setlocal
echo @echo off > "%~dp0/deactivate_conanbuildenv.bat"
echo echo Restoring environment for conanbuildenv.bat >> "%~dp0/deactivate_conanbuildenv.bat"
for %%v in (PYTHONPATH) do (
    set foundenvvar=
    for /f "delims== tokens=1,2" %%a in ('set') do (
        if /I "%%a" == "%%v" (
            echo set "%%a=%%b">> "%~dp0/deactivate_conanbuildenv.bat"
            set foundenvvar=1
        )
    )
    if not defined foundenvvar (
        echo set %%v=>> "%~dp0/deactivate_conanbuildenv.bat"
    )
)
endlocal




if defined PYTHONPATH (
    set "PYTHONPATH=C:\Users\danielm\repos\conan-ros-kilted\.conan2\p\b\ament2ff9df291db29\f;%PYTHONPATH%"
) else (
    set "PYTHONPATH=C:\Users\danielm\repos\conan-ros-kilted\.conan2\p\b\ament2ff9df291db29\f"
)