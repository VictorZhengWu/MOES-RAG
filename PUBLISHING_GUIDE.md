# Marine & Offshore Expert System — 发布指南

> **目标受众**: 项目维护者、发布经理
> **目的**: 将项目发布给最终用户

---

## 📋 目录

1. [发布策略](#发布策略)
2. [准备检查清单](#准备检查清单)
3. [方式一：发布到 GitHub](#方式一发布到-github)
4. [方式二：发布到 Docker Hub](#方式二发布到-docker-hub)
5. [用户下载指南](#用户下载指南)
6. [版本管理](#版本管理)

---

## 发布策略

### 推荐方案：双渠道发布

```
┌─────────────────────────────────────────────────────────────┐
│                    Marine Expert System                       │
│                                                              │
│  ┌──────────────────┐              ┌──────────────────┐     │
│  │   GitHub 仓库    │              │   Docker Hub     │     │
│  │                  │              │                  │     │
│  │  • 源代码        │              │  • Docker 镜像   │     │
│  │  • 文档          │              │  • 开箱即用      │     │
│  │  • 50-100 MB     │              │  • 2-3 GB        │     │
│  │                  │              │                  │     │
│  │  👨‍💻 开发者      │              │  👥 最终用户      │     │
│  └──────────────────┘              └──────────────────┘     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 为什么需要两个渠道？

| 渠道 | 目标用户 | 用途 | 大小 |
|------|---------|------|------|
| **GitHub** | 开发者、贡献者 | 查看源码、自行构建、二次开发 | ~50-100 MB |
| **Docker Hub** | 最终用户、运维 | 开箱即用、快速部署 | ~2-3 GB |

---

## 准备检查清单

发布前请确认：

### ✅ 代码质量

- [ ] 所有测试通过（`python -m pytest`）
- [ ] 代码审查完成
- [ ] 无硬编码、无占位符
- [ ] 文档更新（README, CHANGELOG）

### ✅ 安全检查

- [ ] 无敏感信息（API Key、密码）
- [ ] .gitignore 配置正确
- [ ] 环境变量模板已提供

### ✅ 发布材料

- [ ] 版本号确定（如 v1.0.0）
- [ ] 发布说明（RELEASE.md）
- [ ] 用户文档完整

---

## 方式一：发布到 GitHub

### 目标

将源代码发布到 GitHub，供开发者查看和贡献。

### 步骤

#### 1. 检查 .gitignore 配置

确认 `.gitignore` 已正确配置，排除：
- `node_modules/`（NPM 依赖）
- `venv/`（Python 虚拟环境）
- `data/`（数据库文件）
- `models/`（大模型权重）
- `*.db`、`*.sqlite`（数据库文件）

#### 2. 估算仓库大小

运行检查脚本：
```bash
bash scripts/publish-github.sh
```

这会显示：
- 源代码行数
- 预计上传大小
- 下一步操作指南

#### 3. 创建 GitHub 仓库

**方式 A - 使用 GitHub CLI（推荐）**：

```bash
# 安装 GitHub CLI
# Windows: winget install GitHub.cli
# Mac: brew install gh

# 登录
gh auth login

# 创建仓库并推送
gh repo create marine-offshore-expert-system \
  --public \
  --source=. \
  --remote=origin \
  --push
```

**方式 B - 手动创建**：

1. 访问 https://github.com/new
2. 仓库名：`marine-offshore-expert-system`
3. 设置为 **Public**（公开）
4. **不要**勾选 "Initialize with README"
5. 点击 "Create repository"
6. 复制显示的命令，在项目目录运行：
   ```bash
   git remote add origin https://github.com/您的账号/marine-offshore-expert-system.git
   git branch -M master
   git push -u origin master
   ```

#### 4. 验证发布

访问您的 GitHub 仓库：
```
https://github.com/您的账号/marine-offshore-expert-system
```

检查：
- ✅ 文件列表正确（无 node_modules、venv 等大文件夹）
- ✅ README.md 显示正常
- ✅ 文件大小合理（应该 < 100 MB）

#### 5. 创建 Release（可选）

为稳定版本创建 GitHub Release：

```bash
# 使用 GitHub CLI
gh release create v1.0.0 \
  --title "v1.0.0 - Initial Release" \
  --notes "See CHANGELOG.md for details"
```

或手动在 GitHub 网页上：
1. 访问仓库 → "Releases"
2. 点击 "Draft a new release"
3. 填写版本号和发布说明
4. 点击 "Publish release"

---

## 方式二：发布到 Docker Hub

### 目标

构建并发布 Docker 镜像，让用户开箱即用。

### 步骤

#### 1. 注册 Docker Hub 账号

1. 访问 https://hub.docker.com/
2. 点击 "Sign Up"
3. 验证邮箱

#### 2. 本地登录 Docker Hub

```bash
docker login
# 或指定用户名
docker login -u 您的用户名
```

#### 3. 修改发布脚本

编辑 `scripts/publish-docker.sh` 或 `scripts/publish-docker.bat`，修改配置：

```bash
DOCKER_HUB_USERNAME="您的实际DockerHub账号"
IMAGE_NAME="marine-expert-system"  # 或其他名称
```

#### 4. 构建并推送镜像

**Windows**：
```cmd
cd scripts
publish-docker.bat
```

**Mac/Linux**：
```bash
cd scripts
bash publish-docker.sh
```

这会自动：
- ✅ 构建 Docker 镜像
- ✅ 优化镜像大小
- ✅ 打标签（latest 和 m8）
- ✅ 推送到 Docker Hub

#### 5. 验证发布

1. 访问 Docker Hub：
   ```
   https://hub.docker.com/r/您的账号/marine-expert-system
   ```

2. 检查镜像信息：
   - 标签（Tags）
   - 大小（Size）
   - 拉取次数（Pulls）

#### 6. 测试拉取

在新电脑上测试：
```bash
docker pull 您的账号/marine-expert-system:latest
docker run -d -p 8000:8000 您的账号/marine-expert-system:latest
```

访问 http://localhost:8000/docs 验证。

---

## 用户下载指南

### 用户类型 A：开发者（查看源码）

**下载方式**：
```bash
git clone https://github.com/您的账号/marine-offshore-expert-system.git
cd marine-offshore-expert-system
docker compose up -d
```

**适合**：
- 想查看源代码
- 想二次开发
- 想贡献代码

### 用户类型 B：最终用户（开箱即用）

**下载方式**：
```bash
docker pull 您的账号/marine-expert-system:latest
docker run -d -p 8000:8000 您的账号/marine-expert-system:latest
```

**适合**：
- 只想使用系统
- 不关心源代码
- 希望快速部署

### 用户类型 C：离线环境

**下载方式**：
```bash
# 保存镜像为文件
docker save 您的账号/marine-expert-system:latest -o marine-expert.tar

# 传输到离线电脑（U盘、局域网等）

# 在离线电脑上加载
docker load -i marine-expert.tar

# 运行
docker run -d -p 8000:8000 您的账号/marine-expert-system:latest
```

---

## 版本管理

### 版本号规范

推荐使用 [语义化版本](https://semver.org/)：

```
主版本号.次版本号.修订号 (MAJOR.MINOR.PATCH)

例如：1.0.0

- MAJOR（主版本）：不兼容的 API 变更
- MINOR（次版本）：向后兼容的功能新增
- PATCH（修订号）：向后兼容的问题修复
```

### 发布流程

```
开发分支 (dev)
    ↓
测试通过
    ↓
合并到主分支 (master)
    ↓
打版本标签 (git tag v1.0.0)
    ↓
发布到 GitHub (Release)
    ↓
构建并推送到 Docker Hub
    ↓
发布公告（邮件、社交媒体等）
```

### Docker 镜像标签策略

推荐标签：

| 标签 | 说明 | 示例 |
|------|------|------|
| `latest` | 最新稳定版 | `v1.0.0` |
| `vX.Y.Z` | 特定版本 | `v1.0.0` |
| `dev` | 开发版 | `commit-hash` |
| `m8` | 仅后端服务 | 用于 API 部署 |

---

## 📊 发布后检查清单

### GitHub 检查

- [ ] 仓库可访问
- [ ] README.md 显示正常
- [ ] 文件大小合理（< 100 MB）
- [ ] 无敏感信息泄露
- [ ] License 文件存在

### Docker Hub 检查

- [ ] 镜像可拉取
- [ ] 镜像大小合理（< 3 GB）
- [ ] 镜像描述完整
- [ ] Dockerfile 链接正确

### 用户体验检查

- [ ] 新用户能按文档成功部署
- [ ] API 文档可访问
- [ ] 所有功能正常工作

---

## 常见问题

### Q: GitHub 仓库太大怎么办？

**A**:
1. 检查 `.gitignore` 是否遗漏了大文件
2. 使用 Git LFS 管理必须的大文件
3. 清理 Git 历史：
   ```bash
   git gc --aggressive --prune=now
   ```

### Q: Docker 镜像太大怎么办？

**A**:
1. 使用 `.dockerignore` 排除不必要文件
2. 使用多阶段构建（已实现）
3. 压缩镜像层
4. 考虑分离 M1 文档解析引擎（可选 profile）

### Q: 是否需要同时发布到两个地方？

**A**:
- ✅ **推荐同时发布**
- GitHub 服务于开发者
- Docker Hub 服务于最终用户
- 两者不冲突，互补

---

## 自动化发布（进阶）

### GitHub Actions 自动发布

可以配置 GitHub Actions，在 `git push` 时自动：

1. 运行测试
2. 构建 Docker 镜像
3. 推送到 Docker Hub
4. 创建 GitHub Release

示例配置文件：`.github/workflows/release.yml`

---

## 总结

### 推荐发布流程

```
1. 准备阶段
   ├─ 更新文档
   ├─ 检查 .gitignore
   └─ 运行测试套件

2. 发布到 GitHub
   ├─ 创建仓库（gh repo create）
   ├─ 推送代码（git push）
   └─ 创建 Release（gh release create）

3. 发布到 Docker Hub
   ├─ 修改脚本配置
   ├─ 构建镜像（docker build）
   └─ 推送镜像（docker push）

4. 验证
   ├─ 测试 GitHub 克隆
   ├─ 测试 Docker 拉取
   └─ 新用户部署测试

5. 公告
   ├─ 更新 README
   ├─ 发布博客/邮件
   └─ 通知社区
```

### 下一步

发布完成后，请更新：

1. **README.md** - 添加实际的 GitHub 仓库地址
2. **DEPLOYMENT_GUIDE.md** - 更新为真实的仓库地址
3. **CHANGELOG.md** - 记录本次发布内容

---

*最后更新: 2026-06-13*
*文档版本: 1.0*
