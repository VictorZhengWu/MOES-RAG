# Phase 2 后端核心 — 开发总结

> **日期**：2026-05-23 | **范围**：M2 存储抽象层 + M1 文档解析引擎
> **测试状态**：M2 42 passed, M1 118 passed | **浏览器验证**：部分完成

---

## 一、已完成模块

### M2 — 存储抽象层 ✅

| 子任务 | 名称 | 状态 |
|--------|------|:--:|
| 00050-01 | 配置解析 (config.py) | ✅ |
| 00050-02 | 工厂函数 (factory.py) | ✅ |
| 00050-03 | StorageManager | ✅ |
| 00050-04 | ChromaDB VectorStore | ✅ |
| 00050-05 | Meilisearch DocumentIndex | ✅ |
| 00050-06 | SQLite RelationalDB | ✅ |
| 00050-07 | LocalFS FileStore | ✅ |
| 00050-08 | 集成测试 | ✅ |
| 00050-09 | 打包验证 | ✅ |

**交付**：28 个源文件，~3,600 行，42 tests, 12 次提交
**验证**：`python demo_m2.py` 演示 4 个后端协同工作

### M1 — 文档解析引擎 ✅

| 子任务 | 名称 | 状态 |
|--------|------|:--:|
| 00060-01 | 项目骨架 + GPU 检测 | ✅ |
| 00060-02 | 格式路由 | ✅ |
| 00060-03 | Docling 后端 | ✅ |
| 00060-04 | Marker/MinerU 骨架 | ✅ |
| 00060-05 | 主转换器 | ✅ |
| 00060-06 | 元数据提取 | ✅ |
| 00060-07 | 质量门禁 | ✅ |
| 00060-08 | 序列化 + 图片管理 | ✅ |
| 00060-09 | Chunking | ✅ |
| 00060-10 | M2 桥接 | ✅ |
| 00060-11 | CLI + Web | ✅ |
| 00060-12 | 打包验证 | ✅ |

**交付**：23 个源文件，~7,200 行, 118 tests, 15+ 次提交
**Web UI**：`http://127.0.0.1:8005`，服务器端口启动

---

## 二、发现的问题与修复

### M2 开发期间

| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| F001 | ChromaDB 元数据字段截断 | ChromaDB 只支持 flat scalar metadata | 记录为已知限制，Phase 3 扩展 |
| F002 | Meilisearch filter 注入 | `delete()` 直接拼接 f-string | 改用 `_build_meili_filter()` |
| F003 | logger.exception 打印完整堆栈 | 健康检查失败不应打印 traceback | 改为 `logger.warning()` |
| F004 | `src/` 目录 editable install 失败 | Windows + setuptools package-dir 不兼容 | 改为 `m2_storage/` 常规布局 |
| F005 | GBK 编码错误 | 中文 Windows 默认编码非 UTF-8 | 源文件加 `# -*- coding: utf-8 -*-` |

### M1 开发期间

| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| F006 | Web 页面下拉框为空 | JS 动态生成 option 依赖 JSON 嵌入，escaping 易出错 | 改为服务端渲染 `<option>` 标签 |
| F007 | 拖放/点击不工作 | `addEventListener` + 箭头函数兼容性问题 | 改用 `onclick`/`ondrop` 原生属性 |
| F008 | 目录名 = 临时文件名 `tmpz_8azysb` | Web 上传用 `tempfile`，`Path(source).stem` 取到的是临时文件名 | 新增 `doc_name` 参数，Web 端传原始文件名 |
| F009 | 同名文件冲突时间戳用临时名 | 冲突检测用了 `Path(source).stem` 而非 `doc_basename` | 改为用已计算的 `doc_basename` |
| F010 | `<!-- image -->` 占位符 | Docling 默认 `export_to_markdown()` 用 PLACEHOLDER 模式 | 后处理替换为 `![](figures/figure_XXX.png)` |
| F011 | 选 HTML 格式仍输出 MD | 输出保存逻辑只写 `.md` 文件 | 按格式输出 `.html`/`.md`/`.json` |
| F012 | Export Tables CSV 空 | `tables_csv` 在 API 响应中但未写入文件 | 写入 `tables/tables.csv` |
| F013 | PaddleOCR 报错 `'NoneType' object has no attribute 'kind'` | 后端 OCR 映射表缺少 `paddleocr`，返回 None | 添加 `"paddleocr": "RapidOcrOptions"` 映射 |
| F014 | 服务器僵尸进程 | `taskkill /F /IM python.exe` 在 Windows 上不可靠 | 用 `TerminateProcess` Windows API 强制终止 |
| F015 | 同名文件冲突始终出现 bug | 修了 3 次——每次只修了一个代码路径 | 最终在 `doc_name` 参数和冲突检测两处同时修正 |

### 反复出现的同一问题：文件命名

| 次数 | 发现的问题 | 修复 |
|:--:|------|------|
| 1 | 目录名为 UUID | 改为 `Path(source).stem` |
| 2 | Web 上传目录名为 temp 名 | 新增 `doc_name` 参数 |
| 3 | 冲突时间戳用 temp 名 | 冲突路径改用 `doc_basename` |
| 4 | 浏览器端仍错误 | 服务器未重启，旧进程未杀死 |

**根因**：我每次只修复一个代码路径，修复后只在 Python 层面测试，没有在浏览器端验证完整流程。

---

## 三、未完成工作

### 代码已写但未接入管线

| 组件 | 代码位置 | 管线阶段 | 说明 |
|------|---------|:--:|------|
| 元数据提取 | `enrichments/marine_metadata.py` | 阶段 3 | ✅ 已接入 converter，未用真实 PDF 验证 |
| 复杂度评分 | `core/quality.py` | 阶段 5 | ❌ 代码写了，converter 未调用 |
| 跨页表格合并 | `enrichments/table_merger.py` | 阶段 4 | ❌ 骨架 |
| Header-to-Cell 注释 | `enrichments/table_annotator.py` | 阶段 4 | ❌ 骨架 |
| Hybrid Chunker | `output/chunker.py` | 阶段 6 | ❌ 代码写了，converter 未调用 |
| M2 存储写入 | `integration/m2_bridge.py` | — | ❌ 代码写了，从未测试 |

### 后端服务未就绪

| 组件 | 状态 | 所需操作 |
|------|:--:|------|
| Marker 后端 | ❌ 骨架 | `pip install marker-pdf` + 测试 |
| MinerU 后端 | ❌ 骨架 | `pip install magic-pdf` + 测试 |
| Tesseract OCR | ❌ 未安装 | 下载安装 Tesseract 二进制 + `pip install pytesseract` |
| SuryaOCR | ❌ 未安装 | `pip install docling-surya`（注意 GPL） |
| VLM Pipeline | ❌ 未测试 | 需 GPU 模型或 API 端点 |

### Web UI 浏览器验证清单（17 项未测，见上文）

### 设计规范要求但未实现

| 功能 | 设计规范章节 | 当前状态 |
|------|:--:|------|
| DocTags 输出格式 | §4.2 | 未暴露 |
| 图片描述（Picture Description） | Docling enrichment | 后端支持，UI 有复选框，未测试 |
| 图片分类 | Docling enrichment | 未暴露 |
| PII 脱敏 | Docling 示例 | 未实现 |
| 单文件下载（含图片打包） | — | 仅支持下载文本 |
| 解析历史记录 | — | 无数据库持久化 |

---

## 四、流程缺陷

### 测试方法的系统性不足

| 我的做法 | 问题 | 后果 |
|---------|------|------|
| `curl` 测试 API 端点 | 绕过浏览器 UI，发现不了 JS/HTML bug | 下拉框为空、拖放不工作 |
| 用自制 HTML 测试文件 | 不含表格/图片/中文，无法触发真实解析路径 | 图片占位符 bug 多日后才发现 |
| 只测"第一次"场景 | 不测同名文件冲突、批量多文件 | 冲突逻辑修了 4 次 |
| 修完即 `pytest` | pytest 覆盖不到 Web UI、文件命名、图片输出 | 浏览器端问题反复出现 |
| 不重启服务器 | 旧进程跑旧代码，我的修复从未被用户拿到 | PaddleOCR 报错反复出现 |
| `taskkill /F /IM python.exe` | Windows 上不可靠，僵尸进程残留 | 用户始终连着旧服务器 |

### 需要的改进

1. **每次修改 Web 代码后**，必须确认旧服务器已终止，新服务器已启动
2. **浏览器端测试必须在真实 PDF 上进行**，不能只用 HTML 测试文件
3. **同名文件冲突、批量多文件**必须加入每次验证流程
4. **新 OCR/后端引擎**需在实际安装后完整走一遍流程，不能只验证代码路径

---

## 五、经验教训

1. **服务器僵尸进程是隐蔽杀手** — 代码改了、提交了、pytest 过了，但用户拿到的还是旧代码。每次修改 Web 相关代码后，必须确认服务器进程 PID，强制终止后重启
2. **API 测试不能替代浏览器测试** — JS 错误、CSS 样式、拖放事件、DOM 操作都在 curl 覆盖范围之外
3. **单一场景测试不够** — 同名文件冲突、空目录、批量多文件、特殊字符文件名——每个都触发过不同的代码路径 bug
4. **`Path(source).stem` 是陷阱** — 在 Web 上传场景下，`source` 是临时文件路径，不是原始文件名。必须单独传递原始文件名
5. **默认值不等于正确值** — `export_to_markdown()` 默认用 `ImageRefMode.PLACEHOLDER` 输出 `<!-- image -->`，需显式设置或后处理
6. **OCR 引擎映射表必须完整** — 缺少一个 key 就返回 None，Docling 收到 None 就崩溃，错误信息是 `'NoneType' object has no attribute 'kind'`——毫无提示是 OCR 配置问题

---

## 六、下一步

1. 完成浏览器端 17 项验证
2. 接入已写但未连管的管线组件（quality, chunker, M2 bridge）
3. 完善表格处理（合并、注释）
4. 安装并验证 Marker、MinerU、Tesseract、SuryaOCR
5. 推进 M3（检索引擎）设计

---

*Phase 2 进度：M2 ✅ | M1 🔄（代码完成，浏览器验证进行中）| M3 🔲*
