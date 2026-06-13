#!/bin/bash
# GitHub 发布脚本 - Marine & Offshore Expert System
# ============================================================================
# 这个脚本会：
# 1. 检查 .gitignore 配置
# 2. 计算排除大文件后的仓库大小
# 3. 提示 GitHub 发布步骤

set -e

echo "=========================================="
echo "  GitHub 发布准备工具"
echo "  Marine & Offshore Expert System"
echo "=========================================="
echo

# 检查 git 状态
if [ ! -d ".git" ]; then
    echo "❌ 错误：这不是一个 Git 仓库"
    echo "请先运行: git init"
    exit 1
fi

echo "✅ Git 仓库检查通过"
echo

# 检查 .gitignore
if [ ! -f ".gitignore" ]; then
    echo "❌ 错误：缺少 .gitignore 文件"
    exit 1
fi

echo "✅ .gitignore 配置检查通过"
echo

# 显示当前仓库大小
echo "📊 当前仓库内容统计："
echo "源代码行数: $(find . -name '*.py' -o -name '*.ts' -o -name '*.tsx' | xargs wc -l 2>/dev/null | tail -1)"
echo

# 估算提交后的大小（排除 gitignore 的文件）
echo "📦 估算 GitHub 仓库大小："
# 创建临时目录来测试
TEMP_DIR=$(mktemp -d)
mkdir -p "$TEMP_DIR/test"
rsync -av --exclude-from=.gitignore . "$TEMP_DIR/test/" > /dev/null 2>&1
SIZE=$(du -sh "$TEMP_DIR/test" | cut -f1)
echo "预计上传大小: $SIZE（不含 Git 对象开销）"
rm -rf "$TEMP_DIR"
echo

echo "=========================================="
echo "  下一步：发布到 GitHub"
echo "=========================================="
echo
echo "1️⃣  在 GitHub 创建新仓库："
echo "   访问: https://github.com/new"
echo "   仓库名: marine-offshore-expert-system"
echo "   设置为 Public（公开）"
echo
echo "2️⃣  添加远程仓库并推送："
echo "   git remote add origin https://github.com/您的账号/marine-offshore-expert-system.git"
echo "   git branch -M master"
echo "   git push -u origin master"
echo
echo "3️⃣  或者使用 GitHub CLI（更快）："
echo "   gh repo create marine-offshore-expert-system --public --source=. --remote=origin --push"
echo
echo "=========================================="
echo "  ⚠️  重要提示"
echo "=========================================="
echo
echo "❌ 不要上传:"
echo "   - node_modules/（NPM 依赖）"
echo "   - venv/（Python 虚拟环境）"
echo "   - data/（数据库文件）"
echo "   - models/（大模型权重文件）"
echo "   - *.db（数据库文件）"
echo
echo "✅ 应该上传:"
echo "   - 所有源代码（.py, .ts, .tsx）"
echo "   - 配置文件（.yaml, .json）"
echo "   - 文档（.md）"
echo "   - Dockerfile 和 docker-compose.yml"
echo
echo "如果上传后仓库 > 1GB，请检查是否遗漏了 .gitignore 规则"
echo
