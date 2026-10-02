# 实现阅读地图与维护契约

[English](implementation-guide.md) · [文档指南](../README.zh-CN.md)

更新：2026-10-02。范围：全部 29 个 Python 源码模块、模块/类方法入口、SQL、测试和工程配置。以当前源码为准，不宣称每个内部符号都是稳定公共 API。

## 如何阅读

先从 [CLI](../reference/cli.zh-CN.md) 确认入口/配置，再读 [架构](../design/architecture.zh-CN.md)。按问题选择 [执行/投递](../design/execution-and-delivery.zh-CN.md)、[任务调度](../design/task-scheduling.zh-CN.md)、[上下文](../design/context-management.zh-CN.md)、[工具](../design/tools.zh-CN.md)、[模型/计费](../design/model-and-accounting.zh-CN.md)、[数据维护](../design/data-maintenance.zh-CN.md) 和 [数据库](../reference/database.zh-CN.md)。下面逐符号说明职责，算法/约束只在链接文档中维护。

## __init__.py

[源码](../../src/kestri/__init__.py)

仅包说明与 `__version__ = "0.1.0"`；发行变更需与 `pyproject.toml` 的项目版本一起维护，不执行应用启动。

## application.py

[源码](../../src/kestri/application.py)

应用协调 · [详细机制](../design/execution-and-delivery.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `Application.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `Application.accept_update` | 授权/路由输入，持久接收，唤醒/取消 worker。 |
| `Application.polling` | 按持久 offset 轮询，分类等待，处理后推进。 |
| `Application.work_once` | 使到期记忆失效，领取 run，跟踪/取消 task，完成未知失败。 |
| `Application.working` | 反复执行一个 worker 路线，空闲时等待/重查。 |
| `Application.scheduling` | 检查已存约定、唤醒 worker、按配置间隔等待。 |
| `Application.deliver_once` | 领取一条已存投递，记录成功或分类失败。 |
| `Application.delivering` | 用唤醒/重查和间隔处理有序待发送内容。 |
| `Application.prepare_restore` | 处理一次性陈旧更新丢弃标记，保存恢复通知。 |
| `Application.serve` | 准备/恢复，再监督六个并发循环。 |
| `run_telegram` | 创建资源，检查 webhook/身份/租约，配置菜单，清理 client。 |
| `show_telegram_ids` | 查看待处理私聊 sender，不登记或执行模型。 |

## budget.py

[源码](../../src/kestri/budget.py)

控制与计费 · [详细机制](../design/model-and-accounting.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `micro_usd` | 将 Decimal 美元向上取整为整数微美元。 |
| `RunControl.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `RunControl.ensure_active` | 检查本地/持久取消和研究 epoch 新鲜度。 |
| `Budget.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `Budget.model_cost` | 按配置输入/输出费率计算并向上取整。 |
| `Budget.reserve` | 检查活跃状态，转换上限，申请原子账本预留。 |
| `Budget.provider_usage` | 结算服务 metadata，不改变预留金额。 |
| `conservative_input_size` | 序列化完整消息/工具 schema，计 UTF-8 字节加封装。 |

## cli.py

[源码](../../src/kestri/cli.py)

CLI 路由 · [详细机制](../reference/cli.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `run_data` | 选择操作，初始化存储/工作区，打印 JSON，关闭连接池。 |
| `main` | 构造参数树，选择配置，执行命令，分类退出/错误。 |

## context.py

[源码](../../src/kestri/context.py)

请求上下文中间件 · [详细机制](../design/context-management.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `ContextSummary.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `ContextSummary._acreate_summary` | 校验/准入/预留/调用/结算有界历史摘要。 |
| `ContextSummary._build_new_messages` | 将摘要标为不可信历史 HumanMessage。 |
| `MemoryContext.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `MemoryContext.awrap_model_call` | 检查到期/epoch，检索事实，临时覆盖 system message。 |

## data.py

[源码](../../src/kestri/data.py)

操作员数据生命周期 · [详细机制](../design/data-maintenance.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `disk_operation` | 保护文件 worker，等结束再传播取消。 |
| `encoded` | 排序 key 的 UTF-8 JSON，其他值转字符串。 |
| `write_private` | 有界独占 no-follow 私有写入，fsync，清半成品。 |
| `read_private` | 校验文件权限/类型/大小、envelope、checksum、format。 |
| `DataService.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `DataService.exclusive` | 取得 data/bot 租约，检查主人，锁对话。 |
| `DataService.status` | 统计业务记录，读最近维护 metadata。 |
| `DataService.backup` | 流式读有界业务行和可选证据，写私有 bundle。 |
| `DataService.restore` | 校验空目标，转换授权，导入/文件/序列，失败回滚。 |
| `DataService.cleanup` | 预览/推迟/撤销内容，先提交元数据再清文件。 |
| `DataService.prune_backups` | 只删除识别出的旧管理备份。 |
| `DataService.maintaining` | 周期清理，保留安全最近结果/错误。 |

## embedding.py

[源码](../../src/kestri/embedding.py) · [接口与配置](../reference/embedding.zh-CN.md)

`EmbeddingBatch` 保存校验后的不可变向量/用量；`EmbeddingClient.__init__` 捕获配置/HTTP client，`embed` 执行有界请求及校验；`cosine_similarity` 用于固定比较；`run_embedding_smoke` 只发送非个人测试文本；`save_embedding_evidence` 写脱敏 JSON。`EmbeddingSettings` 校验 key、数字维度和北京接口。自动提取已单独实现；[Memory v2](../design/memory-v2.zh-CN.md) 的向量召回仍待完成。

## errors.py

[源码](../../src/kestri/errors.py)

失败分类 · [详细机制](../design/model-and-accounting.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `PolicyDenied` | 无私人载荷的授权/策略错误分类。 |
| `BudgetExceeded` | 费用估算拒绝分类。 |
| `ContextExceeded` | 上下文/摘要准入拒绝分类。 |
| `ProviderFailure` | 服务/响应契约失败分类。 |

## http.py

[源码](../../src/kestri/http.py)

有界 HTTP · [详细机制](../design/tools.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `post_json` | 流式读有界 JSON，校验 HTTP/结构，返回字典或安全失败。 |

## memory.py

[源码](../../src/kestri/memory.py)

显式记忆服务 · [详细机制](../design/context-management.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `memory_instruction` | 识别 slash/自然语言显式记忆命令和正文。 |
| `display` | 展示范围/状态/来源/时间/到期和隔离警告。 |
| `listing` | 不调用模型，最多读 64 条有效/隔离未到期记录。 |
| `MemoryService.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `MemoryService.apply` | 校验活跃直接命令，变更准确事实/目标，提交回执/epoch。 |
| `MemoryService._insert` | 拒绝凭据模式，限制有效记录，插入来源/替代关系。 |
| `MemoryService.expire` | 使到期 active 事实无效，更新 epoch/对话头。 |
| `MemoryService.retrieve` | 筛主人/状态/到期/任务，再按关键词/范围排序并限制。 |

## memory_extractor.py

[源码](../../src/kestri/memory_extractor.py) · [实施边界](memory-v2-progress.zh-CN.md)

`MemorySource`、`ExistingMemory`、`ExtractionBatch` 定义可信输入，`ExtractionBatch.validate_batch` 检查资格/上限；`SourceReference`、`MemoryOperation`、`MemoryProposal` 定义模型 schema；`validate_proposal` 校验并返回不可变 `ValidatedExtraction`；`MemoryExtractor.__init__` 捕获模型与脱敏器，`extract` 执行有界、计费的提案生成。`Record` 是不可变、拒绝额外字段的公共基类。本模块不写数据库。

## models.py

[源码](../../src/kestri/models.py)

服务序列化适配 · [详细机制](../design/model-and-accounting.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `DeepSeekChatModel._get_request_payload` | 委托序列化，重放字符串 reasoning，规范空 assistant 内容。 |

## redaction.py

[源码](../../src/kestri/redaction.py)

配置秘密脱敏 · [详细机制](../design/model-and-accounting.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `Redactor.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `Redactor.text` | 将准确非空配置值替换为标记。 |
| `Redactor.data` | JSON 序列化、脱敏、解析结构化 metadata。 |

## research.py

[源码](../../src/kestri/research.py)

产品 agent 执行 · [详细机制](../design/architecture.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `BoundsMiddleware.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `BoundsMiddleware.awrap_model_call` | 检查活跃/完整输入，预留模型费用，结算返回用量。 |
| `BoundsMiddleware.awrap_tool_call` | 检查活跃，记录指定工具失败分类。 |
| `safe_research_tool_error` | 返回已知有界工具失败数据，不返回原异常文本。 |
| `ResearchAgent.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `ResearchAgent.run` | 路由控制或构造有界研究图，初始化上下文，生成来源页脚并完成。 |

## runtime.py

[源码](../../src/kestri/runtime.py)

最小模型集成会话 · [详细机制](../design/model-and-accounting.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `TurnResult` | 不可变状态/答案/消息/时间/错误结果，见模型/会话契约。 |
| `build_model` | 固定官方端点/模式、输出/超时、零 SDK 重试。 |
| `safe_tool_error` | 把 smoke 范围错误转换成安全失败字符串。 |
| `AgentSession.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `AgentSession.ask` | 执行内存一轮，分类结果，失败/取消后拒绝复用。 |
| `AgentSession.aclose` | 关闭受支持的同步/异步模型 HTTP client。 |

## schedule.py

[源码](../../src/kestri/schedule.py)

当地时刻算法 · [详细机制](../design/task-scheduling.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `occurrence` | 当地/UTC 回转，跳 DST 缺口，选早 fold。 |
| `next_occurrence` | 向前查 15 天，选严格未来的匹配星期。 |
| `latest_occurrence` | 向后查 15 天，选最近已到期匹配星期。 |
| `requested_time` | 解析明确数字/中文时刻，校验小时/分钟。 |
| `requested_weekdays` | 识别工作日/每日/明确星期并去重排序。 |

## settings.py

[源码](../../src/kestri/settings.py)

配置校验模型 · [详细机制](../reference/cli.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `Settings` | 最小会话配置，必填模型 key 和每轮限制。 |
| `Settings.require_nonempty_key` | 拒绝空白模型 key，不在校验输出返回它。 |
| `TelegramCredentials` | 仅引导使用的 bot-token 配置。 |
| `TelegramCredentials.validate_token` | 校验完整 Bot API token 模式。 |
| `DataSettings` | 操作员 DSN/主人/工作区/保留，不需要服务 key。 |
| `ResearchSettings` | 合并运行/数据/产品字段，完整目录见 CLI。 |
| `ResearchSettings.validate_timezone` | 用 ZoneInfo 校验可选 IANA 主人时区。 |
| `ResearchSettings.require_token` | 产品配置复用 Telegram token validator。 |
| `ResearchSettings.require_secret` | 产品启动拒绝空白搜索 key/DSN。 |

## smoke.py

[源码](../../src/kestri/smoke.py)

真实 Smoke 与证据 · [详细机制](../design/model-and-accounting.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `verify_turn` | 要求新增成功预期工具结果与 completed 数字答案。 |
| `turn_evidence` | 提取可观察工具/用量及推理存在标记。 |
| `run_smoke` | 执行 42 后 50，验证失败停止，关闭会话。 |
| `save_evidence` | 独占保存 schema 证据，key 脱敏和私有权限。 |

## store.py

[源码](../../src/kestri/store.py)

业务事务 · [详细机制](../reference/database.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `chunks` | 按 3500 字符分块，空结果补占位符。 |
| `Store.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `Store.open` | 开连接池，在事务锁下执行四份幂等业务迁移。 |
| `Store.close` | 关闭连接池。 |
| `Store.one` | 用参数 SQL 取一条字典行。 |
| `Store.all` | 用参数 SQL 取字典行列表。 |
| `Store.execute` | 使用给定参数执行独立语句。 |
| `Store.bind_identity` | 插入或校验数据库 bot/owner 绑定。 |
| `Store.offset` | 读持久下一 update ID，默认零。 |
| `Store.advance_offset` | 持久保存单调最大的下一 update ID。 |
| `Store.accept` | 原子去重、归档、排队/控制、确认输入。 |
| `Store._command_notice` | 生成确定性主人状态/历史/列表/重置/帮助。 |
| `Store.claim_run` | 使旧后台失效，领取到期路线，捕获来源/epoch。 |
| `Store.cancelled` | 缺失 run 或取消标记均视为取消。 |
| `Store.finish` | 协调控制/取消/epoch/重试，事务化终态费用/头/outbox。 |
| `Store.recover` | 完成中断执行/已提交控制，标记发送/预留不确定。 |
| `Store.reply_context` | 解析主人回复为已完成、当前 epoch、未过期研究结果。 |
| `Store.add_evidence` | 保存关联 run 的脱敏来源 metadata。 |
| `Store.event` | 保存脱敏结构化运行事件。 |
| `Store.reserve` | 串行费用准入，插入微美元预留。 |
| `Store.settle` | 记录脱敏用量，可选替换预留金额。 |
| `Store.claim_delivery` | 领取最早已到期 pending sequence，增加发送次数。 |
| `Store.delivered` | 提交成功 message ID 与输出归档。 |
| `Store.delivery_failed` | 选择重试/失败/不确定，限制下次延迟。 |

## task_agent.py

[源码](../../src/kestri/task_agent.py)

任务提案执行 · [详细机制](../design/task-scheduling.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `TaskAgent.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `TaskAgent.run` | 提取当前允许 TaskPlan，实施策略，恢复已提交回执。 |

## task_intent.py

[源码](../../src/kestri/task_intent.py)

委托识别 · [详细机制](../design/task-scheduling.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `task_intent` | 保守路由当前直接重复任务/控制用语。 |

## tasks.py

[源码](../../src/kestri/tasks.py)

约定服务 · [详细机制](../design/task-scheduling.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `TaskPlan` | 结构化提案字段/validator，不是直接授权。 |
| `TaskPlan.valid_days` | 拒绝重复/越界星期，返回排序列表。 |
| `TaskPlan.valid_zone` | 校验提案可选 IANA 时区。 |
| `agreement` | 展示已存时间/内容/生命周期和恢复警告。 |
| `list_tasks` | 不调用模型列主人未删除约定。 |
| `TaskService.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `TaskService.apply` | 重查直接意图/字段/目标，提交约定和回执。 |
| `TaskService.tick` | 锁下合并/跳过到期工作，遵守容量，保存 occurrence/决策。 |

## telegram.py

[源码](../../src/kestri/telegram.py)

Bot 传输与路由 · [详细机制](../design/execution-and-delivery.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `DeliveryProblem.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `TelegramClient.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `TelegramClient.call` | 提交有界 API 请求，分类成功/拒绝/限流。 |
| `TelegramClient.identity` | 校验 getMe 结果和整数 bot ID。 |
| `TelegramClient.configure_menu` | 注册主人范围双语命令和菜单按钮。 |
| `TelegramClient.poll` | 按 offset、服务等待、batch 上限请求消息。 |
| `TelegramClient.send` | 发送已存纯文本，区分已知/不确定结果。 |
| `authorized_message` | 检查主人、私聊、非 bot、text/message 标识。 |
| `command_for` | 识别准确 stop 与支持 slash 名称/bot 后缀。 |

## tools.py

[源码](../../src/kestri/tools.py)

Smoke 工具 · [详细机制](../design/tools.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `AddInput` | 严格有界操作数 schema，拒绝未知字段。 |
| `checked_add` | 校验有界严格操作数/总和，返回数字字符串。 |

## url_policy.py

[源码](../../src/kestri/url_policy.py)

公共目标策略 · [详细机制](../design/tools.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `resolve_host` | 限制系统 DNS 时间，返回去重地址。 |
| `CloudflareResolver.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `CloudflareResolver.__call__` | 无回退/服务凭据地取有界 A/AAAA DoH。 |
| `PublicURLPolicy.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `PublicURLPolicy.validate` | 拒绝不安全 URL/地址/秘密 query，去掉 fragment。 |

## web.py

[源码](../../src/kestri/web.py)

信息工具适配 · [详细机制](../design/tools.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `SearchInput` | 严格 query/topic schema，见工具输入表。 |
| `ExtractInput` | 严格的一至三个 URL schema。 |
| `EvidenceInput` | 严格 evidence-ID 字段，读取时实施 UUID 策略。 |
| `WebTools.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `WebTools.output` | 脱敏并限制完整 JSON 输出大小。 |
| `WebTools.evidence` | 保留有界正文，插来源 metadata，返回节选契约。 |
| `WebTools.search` | 预留搜索估算，校验候选，保存摘要。 |
| `WebTools.extract` | 校验/去重 URL、预留、准确匹配、保存失败/页面。 |
| `WebTools.read` | 校验证据 UUID/主人/epoch/状态，有界读工作区。 |
| `WebTools.tools` | 将三个 schema 工具 wrapper 绑定本次服务。 |

## workspace.py

[源码](../../src/kestri/workspace.py)

限定证据文件系统 · [详细机制](../design/tools.zh-CN.md)

| 符号 | 职责 |
| --- | --- |
| `Workspace.__init__` | 构造/捕获该组件依赖与本地状态；默认值和资源创建见负责文档。 |
| `Workspace.directory` | 打开 UUID 相对 no-follow 目录句柄，按需创建。 |
| `Workspace.write` | 独占 no-follow 创建私有证据文件。 |
| `Workspace.read` | 读 limit+1 字符，报告截断。 |
| `Workspace.remove` | 不跟随目录链接删除一份生成证据。 |

## SQL 与工程文件

四份 [SQL 迁移](../reference/database.zh-CN.md) 定义业务表、任务循环外键、记忆代次与恢复字段；saver 单独维护框架表。下列文件也是实现的一部分：

| 文件 | 契约 |
| --- | --- |
| [pyproject.toml](../../pyproject.toml) | Python >=3.14、Hatchling 包、入口、依赖范围与 Ruff/mypy/pytest 策略。 |
| [uv.lock](../../uv.lock) | 锁定解析；可复现依赖用 `uv sync --locked`。 |
| [.python-version](../../.python-version) | 开发解释器选择。 |
| [.env.example](../../.env.example) | 公开占位/示例，不是主人凭据，也不是全部支持配置。 |
| [compose.yaml](../../compose.yaml) | 应用/数据库网络、持久卷、监督、限制和健康检查。 |
| [compose.dev.yaml](../../compose.dev.yaml) | 主机开发明确暴露 loopback 数据库端口，改变基础网络暴露。 |
| [Dockerfile](../../Dockerfile) | 锁定无 dev 环境、包/源码复制、非 root 入口/工作区。 |
| [.gitignore](../../.gitignore) | 普通 Git 跟踪排除秘密/本地状态/缓存/构建产物。 |
| [.dockerignore](../../.dockerignore) | 构建上下文排除秘密/本地状态/缓存。 |
| [.github/workflows/checks.yml](../../.github/workflows/checks.yml) | Linux 离线/数据库检查及打包，不代表服务验收或发布。 |
| [scripts/check_docs.py](../../scripts/check_docs.py) | 检查配对/语言链接/本地文件/标题数量/工程 ID，不检查锚点/正文质量。 |

## 测试组织与证据

测试需要真实库代码和模拟传输，不等于真实服务证明。数据库测试主动删除 `kestri_test` 的业务 schema，只能用可丢弃实例。`conftest.py` 在环境隔离前捕获测试 DSN；autouse fixture 移除指定模型/代理/KESTRI 环境值；配置辅助函数关闭 `.env`。生命周期 suite 另外清理 checkpoint 状态并绑定测试身份。公共模拟模型、DNS、Telegram 输入和场景构建在 `helpers.py`，不在其他测试模块。

| 文件 | 验证边界 |
| --- | --- |
| [test_settings.py](../../tests/test_settings.py) | 配置 key/模式/范围校验。 |
| [test_tools.py](../../tests/test_tools.py) | 严格有界加法。 |
| [test_evidence.py](../../tests/test_evidence.py) | 可观察工具证明、key/推理排除、文件权限。 |
| [test_runtime.py](../../tests/test_runtime.py) | 实际图/SDK 载荷、追问、限制、取消。 |
| [test_boundaries.py](../../tests/test_boundaries.py) | 公共 URL/DNS、工作区、HTTP/Telegram 契约/菜单。 |
| [test_schedule.py](../../tests/test_schedule.py) | 时刻解析与 DST 重复。 |
| [test_research_integration.py](../../tests/test_research_integration.py) | 接收、持久化、预算、来源、worker、发送/恢复。 |
| [test_tasks_integration.py](../../tests/test_tasks_integration.py) | 授权、约定、合并、重试、控制。 |
| [test_memory_context_integration.py](../../tests/test_memory_context_integration.py) | 显式记忆、范围/撤销/到期、压缩。 |
| [test_data_lifecycle_integration.py](../../tests/test_data_lifecycle_integration.py) | 私有备份、隔离、保留、磁盘失败/租约。 |
| [conftest.py](../../tests/conftest.py) | 环境隔离、不收集的配置 helper、可丢弃 store fixture。 |
| [helpers.py](../../tests/helpers.py) | 共享离线传输与主人/任务/记忆场景构造。 |
| [__init__.py](../../tests/__init__.py) | 空包标记，支持相对 helper import。 |

运行命令见[开发检查](../how-to/run-checks.zh-CN.md)。历史 M0–M4 文件记录当时验收，不按旧路径重命名证据。增加用例/功能后，以新结果说明，不能把受控测试、远端 CI、真实 API、部署或长期使用合并成一个“已验证”。

## 文档覆盖与变更责任

当前覆盖是可追踪的实现说明，不是完整形式化证明或稳定 SDK 承诺。维护时新增模块/类方法要更新本地图，字段/迁移更新数据库与备份格式，路由/状态更新执行与任务指南，工具更新 schema/副作用/证据，配置更新 CLI，压缩/记忆更新上下文；双语同时修改。单个职责的数值契约优先在 reference 维护，设计文档解释算法，历史证据保持原结论范围。

## memory_repository.py

[源码](../../src/kestri/memory_repository.py)。`memory_command` 实现确定性开启/列表/候选/变更查看；`MemoryRepository.claim` 管来源顺序、前台优先、租约/run 恢复与版本捕获；`snapshot` 准入有界归档和当前记忆；`ensure_active` 校验代次/版本/epoch/租约；`publish` 复核提案并事务写事实/引用/事件/作业成功；`fail` 记录安全错误、重试时间和未知用量。见[运行进度](memory-v2-progress.zh-CN.md)。

## memory_worker.py

[源码](../../src/kestri/memory_worker.py)。`MemoryJobControl.ensure_active` 在 run 活动检查上增加作业授权；`MemoryBudget.reserve` 使用主人与独立维护预算；`MemoryWorker.work_once` 领取、提取、提交或记录有限失败/重试。`Application.memory_maintaining` 独立于前台和投递运行。[005_automatic_memory.sql](../../src/kestri/sql/005_automatic_memory.sql) 与[持久作业测试](../../tests/test_memory_jobs_integration.py)覆盖本增量。逻辑备份升为 schema 5，兼容 schema 4。
