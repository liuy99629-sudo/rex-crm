# 在另一台电脑上安装 Rex CRM（完整步骤）

按顺序做，每一步都有“怎么确认成功”。第 1–5 步装好整个本地系统（CRM、AI 助手、公开房源网站、
测试）；第 6 步之后是可选模块和云端（AWS、Databricks、Snowflake），不用就跳过。

> 适用系统：Windows 10/11。命令默认在 **PowerShell** 里运行；写着 “Git Bash” 的在 Git Bash 里运行。

---

## 0. 旧电脑上的东西：什么都不用带

| 东西 | 新电脑上怎么办 |
|---|---|
| Snowflake 私钥 | **不带**。在新电脑运行一条命令生成新的（第 9c 步），再在 Snowflake 网页里粘贴运行一行 SQL |
| `.env` | 不用带：旧电脑从没填过值。新电脑从 `.env.example` 复制（第 3 步） |
| 数据库数据 | 不用带：新电脑写入演示数据（第 4 步） |
| AWS、Databricks 登录 | 新电脑各登录一次，浏览器里点确认（第 9a、9b 步）。云上已部署的东西不受影响 |
| 账号、工作区地址、用户名 | 都写在本文第 9 步里 |

为什么私钥不放进 GitHub：这个仓库是**公开**的，任何人拿到私钥就能登录你的 Snowflake。
所以私钥只留在各自电脑的 `C:\Users\<你>\.rex-secrets\`，`.gitignore` 也挡住了 `*.p8`、`*.pem`。

---

## 1. 安装软件

PowerShell（管理员）里逐条运行：

```powershell
winget install --id Git.Git -e
```

```powershell
winget install --id Docker.DockerDesktop -e
```

```powershell
winget install --id OpenJS.NodeJS.LTS -e
```

```powershell
wsl --install
```

装完**重启电脑**，然后打开 Docker Desktop，等左下角显示 “Engine running”。
设置里确认 *Use the WSL 2 based engine* 已勾选；内存建议给 Docker 至少 6 GB（AI 服务和 Spark 比较吃内存）。

确认：

```powershell
git --version; node --version; docker version
```

Node 需要 20 或以上（装的是 22 LTS 即可）。PHP、Python、Java **不用装**，它们都在 Docker 镜像里。

可选（用到对应模块再装）：

| 工具 | 安装命令 | 用途 |
|---|---|---|
| GitHub CLI | `winget install --id GitHub.cli -e` | 开 PR、看 CI |
| Claude Code | `winget install --id Anthropic.ClaudeCode -e`（或在 Claude 桌面版里用 Code 页） | 继续让 Claude 开发 |
| AWS CLI v2 | `winget install --id Amazon.AWSCLI -e` | 第 8 步 |
| Databricks CLI | `winget install --id Databricks.DatabricksCLI -e` | 第 9 步 |

---

## 2. 拉代码（注意换行符设置）

**先**设置换行符，再 clone。否则 Windows 版 Git 默认会把文件转成 CRLF，Linux 容器里的脚本会坏：

```powershell
git config --global core.autocrlf false
```

```powershell
cd $HOME
```

```powershell
git clone -b feat/cloud-deploy https://github.com/liuy99629-sudo/rex-crm.git
```

```powershell
cd rex-crm
```

关于分支：
- `feat/cloud-deploy` 包含**全部**功能（6 个模块 + 云端部署配置），现在用它。
- 等 PR #10、#11 合并进 `main` 之后，直接 `git clone https://github.com/liuy99629-sudo/rex-crm.git`（默认就是 `main`）。
- 仓库里有 `.gitattributes` 固定为 LF，所以就算忘了上面那条设置，新 clone 的文件也是对的。

确认：`git status` 显示 *working tree clean*。

---

## 3. 配置 `.env`（可选，不配也能跑）

```powershell
Copy-Item .env.example .env
```

用记事本打开 `.env`，按需去掉行首 `#` 并填值。全部留空时系统也能完整启动，只是对应功能关闭：

| 变量 | 作用 | 不填会怎样 |
|---|---|---|
| `ANTHROPIC_API_KEY` | “Ask Rex” AI 助手调用 Claude（platform.claude.com 的 key，按量计费；Claude.ai 会员不包含 API） | 助手提示未配置；匹配、成交概率等不需要 key 的 AI 功能照常 |
| `AI_MODEL` | 默认 `claude-opus-5-5` | 用默认 |
| `LEAD_PIPELINE_TOKEN` | 本地邮件线索管道调用 CRM 的 token（第 7 步生成） | 线索管道无法写入 CRM |
| `ANALYTICS_SINKS` | 分析任务输出到哪里，默认 `postgres,parquet` | 用默认 |
| `SNOWFLAKE_*` | 用密码登录 Snowflake 时填（推荐改用第 9 步的密钥方式） | 不写 Snowflake |
| `DB_PASSWORD` / `APP_KEY` | 一般不用改 | 用内置开发值 |

`.env` 已在 `.gitignore` 里，永远不要提交它。

---

## 4. 启动整个系统

```powershell
docker compose up --build -d
```

第一次构建要 10–20 分钟（下载镜像、装依赖、AI 服务要下载 PyTorch 和向量模型）。之后再启动只要几十秒。

查看状态，等所有服务都是 `running` / `healthy`：

```powershell
docker compose ps
```

数据库表在 API 启动时自动建好。写入演示数据（第一次必须做）：

```powershell
docker compose exec api php artisan db:seed
```

打开：

| 地址 | 是什么 |
|---|---|
| http://localhost:8080 | CRM 主界面。登录 `admin@rexcrm.test` / `password` |
| http://localhost:3000 | 公开房源网站（Next.js） |
| http://localhost:4000/graphql | GraphQL 网关 |
| http://localhost:8000/api/health | Laravel API 健康检查 |
| http://localhost:8001/api/ai/health | AI 服务健康检查 |

确认：能登录 CRM，看到 Dashboard、Pipeline、Contacts、Properties、Insights 页面有数据。

常用：

```powershell
docker compose logs -f api worker ai
```

```powershell
docker compose down
```

（`docker compose down -v` 会**删除数据库数据**，重来时才用。）

---

## 5. 跑全部测试（确认安装没问题）

都在 Docker 里跑，不需要任何 key 或云账号：

```powershell
docker compose --profile test run --rm test
```

```powershell
docker compose --profile test run --rm ai-test
```

```powershell
docker compose --profile test run --rm lead-pipeline-test
```

```powershell
docker compose --profile test run --rm analytics-test
```

前端和 Node 项目（在本机 Node 上跑）：

```powershell
cd frontend; npm ci; npm test; npm run build; cd ..
```

```powershell
cd gateway; npm ci; npm test; cd ..
```

```powershell
cd portal; npm ci; npm test; cd ..
```

```powershell
cd mcp; npm ci; npm test; cd ..
```

---

## 6. 可选：让 Claude Code 直接操作 CRM（MCP 服务器）

仓库根目录的 `.mcp.json` 已经登记了 `rex-crm` MCP 服务器，只要构建并提供登录 token：

```powershell
cd mcp; npm ci; npm run build; npm run login; cd ..
```

`npm run login` 会用演示账号登录并打印一个 token。把它设成用户环境变量（只需一次）：

```powershell
[Environment]::SetEnvironmentVariable("REX_API_TOKEN", "<上一步打印的 token>", "User")
```

然后**重开** Claude Code / Claude 桌面版，在项目里就能用 `search_contacts`、`get_pipeline`、`move_deal_stage` 等工具。
重新 seed 数据库后 token 会失效，再跑一次 `npm run login`。

---

## 7. 可选：本地邮件线索管道（模拟 AWS，不花钱）

用 LocalStack 模拟 S3 + DynamoDB，自动把示例邮件变成 CRM 线索。

1. 生成只能写线索的 token：
   ```powershell
   docker compose exec api php artisan rex:integration-token lead-pipeline
   ```
2. 把打印出的 token 填进 `.env`：`LEAD_PIPELINE_TOKEN=...`
3. 启动：
   ```powershell
   docker compose --profile aws up -d
   ```
4. 确认：`docker compose logs lead-pipeline` 显示处理了示例邮件；CRM 的 Contacts 里出现新线索。

---

## 8. 可选：PySpark 分析任务（本地）

```powershell
docker compose --profile analytics run --rm analytics
```

结果写入 Postgres 的 `analytics_*` 表（CRM 的 **Insights** 页面显示）和 `warehouse` 卷里的 Parquet。

---

## 9. 可选：云端（全部是免费层；账号已经在旧电脑上开好）

当前云上已经部署好的东西、以及如何删除，见 [docs/CLOUD-DEPLOY.md](docs/CLOUD-DEPLOY.md)。
新电脑只需要**登录 CLI**，就能继续管理它们。

### 9a. AWS（邮件线索管道：S3 → Lambda → DynamoDB）

- 账号 `432596230376`，区域 `ap-southeast-2`（悉尼），CloudFormation 堆栈 `rex-lead-pipeline`。
- 已设 US$1 预算告警 `rex-crm-1usd-guard`。

登录（会打开浏览器让你确认）：

```powershell
aws configure set region ap-southeast-2
```

```powershell
aws login
```

确认：

```powershell
aws sts get-caller-identity
```

```powershell
aws cloudformation describe-stacks --stack-name rex-lead-pipeline --query "Stacks[0].StackStatus"
```

重新部署：本机没有 Python 时，用 SAM 官方容器构建和部署（Git Bash 里运行）：

```bash
cd lead-pipeline
ENVF=$(cygpath -w /tmp/aws.env); aws configure export-credentials --format env-no-export > /tmp/aws.env
MSYS_NO_PATHCONV=1 docker run --rm --env-file "$ENVF" -e AWS_REGION=ap-southeast-2 \
  -v "$(pwd -W):/src" -w /src public.ecr.aws/sam/build-python3.12 \
  sh -c "sam build && sam deploy --stack-name rex-lead-pipeline --resolve-s3 --capabilities CAPABILITY_IAM --no-confirm-changeset --parameter-overrides Extractor=rules CrmApiUrl=none"
rm /tmp/aws.env
```

`Extractor=rules` 是免费的规则提取；`Extractor=claude` 会调用 Bedrock，**按 token 收费**。

### 9b. Databricks Free Edition（分析任务 → Delta 表）

- 工作区 https://dbc-5c71dbad-77c7.cloud.databricks.com ，数据在 `workspace.rex_crm`（卷 `raw`、`code`）。

登录（会打开浏览器）：

```powershell
databricks auth login --host https://dbc-5c71dbad-77c7.cloud.databricks.com --profile rex
```

更新数据并运行（Git Bash；第一条导出本地 CRM 的快照，只含白名单字段，不含客户姓名电话）：

```bash
MSYS_NO_PATHCONV=1 docker compose --profile analytics run --rm -e EXPORT_RAW_PATH=/data/warehouse/raw -e SINKS=postgres analytics
MSYS_NO_PATHCONV=1 docker run --rm -v rex-crm_warehouse:/w -v "$(pwd -W):/out" alpine sh -c "rm -rf /out/.snapshot && cp -r /w/raw /out/.snapshot"
databricks fs cp -r .snapshot dbfs:/Volumes/workspace/rex_crm/raw --overwrite -p rex
databricks fs cp -r analytics/rex_analytics dbfs:/Volumes/workspace/rex_crm/code/rex_analytics --overwrite -p rex
rm -rf .snapshot
cd analytics && databricks bundle deploy -p rex && databricks bundle run rex_analytics -p rex
```

（卷名 `rex-crm_warehouse` 取决于仓库文件夹名；文件夹不叫 `rex-crm` 时用 `docker volume ls` 查。）

### 9c. Snowflake（30 天试用；分析结果 → `REX_CRM.ANALYTICS.REX_*`）

- 账号 `BIQXSYY-QW95202`，用户 `LIUY99629`，仓库 `REX_WH`（XS，60 秒自动挂起）。
- 用密钥对登录，不用密码。

**第一步：在新电脑生成密钥**（在仓库目录的 PowerShell 里运行，只需 Git 已安装）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\new-snowflake-key.ps1
```

它会把私钥放进 `C:\Users\<你>\.rex-secrets\`（只有你的 Windows 账号能读），
然后打印一行 `ALTER USER LIUY99629 SET RSA_PUBLIC_KEY_2 = '...';`，并**自动复制到剪贴板**。

**第二步：在 Snowflake 换上新公钥。** 打开 https://app.snowflake.com 登录，进入 Projects → Worksheets，
新建一个工作表，`Ctrl+V` 粘贴（编辑器里**只放这一行**），点 Run。
（编辑器里有多条语句时，Run 只执行光标所在那条。）
新公钥放在第 2 个位置（`RSA_PUBLIC_KEY_2`），旧电脑的密钥在第 1 个位置，两台电脑都能继续用。

运行分析并写入 Snowflake（PowerShell）：

```powershell
docker compose --profile analytics run --rm -v "$env:USERPROFILE\.rex-secrets:/secrets:ro" -e SINKS=postgres,snowflake -e SNOWFLAKE_ACCOUNT=BIQXSYY-QW95202 -e SNOWFLAKE_USER=LIUY99629 -e SNOWFLAKE_PRIVATE_KEY_FILE=/secrets/snowflake_rsa_key.p8 analytics
```

确认：Snowflake 里 `SELECT COUNT(*) FROM REX_CRM.ANALYTICS.REX_FACT_DEALS;` 有数据。

### 9d. 没有部署的（要花钱）

- **GKE**：`k8s/` 里的清单完整，但 Google Cloud 账号没有免费额度，集群会产生费用。
- **Claude API / Bedrock**：按 token 计费。需要时在 `.env` 填 `ANTHROPIC_API_KEY`，或 AWS 部署时用 `Extractor=claude`。

---

## 10. 常见问题

| 现象 | 原因 / 解决 |
|---|---|
| `error during connect ... docker_engine` | Docker Desktop 没启动，打开它等 *Engine running* |
| 容器里报 `/usr/bin/env: 'php\r'` 或 `bad interpreter` | 文件被转成了 CRLF。运行 `git config core.autocrlf false`，然后 `git rm --cached -r . -q; git reset --hard` |
| 端口被占用（8080/3000/4000/8000/8001/5432） | 关掉占用的程序，或停掉另一个 compose 项目 |
| Postgres 报 collation version mismatch | 旧卷换过镜像，运行 `docker compose exec postgres psql -U rexcrm -d rexcrm -c "REINDEX DATABASE rexcrm; ALTER DATABASE rexcrm REFRESH COLLATION VERSION;"` |
| 登录 401 / MCP 报 Unauthenticated | 重新 seed 后旧 token 失效，重新登录或 `npm run login` |
| Git Bash 里 `/data/...`、`/aws/...` 路径变成 `C:/Program Files/Git/...` | 命令前加 `MSYS_NO_PATHCONV=1` |
| `aws login` 报 *No Windows console found* | 在普通 PowerShell 窗口（不是嵌入式终端）里运行 |
| AI 服务第一次启动很慢 | 正在下载向量模型，`docker compose logs -f ai` 查看进度 |

---

## 11. 开发规范（在新电脑上继续开发前看一眼）

- 项目约定和命令在 [CLAUDE.md](CLAUDE.md)，功能介绍在 [README.md](README.md)。
- 在分支上开发，开 PR，CI 通过后由人合并。**不要直接推 `main`**。
- 不要提交 `.env`、`node_modules`、`vendor`、私钥或任何 token。
