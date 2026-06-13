#!/bin/bash
# Docker Hub 发布脚本 - Marine & Offshore Expert System
# ============================================================================
# 这个脚本会：
# 1. 构建 Docker 镜像
# 2. 优化镜像大小
# 3. 推送到 Docker Hub
# 4. 生成用户使用指南

set -e

echo "=========================================="
echo "  Docker Hub 发布工具"
echo "  Marine & Offshore Expert System"
echo "=========================================="
echo

# 配置变量
DOCKER_HUB_USERNAME="您的DockerHub账号"
IMAGE_NAME="marine-expert-system"
VERSION="${1:-latest}"

echo "📋 发布配置："
echo "   Docker Hub 用户名: $DOCKER_HUB_USERNAME"
echo "   镜像名称: $IMAGE_NAME"
echo "   版本标签: $VERSION"
echo

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ 错误：Docker 未运行"
    echo "请先启动 Docker Desktop"
    exit 1
fi

echo "✅ Docker 运行检查通过"
echo

# 检查是否已登录 Docker Hub
echo "🔐 检查 Docker Hub 登录状态..."
if ! docker info | grep -q "Username: $DOCKER_HUB_USERNAME"; then
    echo "❌ 未登录到 Docker Hub"
    echo "请先运行: docker login"
    echo "或: docker login -u $DOCKER_HUB_USERNAME"
    exit 1
fi

echo "✅ Docker Hub 登录检查通过"
echo

echo "=========================================="
echo "  开始构建 Docker 镜像"
echo "=========================================="
echo

# 构建 M8 镜像（轻量级版本，不含文档解析）
echo "📦 构建 M8 镜像（API Gateway + QA Engine）..."
docker build \
  -f deploy/Dockerfile \
  --target m8 \
  --tag ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${VERSION} \
  --tag ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:m8 \
  --build-arg DEPLOYMENT_MODE=personal \
  .

echo "✅ M8 镜像构建完成"
echo

# 显示镜像大小
echo "📊 镜像信息："
docker images ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${VERSION}
echo

# 估算压缩后大小（推送到 Docker Hub 后的大小）
UNCOMPRESSED_SIZE=$(docker images ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${VERSION} --format "{{.Size}}")
echo "压缩后预计大小: ~$(echo $UNCOMPRESSED_SIZE | sed 's/MB//') MB" \
     "(Docker 使用分层压缩，实际传输量更小)"
echo

echo "=========================================="
echo "  推送到 Docker Hub"
echo "=========================================="
echo

# 推送镜像
echo "📤 推送镜像到 Docker Hub..."
docker push ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${VERSION}

echo "✅ 镜像推送完成"
echo

# 如果是 latest 标签，也推送 m8 标签
if [ "$VERSION" = "latest" ]; then
    echo "📤 推送 m8 标签..."
    docker push ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:m8
    echo "✅ m8 标签推送完成"
    echo
fi

echo "=========================================="
echo "  ✅ 发布完成！"
echo "=========================================="
echo
echo "📦 Docker Hub 镜像地址："
echo "   https://hub.docker.com/r/${DOCKER_HUB_USERNAME}/${IMAGE_NAME}"
echo
echo "🚀 用户使用方法："
echo
echo "   # 拉取镜像"
echo "   docker pull ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${VERSION}"
echo
echo "   # 运行容器"
echo "   docker run -d \\"
echo "     -p 8000:8000 \\"
echo "     -v marine_data:/data \\"
echo "     ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:${VERSION}"
echo
echo "   # 访问"
echo "   echo API 文档: http://localhost:8000/docs"
echo
echo "📖 完整文档："
echo "   https://github.com/您的账号/marine-offshore-expert-system"
echo
