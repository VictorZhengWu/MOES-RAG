@echo off
REM ============================================================================
REM  全功能开发测试一键启动脚本
REM  启动：后端 Docker(M8) + 前端 M6 用户门户 + M7 管理门户
REM  使用：双击运行（需先启动 Docker Desktop）
REM ============================================================================
chcp 65001 >nul
title MOES Dev Launcher

echo ============================================
echo   Marine ^& Offshore Expert System - 开发测试环境
echo ============================================
echo.

REM 检查 Docker 是否运行
echo [1/4] 检查 Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Docker 未运行！
    echo 请先从开始菜单启动 Docker Desktop，等待鲸鱼图标稳定后再运行本脚本。
    pause
    exit /b 1
)
echo       Docker 正常

REM 启动后端 Docker 服务
echo [2/4] 启动后端服务 (M8 API + Redis + Meilisearch)...
cd /d "E:\myCode\RAG\deploy\personal"
docker compose up -d
if %errorlevel% neq 0 (
    echo [错误] 后端启动失败
    pause
    exit /b 1
)

REM 启动 M6 用户门户 (新窗口)
echo [3/4] 启动 M6 用户门户 (端口 3000)...
start "M6 User Portal (3000)" cmd /k "cd /d E:\myCode\RAG\m6-user-portal && set NEXT_PUBLIC_API_URL=http://localhost:18000 && npm run dev"

REM 启动 M7 管理门户 (新窗口)
echo [4/4] 启动 M7 管理门户 (端口 3001)...
start "M7 Admin Portal (3001)" cmd /k "cd /d E:\myCode\RAG\m7-admin-portal && set NEXT_PUBLIC_API_URL=http://localhost:18000 && npm run dev"

echo.
echo ============================================
echo   全部启动指令已发出！
echo.
echo   [访问地址]
echo   用户门户:   http://localhost:3000
echo   管理门户:   http://localhost:3001
echo   API 文档:   http://localhost:18000/docs
echo.
echo   [获取 Admin Key] (首次需要，用于登录 M7)
echo   docker exec marine-m8 cat /data/admin_key.txt
echo.
echo   [等待提示]
echo   - 后端约 30 秒就绪
echo   - 前端首次编译需 30-60 秒，请耐心等待
echo   - 两个前端窗口请保持打开，关闭即停止该前端
echo ============================================
echo.
echo 正在打开管理门户...
timeout /t 35 >nul
start http://localhost:3001
pause
