# 运行你的第一个 Kestri agent

[English](first-agent-run.md) · [文档](../README.zh-CN.md)

更新日期：2026-10-01。范围：已实现的 M0 开发者 CLI。

你将运行一个真实 LangChain agent，观察受控工具交互，并验证使用上轮结果的追问。此练习向 DeepSeek 发送两个固定算术提示词，会消耗 API 额度。

## 准备代码目录

安装 Git 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)，然后克隆仓库：

```sh
git clone https://github.com/jslee124/kestri.git
cd kestri
uv sync --locked
```

uv 读取 `.python-version`，必要时安装 Python 3.14，创建 `.venv`，并安装锁定的依赖。Python 3.14 是项目基线；此教程不要求更改系统 Python。

## 配置模型密钥

```sh
cp .env.example .env
```

在本地打开 `.env`，将 `DEEPSEEK_API_KEY` 设置为你的 DeepSeek API key。不要把密钥放进聊天或提交。Git 已忽略 `.env`。在 macOS/Linux 上，可以用 `chmod 600 .env` 限制文件权限。

此练习保留其他默认值即可。[配置参考](../reference/configuration.zh-CN.md)解释各项的准确含义。

## 运行两轮检查

```sh
uv run kestri smoke
```

第一轮要求模型使用 `checked_add` 计算 17 加 25；第二轮要求在上一结果上加 8。成功运行会输出：

```text
Evidence: .kestri/evidence/smoke-<unique-id>.json
PASS: real tool interaction and multi-turn follow-up verified.
```

打开输出路径对应的 JSON 文件，确认工具结果为 `42` 和 `50`，每轮都通过验证，并包含模型用量元数据。每轮通常需要两个模型请求：请求工具，以及收到工具结果后回答。实际请求次数可以在配置上限内变化。

证据不包含思考原文、请求头、凭据或异常正文。默认的证据目录被 Git 忽略；在 POSIX 系统上，新建证据文件仅允许所有者读写。

## 观察能力边界

agent 只有一个有范围限制的算术工具，不能浏览网页、运行 shell 命令、读取你的文件或发送 Telegram 消息。对话检查点只存在于当前进程中；重新运行命令会创建新会话。

若要启用思考模式重复练习，在 `.env` 中设置 `KESTRI_THINKING_MODE=enabled`，再运行相同命令。Kestri 在内部保留服务要求的思考状态，但证据文件不包含其原文。每次重跑都会额外消耗 API 额度。

按 Ctrl+C 取消。配置错误退出码为 2，检查失败为 1，检查完成为 0。CLI 隐藏原始异常详情。如果失败且生成了证据文件，查看记录的状态和错误类型；重试前确认凭据和网络连接。

接下来可以[运行离线检查](../how-to/run-checks.zh-CN.md)，或阅读 [M0 验证记录](../development/m0-validation.zh-CN.md)。Telegram 研究是下一个[里程碑](../development/milestones.zh-CN.md)。
