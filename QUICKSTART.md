# 快速启动指南 (Quick Start)

> **5 分钟上手 Marine & Offshore Expert System**

---

## 方式一：Docker 一键启动（推荐）

### 前提条件

- ✅ Windows 10/11（64 位）
- ✅ 8 GB 内存（推荐 12 GB）
- ✅ 5 GB 可用硬盘空间

### 启动步骤

1. **安装 Docker Desktop**（首次使用）
   ```
   https://www.docker.com/products/docker-desktop/
   ```
   安装后重启电脑。

2. **启动系统**
   - 双击 `deploy/personal/start.bat`
   - 首次运行需下载镜像（5-10 分钟）

3. **访问系统**
   - API 文档: http://localhost:8000/docs （推荐）
   - 健康检查: http://localhost:8000/health

### 停止系统

双击 `deploy/personal/stop.bat`

---

## 方式二：仅 API 文档访问（无需前端）

适合快速测试和 API 调用。

1. 启动后端服务（Docker 或手动）
2. 访问 http://localhost:8000/docs
3. 在 Swagger UI 中测试所有 API

**示例：测试问答功能**

```bash
# 使用 curl 测试
curl -X POST http://localhost:8000/api/v1/qa/simple ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer YOUR_API_KEY" ^
  -d "{\"question\":\"DNV规范中,EH36钢的焊接要求是什么?\",\"conversation_id\":\"test-001\"}"
```

或在 Swagger UI 中：
1. 展开 `POST /api/v1/qa/simple`
2. 点击 "Try it out"
3. 输入问题
4. 点击 "Execute"

---

## 首次使用

### 获取 API Key

1. 访问 http://localhost:8000/docs
2. 展开 `POST /api/v1/auth/register`
3. 注册账号（用户名、邮箱、密码）
4. 展开 `POST /api/v1/auth/login`
5. 使用注册信息登录，获取 API Key
6. 复制 API Key（格式：`sk-m8-xxxxx`）

### 开始提问

**方式 1 - 使用 Swagger UI**：
1. 展开 `POST /api/v1/qa/simple`
2. 点击 "Try it out"
3. 输入：
   - `question`: 您的问题
   - `conversation_id`: 会话 ID（可随机生成）
   - `Authorization`: 头部添加 `Bearer YOUR_API_KEY`
4. 点击 "Execute"

**方式 2 - 使用 Python**：
```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/qa/simple",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    json={
        "question": "DNV规范中,EH36钢的焊接要求是什么?",
        "conversation_id": "test-001"
    }
)

print(response.json()["answer"])
```

**方式 3 - 使用 OpenAI SDK**：
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="YOUR_API_KEY"
)

response = client.chat.completions.create(
    model="m5-qa",
    messages=[{"role": "user", "content": "DNV规范中,EH36钢的焊接要求是什么?"}]
)

print(response.choices[0].message.content)
```

---

## 示例问题

### 规范查询

- "DNV Pt.3 Ch.4 对舱室密性测试的要求是什么？"
- "ABS 对双壳油轮的横向强度要求是什么？"
- "SOLAS 第II-2章关于火灾探测器的规定"

### 对比分析

- "DNV 和 ABS 对 LNG 船围护系统绝缘要求的差异"
- "CCS 和 LR 对散货船结构强度的对比"

### 技术问题

- "EH36 钢的焊接程序要求"
- "低温用钢材的冲击试验标准"
- "船舶管系压力试验的要求"

---

## 下一步

- 📖 阅读完整部署指南: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- 🌐 查看在线帮助: http://localhost:3000/help （需启动前端）
- 📚 浏览 API 文档: http://localhost:8000/docs
- 💬 加入社区讨论: [GitHub Discussions](https://github.com/victorzhengwu/MOES-RAG/discussions)

---

## 需要帮助？

查看详细帮助：
- Windows 用户: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- Docker 帮助: [deploy/personal/HELP.md](deploy/personal/HELP.md)
- 常见问题: [DEPLOYMENT_GUIDE.md#常见问题](DEPLOYMENT_GUIDE.md#常见问题)

---

**提示**: 首次使用建议先通过 Swagger UI (http://localhost:8000/docs) 熟悉系统，再考虑部署前端门户。

---

*最后更新: 2026-06-13*
