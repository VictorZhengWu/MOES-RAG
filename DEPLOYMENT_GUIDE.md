# Marine & Offshore Expert System — 新用户部署指南（Windows 平台）

> **适用对象**: 拥有一台新电脑的用户，希望从零开始部署本系统
> **预计耗时**: 30-60 分钟（首次安装）
> **技术要求**: 无需编程基础，会使用浏览器即可

---

## 📋 目录

1. [系统要求](#系统要求)
2. [方式一：Docker 一键部署（推荐）](#方式一docker-一键部署推荐)
3. [方式二：从源代码手动部署](#方式二从源代码手动部署)
4. [首次使用指南](#首次使用指南)
5. [常见问题](#常见问题)

---

## 系统要求

### 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| **CPU** | 4 核心 | 8 核心及以上 |
| **内存** | 8 GB | 12 GB 及以上 |
| **硬盘** | 5 GB 可用空间 | 10 GB 及以上 |
| **网络** | 宽带连接 | 宽带连接（首次需下载镜像） |

### 软件要求

- **操作系统**: Windows 10/11（64 位）
- **浏览器**: Chrome、Edge 或 Firefox 最新版

---

## 方式一：Docker 一键部署（推荐）

> **优点**: 像安装软件一样简单，无需手动配置环境
> **缺点**: 首次需要下载 Docker 镜像（约 2-3 GB）
> **适合**: 所有用户，特别是非技术人员

### 步骤 1：获取软件

#### 选项 A：从 GitHub 下载（推荐）

1. 访问项目 GitHub 页面：
   ```
   https://github.com/your-org/marine-offshore-expert-system
   ```

2. 点击页面右上角的 **"Code"** 按钮，选择 **"Download ZIP"**

3. 下载完成后，右键点击 ZIP 文件，选择 **"全部解压..."**

4. 解压到您喜欢的位置，例如：
   ```
   C:\Users\你的用户名\MarineExpertSystem
   ```

#### 选项 B：使用 Git 克隆（适合开发者）

1. 安装 Git Desktop（如果尚未安装）：
   ```
   https://git-scm.com/download/win
   ```

2. 在文件夹中打开右键菜单，选择 **"Git Bash Here"**

3. 运行命令：
   ```bash
   git clone https://github.com/your-org/marine-offshore-expert-system.git
   cd marine-offshore-expert-system
   ```

### 步骤 2：安装 Docker Desktop

1. 下载 Docker Desktop：
   ```
   https://www.docker.com/products/docker-desktop/
   ```

2. 运行安装程序 `Docker Desktop Installer.exe`

3. 安装过程中**确保勾选**：
   - ✅ "Use WSL 2 instead of Hyper-V"（如果提示）
   - ✅ "Add shortcut to desktop"

4. 安装完成后，**重启电脑**

5. 重启后，从桌面启动 **Docker Desktop**

6. 等待 Docker 启动完成（系统托盘的小鲸鱼图标停止动画）

   ![Docker 托盘图标](https://docs.docker.com/desktop/images/whale-icon.png)

7. 如果是首次使用，Docker 可能要求您登录：
   - 可以点击 **"Sign out"** 或 **"Continue without signing in"** 跳过登录

### 步骤 3：一键启动系统

1. 打开解压后的文件夹，进入：
   ```
   C:\Users\你的用户名\MarineExpertSystem\deploy\personal
   ```

2. 找到 **`start.bat`** 文件，**双击运行**

3. 如果弹出 **"Windows 保护你的电脑"** 提示，点击 **"更多信息"** → **"仍要运行"**

4. 等待启动脚本运行：
   - 首次运行：下载 Docker 镜像（5-10 分钟）
   - 后续运行：约 30 秒

5. 看到 **"System is ready!"** 提示后，浏览器会自动打开

### 步骤 4：访问系统

启动成功后，您可以访问：

| 功能 | 地址 | 说明 |
|------|------|------|
| **用户门户** | http://localhost:8000 | 主要使用界面（需前端部署） |
| **API 文档** | http://localhost:8000/docs | Swagger 交互式文档 |
| **在线帮助** | http://localhost:3000/help | 使用帮助和故障排除 |

> **注意**: 当前 Docker 部署仅包含后端服务（M1-M8）。前端门户（M6/M7）需要单独启动（见下方）。

### 步骤 5：停止系统

当您不再使用系统时：

1. 找到 **`stop.bat`** 文件，**双击运行**

2. 或者在命令行中运行：
   ```bash
   cd deploy/personal
   docker compose down
   ```

---

## 方式二：从源代码手动部署

> **优点**: 完全控制，可以修改代码
> **缺点**: 需要安装多个依赖，配置较复杂
> **适合**: 开发者，或需要定制功能的用户

### 步骤 1：安装基础软件

#### 1.1 安装 Python 3.12

1. 访问：
   ```
   https://www.python.org/downloads/release/python-3120/
   ```

2. 下载 **"Windows installer (64-bit)"**

3. 运行安装程序，**重要**：
   - ✅ 勾选 **"Add Python to PATH"**
   - ✅ 选择 **"Install for all users"**

4. 安装完成后，打开 **命令提示符（CMD）**，验证安装：
   ```bash
   python --version
   # 应显示: Python 3.12.0
   ```

#### 1.2 安装 Node.js 20 LTS

1. 访问：
   ```
   https://nodejs.org/
   ```

2. 下载 **"LTS"** 版本（推荐 20.x）

3. 运行安装程序，使用默认设置

4. 验证安装：
   ```bash
   node --version
   npm --version
   ```

#### 1.3 安装 Git

（如方式一中已安装，可跳过）

### 步骤 2：获取源代码

```bash
# 使用 Git 克隆（推荐）
git clone https://github.com/your-org/marine-offshore-expert-system.git
cd marine-offshore-expert-system
```

或从 GitHub 下载 ZIP 并解压。

### 步骤 3：安装 Python 依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
venv\Scripts\activate

# 安装依赖
pip install -e contracts/
pip install -e m2-storage/
pip install -e m3-retrieval/
pip install -e m4-knowledge-graph/
pip install -e m5-qa-engine/
pip install -e m8-api-gateway/
```

### 步骤 4：安装前端依赖

```bash
# 安装 M6 User Portal 依赖
cd m6-user-portal
npm install
cd ..

# 安装 M7 Admin Portal 依赖
cd m7-admin-portal
npm install
cd ..
```

### 步骤 5：配置环境变量

复制环境变量模板：
```bash
copy .env.example .env
```

编辑 `.env` 文件，根据需要修改配置。

### 步骤 6：启动服务

#### 6.1 启动后端（M8 API Gateway）

```bash
# 激活虚拟环境（如果未激活）
venv\Scripts\activate

# 启动 API Gateway
cd m8-api-gateway
python -m uvicorn m8_gateway.core.app:create_app --host 0.0.0.0 --port 8000
```

后端将在 http://localhost:8000 启动。

#### 6.2 启动前端（M6 User Portal）

**新开一个命令提示符窗口**：

```bash
cd m6-user-portal

# 开发模式启动
npm run dev
```

前端将在 http://localhost:3000 启动。

#### 6.3 启动管理门户（M7 Admin Portal）- 可选

**再开一个命令提示符窗口**：

```bash
cd m7-admin-portal

# 开发模式启动
npm run dev
```

管理门户将在 http://localhost:3001 启动。

### 步骤 7：访问系统

打开浏览器访问：
- **用户门户**: http://localhost:3000
- **管理门户**: http://localhost:3001
- **API 文档**: http://localhost:8000/docs

---

## 首次使用指南

### 1. 注册账号

1. 打开 http://localhost:3000

2. 点击右上角 **"Sign up"** 或 **"注册"**

3. 填写：
   - 用户名（英文或数字）
   - 邮箱地址
   - 密码（至少 8 位）

4. 点击 **"Create Account"** 或 **"创建账号"**

### 2. 登录系统

1. 使用注册的邮箱和密码登录

2. 首次登录后，系统会：
   - 自动创建一个 API Key
   - 引导您选择语言（中文/English/한국어/日本語/Norsk）

### 3. 开始提问

**简单模式**：

1. 在输入框中输入您的问题，例如：
   ```
   DNV 规范中，EH36 钢的焊接程序要求是什么？
   ```

2. 点击 **"Send"** 或按 **Enter** 键

3. 系统会返回带有引用的答案，例如：
   > 根据 DNV Pt.4 Ch.3 §6.2 [1]，EH36 钢的焊接程序需要...
   >
   > **引用**:
   > [1] DNV Pt.4 Ch.3 §6.2, 2025 edition

**Deep Research 模式**（复杂问题）：

1. 点击 **"🧠 Deep Research"** 按钮

2. 输入复杂问题，例如：
   ```
   比较DNV、ABS和CCS对LNG船围护系统的绝缘要求差异
   ```

3. 系统会：
   - 分解问题为多个子任务
   - 并行检索多份规范文档
   - 交叉对比不同船级社的要求
   - 生成 7 节结构化报告

### 4. 创建项目工作区

1. 点击左侧 **"📁 Projects"** 或 **"项目"**

2. 点击 **"+ New Project"** 或 **"+ 新建项目"**

3. 填写项目信息：
   - 项目名称：例如 "LNG运输船设计"
   - 船舶类型：LNG Carrier
   - 主要船级社：DNV
   - 设计阶段：设计

4. 点击 **"Create"** 或 **"创建"**

5. 项目创建后，您可以：
   - 上传相关文档
   - 追踪合规性条款
   - 记录研究结论
   - 邀请团队成员协作

---

## 常见问题

### Q1: Docker 启动失败，提示 "Docker is not running"

**原因**: Docker Desktop 未正确启动

**解决方法**:

1. 检查系统托盘是否有 Docker 鲸鱼图标
2. 如果图标在动画（旋转），请等待其停止
3. 如果没有图标，从开始菜单启动 **Docker Desktop**
4. 等待 Docker 完全启动（约 30 秒）

### Q2: 端口 8000 或 3000 已被占用

**原因**: 其他程序正在使用这些端口

**解决方法**:

**方法 A - 停止占用端口的程序**：

```bash
# 查找占用端口 8000 的程序
netstat -ano | findstr :8000

# 记下最后一列的 PID（进程 ID）
# 使用任务管理器结束该进程
```

**方法 B - 修改配置文件**：

编辑 `deploy/personal/docker-compose.yml`：

```yaml
# 将 8000:8000 改为 8001:8000
ports:
  - "8001:8000"
```

### Q3: 内存不足，容器退出

**原因**: Docker 分配的内存不足

**解决方法**:

1. 打开 Docker Desktop
2. 点击 **设置（齿轮图标）**
3. 选择 **Resources** → **Memory**
4. 从默认的 2 GB 增加到 **6 GB 或 8 GB**
5. 点击 **"Apply & Restart"**

### Q4: 无法访问 localhost:3000

**原因**: 前端服务未启动（Docker 部署仅包含后端）

**解决方法**:

您有两个选择：

**选择 A - 仅使用 API 文档**：
- 访问 http://localhost:8000/docs
- 在 Swagger UI 中测试所有 API

**选择 B - 手动启动前端**：
```bash
cd m6-user-portal
npm install
npm run dev
# 访问 http://localhost:3000
```

### Q5: 首次启动很慢，需要下载大量数据

**说明**: 首次运行需要下载 Docker 镜像（约 2-3 GB）

**预计时间**:
- 100 Mbps 宽带：约 5-10 分钟
- 10 Mbps 宽带：约 30-60 分钟

**注意**: 后续启动只需 30 秒左右

### Q6: 如何完全卸载系统

**卸载 Docker 版本**：

```bash
# 停止并删除所有容器和数据卷
cd deploy/personal
docker compose down -v

# 删除项目文件夹
# 然后在 Windows 控制面板中卸载 Docker Desktop
```

**卸载手动安装版本**：

```bash
# 停止所有服务
# Ctrl+C 停止所有运行的命令行窗口

# 删除虚拟环境
venv\Scripts\deactivate
rmdir /s venv

# 删除 node_modules
rmdir /s m6-user-portal\node_modules
rmdir /s m7-admin-portal\node_modules
```

---

## 推荐部署方式对比

| 特性 | Docker 一键部署 | 手动源代码部署 |
|------|----------------|--------------|
| **安装难度** | ⭐ 简单（像安装软件） | ⭐⭐⭐ 复杂（需技术背景） |
| **启动速度** | ⭐⭐⭐ 快（30 秒） | ⭐⭐ 中等（需启动多个服务） |
| **资源占用** | ⭐⭐ 中等（Docker 开销） | ⭐ 低（原生运行） |
| **可定制性** | ⭐ 低（难以修改代码） | ⭐⭐⭐ 高（可直接修改） |
| **适用场景** | 日常使用、演示、学习 | 开发、定制、生产部署 |

**我们的推荐**：

- **90% 的用户**: 使用 Docker 一键部署
- **开发者**: 使用手动源代码部署
- **生产环境**: 使用 Docker Compose（配置 PostgreSQL/Redis）

---

## 下一步

部署成功后，建议您：

1. **阅读在线帮助**: http://localhost:3000/help
2. **查看 API 文档**: http://localhost:8000/docs
3. **尝试示例问题**: 在帮助页面有常用问题示例
4. **加入社区**: [GitHub Discussions](https://github.com/your-org/marine-offshore-expert-system/discussions)

---

## 获取帮助

如果遇到问题：

1. 查看 `deploy/personal/HELP.md`
2. 查看 [GitHub Issues](https://github.com/your-org/marine-offshore-expert-system/issues)
3. 在 GitHub Discussions 提问
4. 查看日志：
   ```bash
   docker compose logs m8
   ```

---

**祝您使用愉快！** 🚢

---

*最后更新: 2026-06-13*
*文档版本: 1.0*
