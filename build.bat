@echo off
chcp 65001 >nul
echo ========================================
echo   MathFlow - PyInstaller 一键打包
echo ========================================
echo.

REM 检查 PyInstaller 是否安装
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] 正在安装 PyInstaller...
    pip install pyinstaller
)

echo [INFO] 开始打包...
echo.

pyinstaller --clean --onefile --noconsole --strip ^
    --name MathFlow ^
    --icon=icon.ico ^
    --hidden-import ttkbootstrap ^
    --collect-data ttkbootstrap ^
    --collect-data latex2mathml ^
    --exclude-module numpy ^
    --exclude-module scipy ^
    --exclude-module matplotlib ^
    --exclude-module pandas ^
    --exclude-module PIL.ImageQt ^
    --exclude-module unittest ^
    --exclude-module test ^
    --exclude-module setuptools ^
    --exclude-module pip ^
    --exclude-module distutils ^
    --exclude-module xmlrpc ^
    --exclude-module ftplib ^
    --exclude-module http.server ^
    --exclude-module pydoc ^
    --exclude-module doctest ^
    --exclude-module tkinter.test ^
    --exclude-module lib2to3 ^
    --exclude-module multiprocessing ^
    math2mathml.py

echo.
if exist "dist\MathFlow.exe" (
    echo ========================================
    echo   打包完成！
    echo   输出: dist\MathFlow.exe
    for %%A in ("dist\MathFlow.exe") do echo   大小: %%~zA bytes
    echo ========================================
) else (
    echo [ERROR] 打包失败，请检查上面的错误信息。
)
pause
