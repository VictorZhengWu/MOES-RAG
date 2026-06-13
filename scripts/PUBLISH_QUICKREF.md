# 发布快速参考

## 🚀 快速发布（5分钟）

### 1️⃣ 发布到 GitHub

```bash
# 一条命令完成（需要先 gh auth login）
gh repo create marine-offshore-expert-system --public --source=. --push
```

### 2️⃣ 发布到 Docker Hub

**Windows**:
```cmd
cd scripts
publish-docker.bat
```

**Mac/Linux**:
```bash
cd scripts
bash publish-docker.sh
```

---

## 📦 用户下载

### 开发者（GitHub）
```bash
git clone https://github.com/您的账号/marine-offshore-expert-system.git
cd marine-offshore-expert-system
docker compose up -d
```

### 最终用户（Docker Hub）
```bash
docker pull 您的账号/marine-expert-system:latest
docker run -d -p 8000:8000 您的账号/marine-expert-system:latest
```

---

## ⚠️ 发布前检查

- [ ] 修改 `scripts/publish-docker.sh` 中的 `DOCKER_HUB_USERNAME`
- [ ] 确认 `.gitignore` 排除了 node_modules、venv、data
- [ ] 运行测试套件：`python -m pytest`

---

## 🔗 有用链接

- GitHub: https://github.com/您的账号/marine-offshore-expert-system
- Docker Hub: https://hub.docker.com/r/您的账号/marine-expert-system
- 详细指南: [PUBLISHING_GUIDE.md](../PUBLISHING_GUIDE.md)
