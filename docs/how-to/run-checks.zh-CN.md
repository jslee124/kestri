# 运行离线检查

[English](run-checks.md) · [文档](../README.zh-CN.md)

更新日期：2026-10-02。范围：M0、M1、M2、M3 与 M4 开发检查。

## 检查一次变更

安装 [uv](https://docs.astral.sh/uv/getting-started/installation/) 后，从仓库根目录运行：

```sh
uv sync --locked
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest -q
uv run python scripts/check_docs.py
```

这些检查不需要服务凭据，不连接模型服务。runtime 测试使用 HTTP 模拟传输，同时执行真实 LangChain agent 和 DeepSeek SDK 序列化。未提供下方专用测试 DSN 时，数据库测试会跳过；有跳过的运行不代表完整 M1 验证。

文档检查覆盖翻译配对、对应语言链接、本地文件链接、标题数量与工程标识符集合，不评估翻译质量、外部链接或 Markdown 锚点；这些需另行审查。

## 包含持久化与恢复检查

使用隔离、可丢弃的 PostgreSQL 实例，绝不能用个人 Kestri 数据库：测试会在每个案例前**删除 `kestri` schema**。fixture 要求回环主机名和 `kestri_test` 数据库名，但仅名称不能保证数据可丢弃。

```sh
docker run -d --name kestri-m1-test-db \
  -e POSTGRES_PASSWORD=kestri-test-only -e POSTGRES_DB=kestri_test \
  -p 127.0.0.1:55432:5432 \
  postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24
docker exec kestri-m1-test-db pg_isready -U postgres -d kestri_test
KESTRI_TEST_DATABASE_URL=postgresql://postgres:kestri-test-only@127.0.0.1:55432/kestri_test \
  uv run pytest -q
```

等待 `pg_isready` 报告可以连接。上方测试密码不能用于部署。测试覆盖未授权更新、重复接受、并发预算预留、失败/取消/中断执行、成功 checkpoint 提交、新 agent 追问、回复控制、来源攻击、失败/截断材料、明确未发送时重试与发送不确定性恢复。不模拟真实 Telegram 中断，也不证明真实服务语义。

测试后，只移除这个可丢弃容器：

```sh
docker stop kestri-m1-test-db
docker rm kestri-m1-test-db
```

不要在此流程中移除个人 Compose 卷。

## 检查包构建

```sh
uv build
```

这会在 `dist/` 生成源码分发包和 wheel。wheel 必须包含 `kestri/sql/001_initial.sql`、`kestri/sql/002_tasks.sql`、`kestri/sql/003_memory_context.sql` 和 `kestri/sql/004_data_lifecycle.sql`。不会发布包，也不验证部署行为。

## 单独检查真实服务

最小模型和工具接入使用 [M0 教程](../tutorials/first-agent-run.zh-CN.md)，M1 使用 [Telegram 教程](../tutorials/telegram-research.zh-CN.md)。均需要本地凭据并消耗额度。在 [M1 记录](../development/m1-validation.zh-CN.md)中区分离线、真实服务和容器证据。

[GitHub Checks 工作流](../../.github/workflows/checks.yml)在 Linux、Python 3.14 与可丢弃 PostgreSQL 服务上执行这些检查与包构建，不接收开发者的 `.env`，不调用 DeepSeek、Tavily 或 Telegram。只有查看完成运行后，才能声称远程 CI 成功。
