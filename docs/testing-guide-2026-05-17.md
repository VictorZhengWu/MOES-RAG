# M6 / M7 完整测试指南

> **日期**：2026-05-17 | **Phase 1 Mock 阶段**

---

## 一、启动服务

### 终端 1：Mock Server
```bash
cd E:\myCode\RAG
pip install -e contracts/ -e mock-server/
python -c "from mock_server.app import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8002)"
```

### 终端 2：M6 用户端
```bash
cd E:\myCode\RAG\m6-user-portal
copy .env.example .env.development
npm run dev
# → http://localhost:3000
```

### 终端 3：M7 管理后台
```bash
cd E:\myCode\RAG\m7-admin-portal
copy .env.example .env.development
npm run dev
# → http://localhost:3001
```

---

## 二、管理员账户（M7）

| 用户名 | 密码 | 角色 |
|--------|------|------|
| `admin` | `admin123` | 管理员 |
| `editor` | `editor123` | 编辑者 |
| `victor` | `victor123` | 管理员 |

打开 `http://localhost:3001` → 输入上述任一账密 → 进入管理后台。

---

## 三、M6 用户端测试路径

### 场景 1：游客浏览
1. 打开 `http://localhost:3000`
2. 看到空状态 + 5 个建议问题
3. 点击任意建议问题 → 流式回答 + 引用编号
4. 点击引用编号 → 右侧引用面板滑出
5. 输入自定义问题 → Enter 发送 → 流式回答
6. 回答结束后出现 👍👎 反馈按钮 + Follow-up 建议按钮
7. 鼠标悬停消息气泡 → 右上角出现 📋 复制按钮
8. 切换语言（Settings > General > Language dropdown）
9. 切换主题（Settings > General > Light/Dark/System）

### 场景 2：登录/注册
1. 侧边栏底部点 "Log in"
2. 输入任意邮箱（如 `test@shipyard.no`）+ 密码（≥8位）
3. 登录成功 → 侧边栏底部显示用户名 + 头像
4. 发送几轮对话
5. 点 Logout → 回到游客状态
6. 点 Log in → 登录后回到之前的对话页面

### 场景 3：知识库浏览
1. 侧边栏 → Knowledge Base
2. 看到 3 份 mock 文档（DNV/ABS/IMO）
3. 搜索 + 船级社筛选 + 专业筛选

### 场景 4：文件拖放
1. 从桌面拖任意文件到浏览器窗口
2. 全屏覆盖层显示 "Drop any file here"
3. 释放后输入框上方出现文件图标 + 文件名
4. 点 ✕ 可移除

### 场景 5：跳转窄条
1. 发送 2+ 条问题
2. 右侧出现灰色横线
3. 鼠标移入横线区域 → 弹出列表 + 横线变蓝
4. 点击某条横线 → 滚到对应位置

---

## 四、M7 管理后台测试路径

### 场景 1：Dashboard
1. 登录后 → 查看统计卡片（47 文档、12850 块等）
2. 模块健康指示灯（6 个绿点）
3. 存储用量进度条

### 场景 2：文档管理
1. 侧边栏 → Documents
2. 看到上传区域（虚线框）+ 3 份 mock 文档
3. 拖放命名规范的文件 `[DNV][RU-SHIP][Pt.1-Ch.1][Test][202507].pdf`
4. 自动解析 → 预览表格显示 Society/Category/Section 等
5. 选择 Domain + Language
6. 确认上传

### 场景 3：知识图谱
1. 侧边栏 → Knowledge Graph
2. Entities 标签 → 3 个 mock 实体 → 点击查看详情
3. 实体详情页 → ✏️ 编辑名称 / 🗑 删除实体
4. Relations 标签 → 查看关系 / 🗑 删除关系
5. Cross-Reference 标签 → DNV↔ABS 等价映射

### 场景 4：LLM 配置
1. 侧边栏 → LLM Config
2. 7 个目的框：Chat/Reasoning/Embedding/Reranking/OCR/Vision/Parsing
3. 每框可配置 Provider/Model/API Key 等
4. 每框底部有角色权限标签
5. Test Connection 按钮

### 场景 5：用户管理
1. 侧边栏 → Users
2. 看到 2 个 mock 用户（admin/editor_li）+ 社交标签
3. Add User → 创建新用户
4. 停用/激活用户
5. 删除用户

### 场景 6：系统监控
1. 侧边栏 → Monitoring
2. 模块健康卡片（6 个绿灯）
3. 性能指标（延迟/文档数/运行时间）
4. 最近日志列表（INFO/WARN/ERROR 标签）

### 场景 7：Settings
1. 侧边栏 → Settings
2. 语言选择下拉
3. 主题切换（Light/Dark/System）

---

## 五、Playwright 自动化测试

### M6
```bash
cd E:\myCode\RAG\m6-user-portal
npx playwright test --reporter=list
# 预期：9/9 passing
```

### M7
```bash
cd E:\myCode\RAG\m7-admin-portal
npx playwright test --reporter=list
# 预期：13/13 passing
```
