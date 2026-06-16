# 前端门户 Docker 打包方案（待执行）

> **状态**: 📌 待执行（先完成本地功能测试，验证所有功能后再打包）
> **创建日期**: 2026-06-16

## 背景

当前 Docker 部署（`deploy/personal/docker-compose.yml`）只包含后端 M8 API 服务。新用户期望"双击 start.bat 就能用浏览器进入完整图形界面"，但 M6 用户门户、M7 管理门户目前需要本地用 npm 手动启动。

本方案把 M6/M7 打包进 docker compose，实现真正开箱即用。

## 打包前必须解决的 5 个阻塞问题

### 1. 后端 CORS（`m8-api-gateway/m8_gateway/core/app.py`）
浏览器从 M6(3000)/M7(3001) 跨端口调 M8(18000) 会被拦截。需在 `create_app` 内 app 创建后加 CORSMiddleware：
```python
from fastapi.middleware.cors import CORSMiddleware
_default_origins = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001"
_cors_origins = [o.strip() for o in os.environ.get("M8_CORS_ORIGINS", _default_origins).split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
```
**注**：本地功能测试时也需要这个 CORS 修改（前端 npm 跑在 3000/3001 调后端 18000），所以这个会在测试阶段就做。

### 2. 默认管理员 Bootstrap（新建 `m8-api-gateway/m8_gateway/core/bootstrap.py`）
全新部署 users 表为空，M7 登录需 admin API key 但无法获得第一个。
- 幂等函数 `bootstrap_admin_if_needed(db_path)`：users 表空时插入 `moes-admin`(tier=admin, is_admin=1)，用 KeyManager 生成 key，写入 `<db_dir>/admin_key.txt`(0600) 并打印日志
- 在 app.py startup() 中 KeyManager 初始化后调用，try/except 失败不阻塞
- 复用 `_hash_password`(auth.py:166)、`KeyManager.generate_key`(key_manager.py:150)
- 用户名用 `moes-admin`（"admin" 在 `_BANNED_USERNAMES` auth.py:56）

### 3. 持久化 db 路径（docker-compose.yml m8 服务）
environment 追加 `M8_DB_PATH=/data/m8_gateway.db`，使 admin key 和用户数据落到 `marine_data` volume（当前默认 `./data/m8_gateway.db` 在容器内解析为 `/app/data/`，不与 volume `/data` 重合，重建后丢失）。

### 4. next.config.ts（m6、m7 各一份）
```ts
output: "standalone",
outputFileTracingIncludes: { "/**/*": ["./messages/**/*.json"] },
```
`src/i18n/request.ts` 用动态 import 加载 messages，standalone 追踪不到，必须加 tracing。

### 5. 前端 Dockerfile + .dockerignore（m6、m7 各一份）
多阶段 `node:20-alpine`：deps(npm ci) → builder(ARG NEXT_PUBLIC_API_URL + npm run build + cp public/static) → runner(非 root, HOSTNAME=0.0.0.0, CMD node server.js)。`NEXT_PUBLIC_API_URL` 是构建期内联，必须作 build-arg。

## 已验证事实
- Next.js 16 支持 `output:'standalone'`（node_modules/next/dist/docs/.../output.md 确认）
- `_hash_password(password:str)->str`(auth.py:166)、`KeyManager(db_path)`、`async generate_key(user_id,tier="basic")->str`(key_manager.py:89,150)
- users 表已含 `is_admin` 列
- 前端 fetch 都在 client component（非 SSR）

## docker-compose.yml 新增服务
```yaml
m6: { context: ../../m6-user-portal, build-arg NEXT_PUBLIC_API_URL=http://localhost:18000, ports 3000:3000, PORT=3000, depends_on m8 healthy }
m7: { 同上, ports 3001:3001, PORT=3001 }
```

## start.bat 更新（:ready 段）
打印 3 个地址（3000 用户门户 / 3001 管理门户 / 18000/docs）+ `docker exec marine-m8 cat /data/admin_key.txt` 获取 admin key，默认打开 http://localhost:3000。

## 执行顺序（减少试错）
1. 后端 CORS + bootstrap + M8_DB_PATH → curl 验证 admin-login + CORS 头
2. next.config.ts → 本地 `npm run build` 验证 standalone 产物含 messages
3. Dockerfile + .dockerignore → docker build 验证
4. docker-compose.yml + start.bat → 整体 up 端到端验证

## 验证清单
- [ ] 5 容器全 healthy
- [ ] admin-login 拿 key 后 M7 登录成功
- [ ] M6 注册新用户成功
- [ ] DevTools Network 看到 `Access-Control-Allow-Origin` 头
- [ ] down/up 后 key 仍可用（持久化）
- [ ] 配置 LLM 后 qa_engine_ready=true

## 当前进展
- ✅ 方案设计完成（含 Plan agent 详细设计 + 关键函数签名验证）
- ⏳ 等待本地功能测试全部通过后再执行打包
