@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   酒店数据分析系统 - 安全构建 v4
echo   数据存储在项目根 data\ 永不受构建影响
echo ============================================
echo.

:: 0. 停止旧EXE
echo [1/4] 停止旧进程...
taskkill /f /im "酒店数据分析系统.exe" >nul 2>&1
timeout /t 2 /nobreak >nul
del /f "data\.lock" >nul 2>&1
echo       完成

:: 1. 构建前端
echo [2/4] 构建前端...
cd frontend
call npm run build
if %ERRORLEVEL% neq 0 (
    echo       前端构建失败!
    pause
    exit /b 1
)
cd ..
echo       完成

:: 2. 构建EXE（COLLECT直接覆盖dist/酒店数据分析系统/，数据在项目根不受影响）
echo [3/4] 构建EXE...
pyinstaller build.spec --noconfirm
if %ERRORLEVEL% neq 0 (
    echo       EXE构建失败!
    pause
    exit /b 1
)
echo       完成

:: 3. 清理dist中残留的data目录（数据已迁移至项目根data/）
echo [4/4] 清理...
if exist "dist\酒店数据分析系统\data" (
    rmdir /s /q "dist\酒店数据分析系统\data" 2>nul
    echo       已清理dist残留data目录
)
if exist "build" rmdir /s /q "build" 2>nul

echo.
echo ============================================
echo   构建完成！
echo   数据位置: data\hotel_data.db （项目根）
echo   dev和EXE共用，构建永不影响
echo ============================================
pause
