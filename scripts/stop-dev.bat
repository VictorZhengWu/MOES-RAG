@echo off
chcp 65001 >nul
title MOES Dev Stopper
echo ============================================
echo   停止 MOES 开发测试环境
echo ============================================
echo.

echo [1/2] 停止后端 Docker 服务...
cd /d "E:\myCode\RAG\deploy\personal"
docker compose down
echo       后端已停止（数据保留在 volume，下次启动不丢失）

echo.
echo [2/2] 前端 M6/M7 请手动关闭：
echo   - 关闭标题为 "M6 User Portal (3000)" 的窗口
echo   - 关闭标题为 "M7 Admin Portal (3001)" 的窗口
echo   （或在各自窗口按 Ctrl+C）

echo.
echo ============================================
echo   全部停止完成
echo ============================================
pause
