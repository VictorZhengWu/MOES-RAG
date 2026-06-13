# 新用户下载指南 - Marine & Offshore Expert System

> **目标**: 从 GitHub 下载源码到新电脑
> **适合**: 完全新用户，无需编程基础

---

## 📋 方案对比

| 方案 | 难度 | 适用场景 | 需要安装 |
|------|------|---------|---------|
| **方案 A：下载 ZIP** | ⭐ 超简单 | 只想使用系统 | 无需安装额外软件 |
| **方案 B：Git 克隆** | ⭐⭐ 简单 | 开发者、需要更新 | Git |
| **方案 C：GitHub Desktop** | ⭐⭐ 中等 | 图形界面操作 | GitHub Desktop |

---

## 方案 A：下载 ZIP（推荐给完全新手）

### 优点
- ✅ 无需安装任何软件
- ✅ 像下载普通文件一样简单
- ✅ 适合只想使用系统的用户

### 缺点
- ❌ 更新代码需要重新下载
- ❌ 无法提交修改（如果有）

### 步骤

#### 第 1 步：访问 GitHub 仓库

在浏览器中打开：
```
https://github.com/victorzhengwu/MOES-RAG
```

您会看到项目主页。

#### 第 2 步：下载 ZIP 文件

1. 在仓库页面，找到绿色的 **"Code"** 按钮（在右上角，文件列表上方）

2. 点击 **"Code"** 按钮，会弹出下拉菜单

3. 在下拉菜单中，找到 **"Download ZIP"** 选项

4. 点击 **"Download ZIP"**

5. 浏览器会开始下载文件：`MOES-RAG-main.zip`（约 50-100 MB）

6. 等待下载完成（根据网速，约 1-5 分钟）

#### 第 3 步：解压文件

**Windows**：
1. 打开 **文件资源管理器**
2. 找到下载的 `MOES-RAG-main.zip` 文件（通常在 `下载` 文件夹）
3. **右键点击** ZIP 文件
4. 选择 **"全部解压..."**
5. 选择解压位置（例如 `C:\Users\您的用户名\MOES-RAG`）
6. 点击 **"解压"**

**Mac**：
1. 双击 ZIP 文件
2. 系统会自动解压到 `下载` 文件夹
3. 将解压后的文件夹移动到您想要的位置

#### 第 4 步：验证下载

解压后的文件夹结构应该是：

```
MOES-RAG-main/
├── deploy/
│   └── personal/
│       ├── start.bat          ← 启动脚本
│       ├── stop.bat
│       ├── docker-compose.yml
│       └── HELP.md
├── contracts/
├── m1-doc-parsing/
├── m2-storage/
├── m3-retrieval/
├── m4-knowledge-graph/
├── m5-qa-engine/
├── m6-user-portal/
├── m7-admin-portal/
├── m8-api-gateway/
├── README.md
├── DEPLOYMENT_GUIDE.md
└── QUICKSTART.md
```

#### 第 5 步：启动系统

1. 确保已安装 Docker Desktop（见下方）
2. 进入解压文件夹：`MOES-RAG-main\deploy\personal\`
3. 双击 **`start.bat`**

---

## 方案 B：使用 Git 克隆（推荐给开发者）

### 优点
- ✅ 可以轻松更新代码（`git pull`）
- ✅ 可以查看提交历史
- ✅ 可以提交修改（如果有权限）

### 缺点
- ❌ 需要安装 Git
- ❌ 需要使用命令行

### 步骤

#### 第 1 步：安装 Git

**Windows**：
1. 访问：https://git-scm.com/download/win
2. 下载 `Git for Windows Setup`
3. 运行安装程序
4. 使用默认设置，一路点击 **"Next"**
5. 安装完成后，重启电脑

**验证安装**：
```cmd
git --version
# 应显示：git version 2.x.x
```

#### 第 2 步：克隆仓库

**方式 A - 使用命令行**：

1. 打开 **命令提示符（CMD）** 或 **PowerShell**
   - 按 `Win + R`
   - 输入 `cmd` 或 `powershell`
   - 按 `Enter`

2. 导航到您想要的文件夹：
   ```cmd
   cd C:\Users\您的用户名\Documents
   ```

3. 运行克隆命令：
   ```cmd
   git clone https://github.com/victorzhengwu/MOES-RAG.git
   ```

4. 等待克隆完成（约 1-5 分钟）

5. 进入项目文件夹：
   ```cmd
   cd MOES-RAG
   ```

**方式 B - 使用 GitHub Desktop**（见方案 C）

#### 第 3 步：验证克隆

```cmd
dir
# 应显示所有项目文件夹：contracts/, m1-doc-parsing/, 等
```

#### 第 4 步：启动系统

```cmd
cd deploy\personal
start.bat
```

---

## 方案 C：使用 GitHub Desktop（图形界面）

### 优点
- ✅ 图形界面，无需命令行
- ✅ 可以轻松更新代码
- ✅ 适合不熟悉命令行的用户

### 缺点
- ❌ 需要安装额外软件（GitHub Desktop）
- ❌ 体积较大（约 200 MB）

### 步骤

#### 第 1 步：安装 GitHub Desktop

1. 访问：https://desktop.github.com/
2. 点击 **"Download for Windows"**
3. 运行安装程序
4. 使用默认设置安装

#### 第 2 步：登录 GitHub Desktop

1. 启动 **GitHub Desktop**
2. 点击 **"Sign in to GitHub.com"**
3. 在浏览器中授权 GitHub Desktop
4. 返回 GitHub Desktop，登录成功

#### 第 3 步：克隆仓库

1. 在 GitHub Desktop 中，点击 **"File"** → **"Clone a repository from the Internet"**
2. 在 URL 输入框中输入：
   ```
   https://github.com/victorzhengwu/MOES-RAG
   ```
3. 在 **"Local path"** 中选择保存位置：
   ```
   C:\Users\您的用户名\Documents\MOES-RAG
   ```
4. 点击 **"Clone"**
5. 等待克隆完成（约 1-5 分钟）

#### 第 4 步：启动系统

1. 在文件资源管理器中，打开克隆的文件夹：
   ```
   C:\Users\您的用户名\Documents\MOES-RAG
   ```

2. 进入 `deploy\personal` 文件夹

3. 双击 **`start.bat`**

---

## 🎯 推荐选择

### 如果您是**完全新手**，只想使用系统

👉 **方案 A（下载 ZIP）**

**原因**：
- 最简单，无需安装额外软件
- 像下载普通文件一样
- 5 分钟搞定

### 如果您是**开发者**，或希望后续更新代码

👉 **方案 B（Git 克隆）**

**原因**：
- 可以轻松更新（`git pull`）
- 可以查看提交历史
- 开发必备技能

### 如果您**不熟悉命令行**，但希望使用 Git

👉 **方案 C（GitHub Desktop）**

**原因**：
- 图形界面，操作简单
- 无需记忆命令
- 一键更新代码

---

## 📊 下载方式对比表

| 特性 | 方案 A (ZIP) | 方案 B (Git CLI) | 方案 C (GitHub Desktop) |
|------|-------------|-----------------|------------------------|
| **安装软件** | 无需 | Git（~50 MB） | GitHub Desktop（~200 MB） |
| **使用命令行** | 不需要 | 需要 | 不需要 |
| **更新代码** | 重新下载 | `git pull` | 点击按钮 |
| **查看历史** | 无法 | 可以 | 可以 |
| **提交修改** | 无法 | 可以 | 可以 |
| **适合用户** | 最终用户 | 开发者 | 所有用户 |
| **难度** | ⭐ 超简单 | ⭐⭐ 简单 | ⭐⭐ 中等 |

---

## 🚀 快速开始（3 步搞定）

### 方式 1：下载 ZIP（最简单）

```
1. 访问：https://github.com/victorzhengwu/MOES-RAG
2. 点击 "Code" → "Download ZIP"
3. 解压并双击 deploy/personal/start.bat
```

### 方式 2：Git 克隆（推荐）

```cmd
git clone https://github.com/victorzhengwu/MOES-RAG.git
cd MOES-RAG\deploy\personal
start.bat
```

---

## ⚠️ 下载前必读

### 系统要求

下载源码前，请确保您的电脑满足：

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| **操作系统** | Windows 10/11 | Windows 11 |
| **CPU** | 4 核 | 8 核+ |
| **内存** | 8 GB | 12 GB+ |
| **硬盘** | 5 GB 可用 | 10 GB+ |
| **网络** | 宽带 | 宽带 |

### 必需软件

**Docker Desktop**（所有方案都需要）：

1. 下载：https://www.docker.com/products/docker-desktop/
2. 安装并重启电脑
3. 启动 Docker Desktop

---

## 📥 下载完成后

### 验证下载

检查文件是否完整：

```cmd
# 应该有这些主要文件夹
dir contracts m1-doc-parsing m2-storage m3-retrieval m4-knowledge-graph m5-qa-engine m6-user-portal m7-admin-portal m8-api-gateway
```

### 启动系统

```cmd
cd deploy\personal
start.bat
```

### 访问系统

- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

---

## 🔄 如何更新代码

### 如果您下载了 ZIP

重新下载新的 ZIP 文件并解压（会覆盖旧文件）。

### 如果您使用 Git 克隆

```cmd
cd MOES-RAG
git pull
```

### 如果您使用 GitHub Desktop

1. 打开 GitHub Desktop
2. 选择 **MOES-RAG** 仓库
3. 点击 **"Fetch origin"**
4. 点击 **"Pull origin"**

---

## 🆘 常见问题

### Q: 下载速度慢怎么办？

**A**:
- 使用下载管理器（如 IDM、Free Download Manager）
- 或使用 Git 克隆（支持断点续传）

### Q: ZIP 文件损坏怎么办？

**A**:
- 重新下载 ZIP 文件
- 或使用 Git 克隆（更可靠）

### Q: Git 克隆失败怎么办？

**A**:
1. 检查网络连接
2. 检查 Git 是否正确安装：
   ```cmd
   git --version
   ```
3. 如果提示认证错误，确保 GitHub 账号设置正确

### Q: 克隆后找不到 start.bat？

**A**:
- 确认克隆了正确的仓库
- 检查文件路径：`MOES-RAG\deploy\personal\start.bat`

---

## 📚 下一步

下载完成后，请参考：

- **快速启动**: [QUICKSTART.md](QUICKSTART.md)
- **详细部署**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **Docker 帮助**: [deploy/personal/HELP.md](deploy/personal/HELP.md)

---

## 🎉 总结

**推荐流程**：

```
新用户下载源码（3 种方式）

1. 下载 ZIP（最简单）
   └─ 访问 GitHub → 点 "Code" → "Download ZIP"

2. Git 克隆（推荐）
   └─ git clone https://github.com/victorzhengwu/MOES-RAG.git

3. GitHub Desktop（图形界面）
   └─ GitHub Desktop → Clone Repository

然后：

安装 Docker Desktop → 双击 start.bat → 访问 http://localhost:8000/docs
```

---

*最后更新: 2026-06-13*
*文档版本: 1.0*
