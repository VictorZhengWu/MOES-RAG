# Marine & Offshore Expert System（船舶与海洋工程专家系统）

面向船舶与海洋工程行业的专业检索增强生成（RAG）智能问答系统。

**支持语言**：English | 中文 | 한국어 | 日本語 | Norsk

## 概述

本系统整合全球主要船级社规范（CCS/DNV/ABS/LR/BV 等）、国际海事规则（IMO）、多专业领域知识（结构/机械/管系/电气/通讯/自动化）、各类型船舶与海洋结构物资料、以及主流厂商配套产品数据，提供精准的、带引证溯源的智能问答服务。

## 部署模式

- **个人版**：单用户本地部署，零外部依赖
- **企业版**：企业内部服务器多用户部署
- **SaaS 版**：多租户云服务，支持弹性伸缩与计费

## 系统架构

8 大独立模块，5 层架构：

```
M8: API 网关 → M5: 智能问答引擎 → M3: 检索引擎 / M4: 知识图谱 → M2: 存储抽象层 → M1: 文档解析引擎
M6: 用户前端 / M7: 管理后台 → M5
```

## 快速开始（个人版）

```bash
# 1. 克隆并安装
git clone <repo-url> && cd marine-rag
pip install -r requirements.txt

# 2. 使用个人版配置启动
cp deploy/personal/deploy.yaml .
python -m m5_qa_engine.src.server

# 3. 浏览器打开 http://localhost:8000
```

## API 接入

OpenAI 兼容 API 端点：

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="your-api-key")
response = client.chat.completions.create(
    model="marine-rag",
    messages=[{"role": "user", "content": "DNV 对 LNG 船货舱结构的要求是什么？"}]
)
```

## 文档

- [设计规范](docs/superpowers/specs/rag-system-design-2026-05-12.md)
- [开发规划](.dev/planning.md)

## 许可证

专有软件。保留所有权利。
