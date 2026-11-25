# Rex CRM

[English](README.md) | **中文**

面向房产中介的 CRM：管理**客户**、**房源**和**销售管道**，并配套 AI 助手、公开房源网站、
邮件线索自动入库和数据分析。

## 架构

```
                       ┌──────────── 浏览器 ─────────────┐
                       │                                 │
         经纪人用 CRM  :8080                    买家看房源  :3000
                       │                                 │
             ┌─────────▼─────────┐             ┌─────────▼─────────┐
             │ web（React 前端） │             │ portal（Next.js） │
             │ + nginx 反向代理  │             │ 公开房源网站      │
             └───┬───────────┬───┘             └─────────┬─────────┘
           /api/ │           │ /api/ai/                  │ GraphQL
                 │           │                 ┌─────────▼─────────┐
                 │           │                 │ gateway（GraphQL）│
                 │           │                 └─────────┬─────────┘
                 ▼           ▼                           │ /api/public/*
       ┌──────────────┐  ┌──────────────────┐            │
       │ api（Laravel）│◄─┤ ai（Python）     │            │
       │ 核心业务     │◄─┼──────────────────┼────────────┘
       └──┬────────┬──┘  │ AI 助手/匹配/评分│
          │        │     └────────┬─────────┘
          │        └─► worker（队列任务）
          ▼                       ▼
   PostgreSQL（数据 + pgvector 向量）   Redis（缓存 + 队列）

  进入 CRM：邮件线索管道（AWS Lambda）、MCP 服务器（让 Claude 操作 CRM）
  离开 CRM：PySpark 分析 → Postgres / Parquet / Databricks / Snowflake
```

## 模块

| 目录 | 技术 | 功能 |
|---|---|---|
| [`backend/`](backend/) | Laravel 11、Sanctum、PostgreSQL、Redis | 核心 API：客户、房源、交易、看板、仪表盘；公开房源和咨询接口；外部线索接口（受限 token） |
| [`frontend/`](frontend/) | React 19、TypeScript、Vite、TanStack Query | 经纪人界面：仪表盘、可拖拽交易看板、客户、房源、买家匹配、Ask Rex 助手、Insights 分析 |
| [`ai/`](ai/) | FastAPI、LangGraph、Claude、pgvector、PyTorch | Ask Rex 智能体（调用工具查 CRM）、RAG 语义搜索、买家与房源匹配、成交概率预测（附原因解释） |
| [`mcp/`](mcp/) | TypeScript、MCP SDK | 让 Claude Code / Claude 桌面版用自然语言查询和更新 CRM（9 个工具） |
| [`portal/`](portal/)、[`gateway/`](gateway/) | Next.js 16、GraphQL Yoga | 公开房源网站：浏览、筛选、相似房源、看房咨询（自动进 CRM 成为线索） |
| [`lead-pipeline/`](lead-pipeline/) | AWS SAM、Lambda、S3、DynamoDB、SQS、Bedrock | 房产网站询盘邮件 → 提取线索 → 写入 CRM，幂等、可重试、有死信队列 |
| [`analytics/`](analytics/) | PySpark、Delta、Databricks、Snowflake | 每晚生成分析表：交易明细、郊区市场、线索来源漏斗、经纪人业绩、阶段耗时 |
| [`k8s/`](k8s/) | Kubernetes、kustomize | GKE 部署清单 |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | GitHub Actions | 所有模块的测试和构建 → 推送镜像 → 部署 GKE 和 AWS 线索管道 |

更多细节（英文）：[ai](ai/README.md)、[mcp](mcp/README.md)、[portal + gateway](portal/README.md)、[lead-pipeline](lead-pipeline/README.md)、[analytics](analytics/README.md)。

## 快速开始（需要 Docker Desktop）

> 在新电脑上从零安装（软件、换行符、`.env`、各模块、云端登录）：见 [SETUP-ON-NEW-PC.md](SETUP-ON-NEW-PC.md)。

```bash
docker compose up --build -d                    # 第一次 10–20 分钟
docker compose exec api php artisan db:seed     # 写入演示数据
```

| 地址 | 内容 |
|---|---|
| http://localhost:8080 | CRM，登录 `admin@rexcrm.test` / `password` |
| http://localhost:3000 | 公开房源网站 |
| http://localhost:4000/graphql | GraphQL 网关 |
| http://localhost:8000/api/health | Laravel API |
| http://localhost:8001/api/ai/health | AI 服务 |

- Ask Rex 助手需要在 `.env` 里设置 `ANTHROPIC_API_KEY`（按量计费）。匹配和成交概率不需要。
- VS Code：`Ctrl+Shift+P` → `Tasks: Run Task`，已配置 up / down / seed / 测试等任务。
- 只改前端：`cd frontend && npm install && npm run dev`（http://localhost:5173，`/api` 代理到 `localhost:8000`）。

可选服务：

```bash
docker compose --profile aws up -d                     # 本地邮件线索管道（LocalStack 模拟 S3 + DynamoDB）
docker compose --profile analytics run --rm analytics  # PySpark 分析，结果显示在 Insights 页面
```

## 测试

```bash
docker compose --profile test run --rm test                 # 后端
docker compose --profile test run --rm ai-test              # AI 服务
docker compose --profile test run --rm lead-pipeline-test   # 邮件线索管道
docker compose --profile test run --rm analytics-test       # 分析任务
cd frontend && npm test     # gateway、portal、mcp 同理
```

## API 速览

所有接口在 `/api` 下。除登录、健康检查和 `/public/*` 外，都需要 `Authorization: Bearer <token>`。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/login` | 登录，返回 token |
| GET / POST | `/auth/me`、`/auth/logout` | 当前用户 / 退出 |
| CRUD | `/contacts`、`/properties`、`/deals` | 客户、房源、交易（支持搜索和筛选） |
| PATCH | `/deals/{id}/stage` | 换阶段（同步保存，并入队 Worker 记录历史） |
| POST / DELETE | `/deals/{id}/notes` | 添加 / 删除备注 |
| GET | `/pipeline`、`/dashboard` | 看板和仪表盘（Redis 缓存，交易变更时自动清除） |
| GET | `/insights` | 分析结果 |
| GET | `/public/listings`、`/public/listings/{id}` | 公开房源（无需登录，有限流） |
| POST | `/public/enquiries` | 网站看房咨询 |
| POST | `/integrations/leads` | 外部线索（需要 `leads:write` 受限 token） |
| * | `/ai/*` | AI 服务：`ask`、`matches/...`、`deals/win-probability` |

交易阶段：`lead → contacted → inspection → offer → negotiation → won / lost`。

## 部署

- **云端（免费层）**：AWS 线索管道、Databricks、Snowflake 已部署。部署了什么、怎么删除：见 [docs/CLOUD-DEPLOY.md](docs/CLOUD-DEPLOY.md)。
- **GKE**：清单在 [`k8s/`](k8s/)。一次性 GCP 配置见 [docs/ai-workflow.md](docs/ai-workflow.md)。因为会产生费用，目前没有部署。
- **Claude API / Bedrock**：按量计费，默认关闭。

## 开发方式

开发规范见 [CLAUDE.md](CLAUDE.md)，流程见 [docs/ai-workflow.md](docs/ai-workflow.md)。在分支上开发、开 PR、CI 通过后由人合并，不直接推 `main`。

## 已知限制

- 没有按角色细分权限：所有登录用户都能查看和修改全部数据（`users.role` 字段已预留）。
- 房源图片上传、邮件 / 短信提醒尚未实现。
