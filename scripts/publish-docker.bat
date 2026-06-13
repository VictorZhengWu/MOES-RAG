@echo off
REM Docker Hub 发布脚本 (Windows) - Marine & Offshore Expert System
REM ============================================================================

setlocal

echo ==========================================
echo   Docker Hub 发布工具 (Windows)
echo   Marine & Offshore Expert System
echo ==========================================
echo.

REM 配置变量（请修改为您的实际信息）
set DOCKER_HUB_USERNAME=您的DockerHub账号
set IMAGE_NAME=marine-expert-system
set VERSION=%1
if "%VERSION%"=="" set VERSION=latest

echo 📋 发布配置：
echo    Docker Hub 用户名: %DOCKER_HUB_USERNAME%
echo    镜像名称: %IMAGE_NAME%
echo    版本标签: %VERSION%
echo.

REM 检查 Docker 是否运行
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误：Docker 未运行
    echo 请先启动 Docker Desktop
    pause
    exit /b 1
)

echo ✅ Docker 运行检查通过
echo.

REM 构建 M8 镜像
echo ==========================================
echo   开始构建 Docker 镜像
echo ==========================================
echo.

echo 📦 构建 M8 镜像（API Gateway + QA Engine）...
docker build ^
  -f deploy/Dockerfile ^
  --target m8 ^
  --tag %DOCKER_HUB_USERNAME%/%IMAGE_NAME%:%VERSION% ^
  --tag %DOCKER_HUB_USERNAME%/%IMAGE_NAME%:m8 ^
  --build-arg DEPLOYMENT_MODE=personal ^
  .

if %errorlevel% neq 0 (
    echo ❌ 构建失败
    pause
    exit /b 1
)

echo ✅ M8 镜像构建完成
echo.

REM 显示镜像大小
echo 📊 镜像信息：
docker images %DOCKER_HUB_USERNAME%/%IMAGE_NAME%:%VERSION%
echo.

REM 推送镜像
echo ==========================================
echo   推送到 Docker Hub
echo ==========================================
echo.

echo 📤 推送镜像到 Docker Hub...
docker push %DOCKER_HUB_USERNAME%/%IMAGE_NAME%:%VERSION%

if %errorlevel% neq 0 (
    echo ❌ 推送失败
    echo 请检查是否已登录: docker login
    pause
    exit /b 1
)

echo ✅ 镜像推送完成
echo.

if "%VERSION%"=="latest" (
    echo 📤 推送 m8 标签...
    docker push %DOCKER_HUB_USERNAME%/%IMAGE_NAME%:m8
    echo ✅ m8 标签推送完成
    echo.
)

echo ==========================================
echo   ✅ 发布完成！
echo ==========================================
echo.
echo 📦 Docker Hub 镜像地址：
echo    https://hub.docker.com/r/%DOCKER_HUB_USERNAME%/%IMAGE_NAME%
echo.
echo 🚀 用户使用方法：
echo.
echo    # 拉取镜像
echo    docker pull %DOCKER_HUB_USERNAME%/%IMAGE_NAME%:%VERSION%
echo.
echo    # 运行容器
echo    docker run -d -p 8000:8000 %DOCKER_HUB_USERNAME%/%IMAGE_NAME%:%VERSION%
echo.
echo    # 访问 API 文档
echo    start http://localhost:8000/docs
echo.

pause
