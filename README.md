# Rex CRM

房产中介 CRM：管理**客户**、**房源**和**销售管道**。按架构图实现：

```
浏览器 (React) --HTTPS--> 负载均衡 (Ingress) --路由--> Laravel API --读写--> PostgreSQL
                                                         |入队/缓存
                                                         v
                                                       Redis --取任务--> 队列 Worker --写库--> PostgreSQL
Git 仓库 --任务/代码--> AI 编码智能体 --提交 PR--> CI 构建 --推送镜像--> 镜像仓库 --部署--> GKE
```

| 目录 | 内容 |
|------|------|
| `backend/` | Laravel 11 API（Sanctum 令牌认证、PostgreSQL、Redis 队列和缓存） |
| `frontend/` | React 19 + TypeScript + Vite（登录、仪表盘、客户、房源、可拖拽销售管道看板） |
| `compose.yaml` | 本地一键运行：postgres、redis、api、worker、web |
| `k8s/` | GKE 部署清单（kustomize）：Ingress、API、Worker、Web、Redis、PostgreSQL |
| `.github/workflows/ci.yml` | 测试 → 构建镜像 → 推送 Artifact Registry → 部署 GKE |
| `CLAUDE.md`、`docs/ai-workflow.md` | AI 智能体开发规范和流程（图下半部分） |

## 快速开始（需要 Docker Desktop）

```bash
docker compose up --build          # 第一次会下载镜像并安装 PHP 依赖，需要几分钟
docker compose exec api php artisan db:seed     # 灌入演示数据（另开一个终端）
```

打开 http://localhost:8080 ，登录 `admin@rexcrm.test` / `password`。

- API 直连：http://localhost:8000/api/health
- 在 VS Code 里：`Ctrl+Shift+P` → `Tasks: Run Task`，已配置好 up / down / seed / 测试等任务
- 只改前端时：`cd frontend && npm install && npm run dev`（http://localhost:5173，自动把 `/api` 代理到 `localhost:8000`）

## 验证“队列 Worker”真的在工作

1. 在销售管道页面把一张卡片拖到另一列，界面立即更新（API 已保存阶段）。
2. 点开这张卡片，约 1 秒后“Activity”里出现 *Stage changed from X to Y*。这条记录由 Worker 从 Redis 取任务后写入数据库。
3. 把卡片拖到 **Won**：关联房源会被 Worker 自动标记为 *Sold*。
4. `docker compose logs -f worker` 可看到任务执行日志。

## 测试

```bash
docker compose --profile test run --rm test     # 后端（SQLite 内存库，不需要其他服务）
cd frontend && npm test                           # 前端
```

## API 速览（均在 `/api` 下，除登录和健康检查外需要 `Authorization: Bearer <token>`）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/login` | 登录，返回 token |
| GET | `/auth/me`、POST `/auth/logout` | 当前用户 / 退出 |
| GET/POST/PUT/DELETE | `/contacts`、`/contacts/{id}` | 客户（支持 `q`、`type`、`page`） |
| GET/POST/PUT/DELETE | `/properties`、`/properties/{id}` | 房源（支持 `q`、`status`、`type`、`min_price`、`max_price`） |
| GET/POST/PUT/DELETE | `/deals`、`/deals/{id}` | 交易 |
| PATCH | `/deals/{id}/stage` | 换阶段（同步保存 + 入队 Worker 任务） |
| POST | `/deals/{id}/notes` | 添加备注 |
| GET | `/pipeline` | 看板数据（按阶段分组，Redis 缓存 5 分钟，交易变更时自动清缓存） |
| GET | `/dashboard` | 仪表盘统计（缓存 1 分钟） |

交易阶段：`lead → contacted → inspection → offer → negotiation → won / lost`。

## 部署到 GKE

见 [`docs/ai-workflow.md`](docs/ai-workflow.md) 末尾的一次性 GCP 配置。大致是：建 Artifact Registry 和 GKE 集群 → 在集群里创建 `rex-crm-secrets` → 在 GitHub 配置变量和密钥 → 推送到 `main` 后 CI 自动构建并部署。

## 诚实说明：哪些验证过，哪些没有

生成这套代码的云端环境访问不了 PHP 包仓库（Packagist），所以：

- **已验证**：前端 TypeScript 类型检查、生产构建、5 个单元测试；`compose.yaml` 配置校验；K8s 和 CI 的 YAML 语法；全部 PHP 文件语法检查。
- **未实际运行**：Laravel 后端（没有执行过 `composer install`、迁移和 PHPUnit 测试）、Docker 镜像构建、K8s 部署。后端测试已写好（认证、客户、房源、管道、Worker 任务），但第一次运行时可能暴露小问题，需要你跑一遍并把报错发给我修。
- 没有 `composer.lock`。第一次 `docker compose up --build` 会解析最新兼容版本；建议之后在 `backend/` 里生成并提交 lock 文件以固定版本。
- 没有做角色权限细分：所有登录用户可以看和改全部数据（`users.role` 字段已预留）。

## 可以继续做的

文件上传（房源图片到 GCS）、邮件/短信提醒（新的队列任务）、按角色的权限策略、Cloud SQL 替换集群内 PostgreSQL、HPA 自动扩缩 Worker。
