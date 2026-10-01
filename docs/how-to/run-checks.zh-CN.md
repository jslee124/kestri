# 运行离线检查

[English](run-checks.md) · [文档](../README.zh-CN.md)

更新日期：2026-10-01。范围：已实现的 M0 开发检查。

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

这些检查不需要凭据，也不连接模型服务。runtime 测试使用 HTTP 模拟传输，同时执行真实 LangChain agent 和 DeepSeek SDK 序列化，覆盖工具结果连续性、服务思考状态回传、失败、上限、超时、取消和证据处理，不证明真实模型行为。

文档检查覆盖翻译配对、对应语言链接、本地文件链接、标题数量与工程标识符集合，不评估翻译质量、外部链接或 Markdown 锚点；这些需要另行审查。

## 检查包构建

```sh
uv build
```

这会在 `dist/` 生成源码分发包和 wheel，不会发布包，也不验证 Telegram 或部署行为。

## 单独检查真实服务

需要真实接入检查时使用[首次运行教程](../tutorials/first-agent-run.zh-CN.md)。它需要本地 API key，会消耗 API 额度。验证记录中应区分离线结果与真实调用证据。

[GitHub Checks 工作流](../../.github/workflows/checks.yml)在 Linux、Python 3.14 上执行离线命令和包构建，不接收开发者的 `.env`，不调用 DeepSeek。只有查看完成的运行后，才能声称远程 CI 成功。
