@echo off
chcp 65001 >nul 2>&1
title Go Write

set "ROOT=%~dp0"

echo ========================================
echo   Go Write
echo ========================================
echo.

REM --- 1. 检查运行环境 ---
if not exist "%ROOT%.venv\Scripts\python.exe" (
    echo Go Write 运行环境不存在，请先完成环境安装。
    echo.
    echo 需要：%ROOT%.venv\Scripts\python.exe
    pause
    exit /b 1
)

REM --- 2. 检查前端构建产物 ---
if not exist "%ROOT%07_工作台应用\ui\dist" (
    echo 正在构建 Go Write 前端界面...
    echo.
    cd /d "%ROOT%07_工作台应用\ui"
    if errorlevel 1 (
        echo 无法进入前端目录：%ROOT%07_工作台应用\ui
        pause
        exit /b 1
    )
    call npm run build
    if errorlevel 1 (
        echo.
        echo Go Write 前端构建失败，请检查 Node.js 和 npm 是否已安装。
        pause
        exit /b 1
    )
    echo.
    echo 前端构建完成。
    echo.
)

REM --- 3. 启动桌面程序 ---
cd /d "%ROOT%07_工作台应用"
if errorlevel 1 (
    echo 无法进入应用目录：%ROOT%07_工作台应用
    pause
    exit /b 1
)

"%ROOT%.venv\Scripts\python.exe" desktop\main.py
if errorlevel 1 (
    echo.
    echo Go Write 启动失败，请查看上方错误信息。
    pause
    exit /b 1
)
