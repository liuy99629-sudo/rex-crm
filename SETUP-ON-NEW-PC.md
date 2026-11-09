# Rex CRM：在另一台 Windows 电脑上搭建（PowerShell 命令清单）

这是在第一台电脑上做过的事情，整理成可以照着执行的命令。项目代码本身已经写好，**不需要重新生成**，只要把文件夹搬过去、装好工具、启动即可。

## 0. 在原电脑上：打包项目

项目在 `C:\Users\san96\rex-crm`。任选一种方式搬运。

**方式 A：U 盘 / 网盘（最简单）**

```powershell
cd C:\Users\san96
tar --exclude=node_modules --exclude=dist --exclude=vendor -czf rex-crm.tar.gz rex-crm
# 把 rex-crm.tar.gz 拷到新电脑
```

**方式 B：GitHub 私有仓库（推荐，后面 CI/CD 也要用）**

```powershell
cd C:\Users\san96\rex-crm
git init -b main
git add .
git commit -m "Initial commit: Rex CRM"
gh auth login                                   # 需要先装 GitHub CLI: winget install GitHub.cli
gh repo create rex-crm --private --source=. --push
```

## 1. 新电脑：安装工具

用管理员身份打开 PowerShell：

```powershell
winget install -e --id Git.Git
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Microsoft.VisualStudioCode
winget install -e --id Docker.DockerDesktop
wsl --install            # Docker Desktop 需要 WSL 2；装完按提示重启电脑
```

重启后打开 Docker Desktop，等左下角显示 **Engine running**。然后新开一个 PowerShell 验证：

```powershell
git --version; node -v; docker --version; docker compose version
```

## 2. 新电脑：安装 Claude Code

```powershell
irm https://claude.ai/install.ps1 | iex
# 或者（需要 Node）：npm install -g @anthropic-ai/claude-code
claude --version
```

VS Code 扩展（可选，在 VS Code 里用）：

```powershell
code --install-extension anthropic.claude-code
code --install-extension ms-azuretools.vscode-docker
code --install-extension bmewburn.vscode-intelephense-client
```

> 第一次在 VS Code 打开项目时，如果顶部提示 "Restricted Mode"，点 **Trust** 信任文件夹，Claude 扩展才会启用。

## 3. 新电脑：取回项目

**方式 A（压缩包）：**

```powershell
cd $HOME
tar -xzf rex-crm.tar.gz
cd rex-crm
```

**方式 B（GitHub）：**

```powershell
cd $HOME
gh auth login
gh repo clone rex-crm
cd rex-crm
```

## 4. 启动整套服务

```powershell
docker compose up --build
```

第一次会下载镜像并安装 PHP 依赖，需要几分钟。看到 api 和 worker 日志稳定后，**另开一个 PowerShell**：

```powershell
cd $HOME\rex-crm
docker compose exec api php artisan db:seed      # 灌入演示数据
start http://localhost:8080                        # 登录 admin@rexcrm.test / password
```

常用命令：

```powershell
docker compose logs -f worker      # 看队列 Worker 处理任务（拖动管道卡片时会有日志）
docker compose logs -f api         # 看 API 报错
docker compose down                # 停止（数据保留）
docker compose down -v             # 停止并清空数据库
docker compose up --build -d       # 改了后端代码后重建并后台运行
```

## 5. 测试

```powershell
docker compose --profile test run --rm test       # 后端（SQLite 内存库）
cd frontend; npm ci; npm test; npm run build; cd ..   # 前端：单测 + 类型检查 + 构建
```

只改前端、想要热更新时：

```powershell
cd frontend
npm install
npm run dev          # http://localhost:5173，/api 自动代理到 localhost:8000（需要 compose 里的 api 在跑）
```

## 6. 在新电脑用 Claude Code 继续开发

```powershell
cd $HOME\rex-crm
claude
```

项目里的 `CLAUDE.md` 已写好命令和开发规范，Claude Code 会自动读取。**第一件事**建议直接对它说：

> 后端是在没有 PHP 环境的沙盒里手写的，从未运行过。请先执行 `docker compose up --build`，把所有报错修好，再跑后端测试（`docker compose --profile test run --rm test`）和前端测试，全部通过后告诉我结果。

## 7. 后端跑通之后建议做的两件事

固定 PHP 依赖版本（目前没有 `composer.lock`）：

```powershell
docker run --rm -v "${PWD}/backend:/app" -w /app composer:2 composer update --no-interaction --no-scripts --ignore-platform-reqs
git add backend/composer.lock; git commit -m "Add composer.lock"
```

部署到 GKE：按 `docs/ai-workflow.md` 末尾的"一次性 GCP 配置"操作（需要 GCP 账号，Claude 不能替你登录）。

## 已知情况（别白查）

- 已验证：前端类型检查、构建、5 个单测；`compose.yaml` 校验；K8s 和 CI 的 YAML 语法；PHP 语法。
- **未运行过**：Laravel 后端、Docker 镜像构建、K8s 部署。第一次启动出小报错属正常，把完整输出交给 Claude Code 修。
- 没有按角色细分权限，所有登录用户可看改全部数据。
- 压缩包里不含 `node_modules`、`vendor`，到新电脑由 Docker 或 `npm ci` 重新安装。
