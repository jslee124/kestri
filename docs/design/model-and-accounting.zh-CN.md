# 模型接入、计费与安全诊断

[English](model-and-accounting.md) · [文档指南](../README.zh-CN.md)

更新：2026-10-02。源码：[models.py](../../src/kestri/agent/models.py)、[runtime.py](../../src/kestri/agent/runtime.py)、[budget.py](../../src/kestri/agent/budget.py)、[research.py](../../src/kestri/agent/research.py)、[smoke.py](../../src/kestri/agent/smoke.py)、[redaction.py](../../src/kestri/redaction.py) 与 [errors.py](../../src/kestri/errors.py)。这里是已实现适配/计费规则，不宣称当前服务商容量/价格。

## 模型构造与序列化

`build_model()` 用配置模型/key、固定 `https://api.deepseek.com/v1`、配置 `max_tokens`/timeout、`max_retries=0` 和明确 `extra_body={'thinking': {'type': ...}}` 构造 `DeepSeekChatModel`。环境 SDK base URL 不选择端点；HTTP proxy 另属传输环境。

`DeepSeekChatModel._get_request_payload()` 调用锁定版本的父序列化器，把原输入转成消息，用 `strict=True` 将原消息和载荷逐项配对。每个原 `AIMessage` 的字符串 `additional_kwargs['reasoning_content']` 复制到出站 assistant 消息，`content=None` 改为 `''`。其他字段仍由父序列化器处理。没有或非字符串的 reasoning 不会虚构。

这是补偿集成出站推理重放的受保护 SDK 接口，不是另一个推理生成器或通用服务抽象。[Runtime 测试](../../tests/agent/test_runtime.py)检查两种 thinking 模式的实际序列化请求、端点、工具结果和追问。适配器和锁定依赖一起升级，不能把 import 成功当兼容证明。

## 最小会话与 Smoke 验证

`AgentSession` 构建独立图，使用 `checked_add`、模型/工具次数限制、安全工具错误、`InMemorySaver` 和一个 UUID thread。`ask()` 在关闭云 tracing 和外层 timeout 下执行，返回不可变 `TurnResult(status, answer, messages, elapsed_seconds, error_type)`，失败/取消会话不再接受下一轮。取消重新抛出；普通失败读取本地快照作为诊断证据。只有成功最终 `AIMessage` 提供 answer。

状态为 `completed`、`timeout`、`model_limit`、`tool_limit`、`provider_error`、`internal_error`，与持久产品 run 状态不同。`aclose()` 在模型支持时关闭同步/异步 root client。进程内状态不等于产品归档、费用账本、记忆或恢复机制。

`run_smoke()` 先问 17+25，再问 8+上次结果。`verify_turn()` 只看上轮后新增消息，要求 completed、有 AI 工具调用、成功工具结果等于 42 或 50，答案出现带数字边界的预期数。它不证明周围每个词都正确，也不要求答案只有该数。失败不继续第二轮，`finally` 关闭模型 client。

`turn_evidence()` 记录状态/时间/错误类型、脱敏答案、模型响应数、工具名/参数/结果、用量、推理存在布尔值，不保存推理正文。`run_smoke()` 补充 schema version 1、kind `deepseek-live-smoke`、UTC 时间、Python/依赖版本、模型/模式/限制及总结果。`save_evidence()` 独占写入 `smoke-<UUID hex>.json`，模式 0600，再对整个文档替换配置 key。新目录请求 0700，不收紧已有目录权限。与研究 `Workspace` 不同，这个操作员选路径的 writer 不是基于标识、no-follow 目录句柄的 API。

## 活跃状态与输入准入

`RunControl` 持有进程内取消事件和持久 run ID。`ensure_active()` 拒绝已触发取消、缺失/取消 run，再比较前台/后台 run 与对话 epoch。记忆/任务控制不会仅因自身变更了 epoch 而被拒绝。检查在模型/工具/计费预留前执行，适用时在业务完成再检查。

`conservative_input_size()` 用 UTF-8 序列化完整消息 `model_dump()` 与工具名/说明/JSON schema，再加 2048。存在的推理和元数据也包含。它是保守估计，不是精确 tokenization。`BoundsMiddleware` 在普通模型预留前计算包含 system message 的实际请求。摘要单独用同一工具准入；选中记忆也影响普通请求大小。见[上下文管理](context-management.zh-CN.md)。

## 费用单位与公式

`micro_usd(Decimal)` 把美元转为整数百万分之一，用 `ROUND_CEILING` 向上取整。`Budget.model_cost()` 计算：

```text
估算微美元 = ceil(
    输入单位 × 配置的每百万输入美元
    + 输出 token × 配置的每百万输出美元
)
```

按仓库费率，10,000 估算输入单位与最多 4096 输出 token 预留 `ceil(10000×0.30 + 4096×1.20) = 7916` 微美元，即 USD 0.007916。若实际元数据为 1000 输入和 100 输出，则记录 420 微美元。这是配置费率算术，不是服务账单；不计算缓存/折扣价格。

每次搜索/提取预留 `ceil(search_credit_usd × 1,000,000)`，默认 8000 微美元。受支持 basic 提取 batch 最多三个 URL。报告 credits 只写元数据，美元估算不变。

## 预留与结算事务

`Budget.reserve()` 先检查活跃状态，再把单次/月度美元上限转微美元交给 `Store.reserve()`。在 `kestri-budget` 事务 advisory lock 下，要求运行且未取消的 run，按 `created_at` 合计 UTC 月用量与 run 累计用量，检查加上新金额是否超额，插入 UUID `reserved` 行。前后台并发不能经此事务同时消费同一剩余额度。

所有账本状态都计入合计。月度归属以创建预留时间为准，不以服务结算时间为准；跨午夜/月末的操作保留原时间戳。后台重试共享 run 总额。使用模型的控制与摘要也使用账本；确定性记忆命令和证据读取没有外部预留。

| 状态 | 含义与变化 |
| --- | --- |
| `reserved` | 外部请求前准入 |
| `recorded` | 用响应 metadata 结算；已知模型用量可替换金额 |
| `unknown` | 完成/重启时还没有明确结算，保留预留金额 |

`settle()` 写脱敏元数据，可选替换金额；没有金额则维持原值。实际用量替换估计后不会重新检查配置上限。不能假定失败外部请求免费。这保护本地估算准入，不保证绝对服务端支出。没有预留退款命令或账单对账 API。

普通模型结算合计返回 AI 消息可用 usage，缺失则保留估计；摘要使用单次响应 metadata。run 完成把剩余预留标记 unknown；进程恢复也全局执行此操作。`/usage` 计 UTC 月创建的账本操作数和全部金额，不是聊天消息数、工具调用数或成功 HTTP 数。

## 错误分类与可见性

| 错误 / 分类 | 使用位置 | 可见行为 |
| --- | --- | --- |
| `PolicyDenied` | 授权、URL/路径/UUID、epoch、恢复/维护 | 安全拒绝分类；工具可返回有界失败数据，run 可能停止 |
| `BudgetExceeded` | 事务化费用估算准入 | 最终预算通知，不自动重试 |
| `ContextExceeded` | 输入或摘要边界 | 最终上下文通知，不虚构摘要 |
| `ProviderFailure` | 非法/超长服务响应、缺失答案契约 | 安全服务失败，不返回原始正文 |
| `DeliveryProblem(kind, uncertain, delay)` | Telegram 适配器 | 独立发送分类；见执行/投递 |
| Timeout/次数限制/SDK 异常 | Agent 与传输 | 按类型生成安全通知/状态，受限后台重试列表 |

研究按异常类选择通知，未知异常通用失败，模型 SDK 错误返回模型请求失败。`safe_research_tool_error()` 只把已知策略/服务/值/HTTP 错误转换成有界失败字符串；`safe_tool_error()` 只处理 smoke 的 `ValueError`。模型可在剩余额度内纠正输入，错误消息不证明成功或额外权限。

## 脱敏与可观测边界

`Redactor.text()` 将配置的每个非空秘密准确字符串替换成 `[REDACTED]`；`data()` 序列化 JSON、替换后再解析。这是准确值脱敏，不是完整分类器、加密或去掉编码/变换秘密的保证。研究启动注册模型/bot/搜索/DSN 秘密；数据命令注册 DSN。记忆插入另有保守凭据模式拒绝。

研究、任务规划、研究中的摘要和 smoke 都关闭 LangSmith tracing。业务事件有 `context_compressed`、`tool_rejected_or_failed`、`url_rejected`、`schedule_decision`，保存脱敏结构化 metadata，不是完整云 trace。维护在 `meta` 保存最近报告/错误类，CLI 隐藏原异常。`/status` 与 `data status` 是观察视图，不是主动服务健康探针。

即使 tracing 关闭，checkpoint 仍可能包含原对话、工具材料和服务推理。逻辑备份排除图表，checkpoint 本地数据在重置/保留策略前仍属私人。Smoke 证据有独立受限 schema。保持产物和证据类别分离；脱敏证据不代表全部本地状态适合公开。

## 验证与维护

[Runtime 测试](../../tests/agent/test_runtime.py)覆盖模型载荷和失败会话；[证据测试](../../tests/agent/test_evidence.py)覆盖不含推理/key 和必需工具证明；[研究集成测试](../../tests/agent/test_research_integration.py)覆盖并发预留、超额拒绝、未知用量和最终结果。这验证配置算术/控制，不验证服务账单。更换 SDK/模型时一起审查载荷、thinking mode、usage metadata、上下文估计、timeout/retry 和中间件受保护接口。
