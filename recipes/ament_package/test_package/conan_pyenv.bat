@echo off
chcp 65001 > nul
@echo off


setlocal
echo @echo off > "%~dp0/deactivate_conan_pyenv.bat"
echo echo Restoring environment for conan_pyenv.bat >> "%~dp0/deactivate_conan_pyenv.bat"
for %%v in (PATH) do (
    set foundenvvar=
    for /f "delims== tokens=1,2" %%a in ('set') do (
        if /I "%%a" == "%%v" (
            echo set "%%a=%%b">> "%~dp0/deactivate_conan_pyenv.bat"
            set foundenvvar=1
        )
    )
    if not defined foundenvvar (
        echo set %%v=>> "%~dp0/deactivate_conan_pyenv.bat"
    )
)
endlocal




if defined PATH (
    set "PATH=%~dp0/conan_pyenv/Scripts;%PATH%"
) else (
    set "PATH=%~dp0/conan_pyenv/Scripts"
)