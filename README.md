# Marine & Offshore Expert System

Professional Retrieval-Augmented Generation (RAG) intelligent Q&A system for the ship and offshore engineering industry.

**Supported Languages**: English | 中文 | 한국어 | 日本語 | Norsk

## Overview

This system integrates global classification society rules (CCS/DNV/ABS/LR/BV etc.), IMO regulations, multi-discipline engineering knowledge (structural/mechanical/piping/electrical/communication/automation), vessel-type-specific data, and manufacturer equipment documentation to provide precise, citation-backed answers.

## Deployment Modes

- **Personal**: Single-user local deployment, zero external dependencies
- **Enterprise**: On-premise multi-user deployment with enterprise auth
- **SaaS**: Multi-tenant cloud service with billing and elastic scaling

## Architecture

8 independent modules across 5 layers:

```
M8: API Gateway → M5: QA Engine → M3: Retrieval / M4: Knowledge Graph → M2: Storage → M1: Doc Parsing
M6: User Portal / M7: Admin Portal → M5
```

## Quick Start (Personal Edition)

```bash
# 1. Clone and install
git clone <repo-url> && cd marine-rag
pip install -r requirements.txt

# 2. Start with personal config
cp deploy/personal/deploy.yaml .
python -m m5_qa_engine.src.server

# 3. Open http://localhost:8000
```

## API Access

OpenAI-compatible API endpoint:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="your-api-key")
response = client.chat.completions.create(
    model="marine-rag",
    messages=[{"role": "user", "content": "DNV 对 LNG 船货舱结构的要求是什么？"}]
)
```

## Documentation

- [Design Specification](docs/superpowers/specs/rag-system-design-2026-05-12.md)
- [Development Plan](.dev/planning.md)

## License

Proprietary. All rights reserved.
