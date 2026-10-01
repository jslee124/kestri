# M0 配置参考

[English](configuration.md) · [文档](../README.zh-CN.md)

更新日期：2026-10-01。范围：`kestri smoke`，实现位于 `src/kestri/settings.py` 和 `src/kestri/runtime.py`。

## 配置来源

从项目根目录运行。进程环境变量优先于当前工作目录的 `.env`，两者都未提供时采用默认值。变量名不区分大小写。未知 `.env` 键被忽略。受支持配置的无效值会在模型执行前终止 CLI。

| 变量 | 默认值 | 可接受值与含义 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 必填 | 非空 API 凭据；不进入 agent 提示词 |
| `KESTRI_MODEL` | `deepseek-flash` | 非空模型标识符，最多 100 个字符；其他型号需要单独验证 |
| `KESTRI_THINKING_MODE` | `disabled` | `disabled` 或 `enabled`；显式发送给服务 |
| `KESTRI_MAX_MODEL_CALLS` | `4` | 整数 1–20；每轮对话的模型调用尝试上限 |
| `KESTRI_MAX_TOOL_CALLS` | `4` | 整数 1–20；每轮对话的工具调用尝试上限 |
| `KESTRI_RUN_TIMEOUT_SECONDS` | `60` | 大于 0、不超过 300 的数值；一轮 agent 执行的时间限制 |
| `KESTRI_REQUEST_TIMEOUT_SECONDS` | `20` | 大于 0、不超过 120 的数值；SDK HTTP 超时设置，仍受整轮期限约束 |
| `KESTRI_MAX_OUTPUT_TOKENS` | `1024` | 整数 64–8192；每次模型请求的服务 `max_tokens` |
| `KESTRI_EVIDENCE_DIR` | `.kestri/evidence` | CLI 证据目录；相对路径从工作目录解析 |

证据目录是操作者配置，不是模型可控制的文件系统能力。如果选用其他路径，需要自行管理权限和 Git 忽略。证据写入器在 POSIX 系统上限制新建目录和文件的权限，但不会收紧已有目录的权限。

## M0 固定行为

- 官方地址：`https://api.deepseek.com/v1`。`DEEPSEEK_API_BASE` 不会覆盖应用使用的地址。
- SDK 自动重试次数为零。限制按轮计算，因此两轮 smoke 整体最多尝试两倍的单轮模型调用额度。
- LangChain 模型和工具限制中间件在新调用将超过额度时终止执行。失败或取消的会话不能继续接受下一轮。
- 此次执行禁用应用的 LangSmith 跟踪，即使父环境已启用。
- agent 状态使用进程内 LangGraph `InMemorySaver`，尚无跨进程恢复或原始消息归档。
- `checked_add` 接受两个 ±1,000,000 范围内的严格整数，拒绝未知字段，结果也必须在该范围内。工具不访问文件、网络或 shell。

服务适配器保留历史 assistant 消息中的 `reasoning_content`，并规范化空的 assistant 工具调用内容。这弥补了锁定集成版本的请求序列化行为，有请求载荷级回归测试覆盖。DeepSeek 的[思考模式指南](https://api-docs.deepseek.com/guides/thinking_mode/)规定携带工具请求的思考状态回传要求（核对于 2026-10-01）。

## 结果与证据

执行状态为 `completed`、`timeout`、`model_limit`、`tool_limit`、`provider_error` 或 `internal_error`。只有两轮都完成、包含成功的预期工具结果，并回答预期数字，smoke 才通过。agent 状态为 `completed` 仍可能未通过 smoke 验证。

CLI 退出码：检查通过为 0，检查失败或执行、证据错误为 1，配置或参数无效为 2，Ctrl+C 取消为 130。CLI 报告异常类型，不输出原始异常消息。完成前取消可能不产生证据文件。

证据 schema 版本 1 包含 UTC 时间、Python 和包版本、服务、模型、模式、配置限制，以及每轮状态、耗时、模型响应次数、工具调用和结果、可用 token 用量、是否包含思考的布尔值、回答和验证结果。不包含思考原文或认证数据。token 用量来自服务元数据，不是精确价格或账单。

## 计划中的配置

设计提出的 128,000-token 输入预算、压缩阈值、月度费用范围，以及 Telegram、Tavily、PostgreSQL 和调度参数，都不是 M0 配置。此 CLI 不执行这些控制。见[架构](../design/architecture.zh-CN.md)与[里程碑](../development/milestones.zh-CN.md)。

M1 已另行实现输入准入、费用预留、Telegram、Tavily 与 PostgreSQL，见 [M1 参考](telegram.zh-CN.md)。这些行为不适用于 `kestri smoke`。
