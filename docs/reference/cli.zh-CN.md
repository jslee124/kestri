# CLI 与完整配置

[English](cli.md) · [文档指南](../README.zh-CN.md)

更新：2026-10-02。范围：[cli.py](../../src/kestri/cli.py)、[settings.py](../../src/kestri/settings.py) 全部字段及应用固定限制。数值描述当前源码，不是当前服务商报价。

## 入口与命令

安装入口为 `kestri = kestri.cli:main`。`uv run kestri ...` 使用项目环境；容器 entrypoint 已包含 `kestri`，Compose 参数从 `telegram` 或 `data` 开始。没有子命令时 argparse 打印 usage 并退出 2。`--help` 退出 0，不构造配置或访问服务。

| 命令 | 配置类 | 行为 / 参数 |
| --- | --- | --- |
| `smoke` | `Settings` | 两轮有界真实模型/工具调用，写证据；没有任意 prompt 参数 |
| `telegram` | `ResearchSettings` | 长期运行的主人 bot；模型、搜索、数据库、调度与保留策略 |
| `telegram-id` | `TelegramCredentials` | 查看 bot 身份和待处理私聊 sender ID；不登记主人、不调用模型 |
| `data status` | `DataSettings` | 只开连接池，不执行迁移；报告表数量和维护元数据 |
| `data backup [path]` | `DataSettings` | 私有逻辑备份；路径可选 |
| `data export path` | `DataSettings` | 无证据正文的业务 JSON；路径必填，不可恢复 |
| `data restore path [--apply]` | `DataSettings` | 默认校验空目标恢复，显式 apply 导入 |
| `data cleanup [--apply]` | `DataSettings` | 预览或应用保留策略 |
| `data delete-history [--before ISO] [--apply]` | `DataSettings` | 默认截止当前 UTC 时间；可选 ISO 必须带时区 |
| `data erase [--apply]` | `DataSettings` | 预览/应用内容清除；不是清空数据库 |

除 `status` 外，所有 `data` 命令都先调用 `Store.open()`，因此预览也可能执行迁移。CLI 初始化还构造 `Workspace`，可能创建配置根目录。“Dry run” 指不执行请求的导入/内容删除，不代表没有初始化副作用。`status` 需要已初始化结构，不是 bootstrap 命令。

## 配置加载与校验

构造配置时依次读取进程环境、当前工作目录 `.env`、默认值。变量名不区分大小写，忽略未知 `.env` key。配置类不是严格工具 schema：Pydantic 将环境中的数字字符串解析为声明类型。相对路径基于进程工作目录。没有全局配置搜索、动态重载或远端配置服务。

多数变量使用 `KESTRI_`，凭据/DSN 使用下方明确 alias。`TelegramCredentials` 只读取 bot token；`DataSettings` 不需要模型服务 key。`ResearchSettings` 继承运行与数据字段，并覆盖产品执行限制。[.env.example](../../.env.example) 显式设置产品级限制，复制后也会影响 smoke。缺失表示未提供；空数字/时区值不等于省略变量。

### 凭据与存储

| 变量 | 默认值 / 校验 | 使用位置 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 必填非空白 `SecretStr`；运行校验检查 stripped 内容但返回原值 | Smoke、bot |
| `TELEGRAM_BOT_TOKEN` | 必填；完整匹配 `[0-9]+:[A-Za-z0-9_-]{20,}` | ID 查询、bot |
| `TAVILY_API_KEY` | 必填非空白 `SecretStr` | Bot |
| `DATABASE_URL` | 必填；bot 额外检查非空白；`DataSettings` 只声明必填 `SecretStr`，没有额外非空白 validator；实际连接检查可用性 | Bot、data |
| `KESTRI_TELEGRAM_OWNER_ID` | 必填整数 >0 | Bot、data |
| `KESTRI_WORKSPACE_DIR` | `.kestri/workspace`；path，应用拒绝符号链接根目录；Compose 显式用 `/workspace` | Bot、data |
| `KESTRI_EVIDENCE_DIR` | `.kestri/evidence`；smoke JSON 路径，不是研究原文存储 | Smoke；bot 继承字段但证据不使用它 |

`POSTGRES_PASSWORD` 是 Compose 插值输入，不是 Python 配置字段。Compose 为 `postgres` 服务构造 `DATABASE_URL`；使用适合 URL 的值，或在 DSN 中正确编码。秘密从配置 repr/校验输出隐藏，但这不加密 `.env`、数据库或文件。

### 模型与执行

| 变量 | Smoke 默认 | Bot 默认 | 校验 / 含义 |
| --- | --- | --- | --- |
| `KESTRI_MODEL` | `deepseek-flash` | 相同 | 长度 1–100；其他模型行为需验证 |
| `KESTRI_THINKING_MODE` | `disabled` | 相同 | `disabled` 或 `enabled`；服务请求覆盖 |
| `KESTRI_MAX_MODEL_CALLS` | 4 | 8 | 整数 1–20；每轮/run 普通模型次数 |
| `KESTRI_MAX_TOOL_CALLS` | 4 | 8 | 整数 1–20；每轮/run 工具次数 |
| `KESTRI_RUN_TIMEOUT_SECONDS` | 60 | 120 | >0，≤300；外层执行期限 |
| `KESTRI_REQUEST_TIMEOUT_SECONDS` | 20 | 30 | >0，≤120；DeepSeek/Tavily HTTP 配置 |
| `KESTRI_MAX_OUTPUT_TOKENS` | 1024 | 4096 | 整数 64–8192；每次模型请求输出上限 |

任务提案固定最多两次模型调用。摘要使用下方单独设置。Telegram HTTP 固定超时 40 秒、长轮询等待 25 秒、DNS client 5 秒；改变模型服务超时不会改变这些值。

### 研究准入与费用

| 变量 | Bot 默认 | 校验 / 含义 |
| --- | --- | --- |
| `KESTRI_INPUT_TOKEN_BUDGET` | 128000 | 整数 4096–256000；UTF-8/封装准入估计，不是精确服务 token |
| `KESTRI_TOOL_OUTPUT_CHARS` | 12000 | 整数 2000–32000；整个序列化工具结果 |
| `KESTRI_MAX_REPLY_CHARS` | 12000 | 整数 1000–16000；正文目标，截断通知可能额外延长 |
| `KESTRI_URL_DNS_MODE` | `system` | `system` 或 `cloudflare`；失败不回退 |
| `KESTRI_QUEUE_LIMIT` | 8 | 整数 1–32；排队/运行的非后台请求，包括任务/记忆控制 |
| `KESTRI_MONTHLY_BUDGET_USD` | 20 | Decimal >0，≤1000；UTC 月本地额度 |
| `KESTRI_RUN_BUDGET_USD` | 0.50 | Decimal >0，≤20；单 run，包括后台重试 |
| `KESTRI_INPUT_USD_PER_MILLION` | 0.30 | Decimal >0，≤100；配置输入估算费率 |
| `KESTRI_OUTPUT_USD_PER_MILLION` | 1.20 | Decimal >0，≤100；配置输出估算费率 |
| `KESTRI_SEARCH_CREDIT_USD` | 0.008 | Decimal >0，≤1；每次搜索/提取 batch 的预留估算 |

费率是应用估算，没有自动价格更新、预付余额读取、服务端限额或未知请求退款。HTTPX 继承标准 HTTP proxy 环境；主机与容器的可达地址不同。这些是传输环境，不是配置字段。`DEEPSEEK_API_BASE` 不能替换固定模型端点。

### 记忆与压缩

| 变量 | Bot 默认 | 校验 / 含义 |
| --- | --- | --- |
| `KESTRI_MEMORY_LIMIT` | 64 | 整数 1–64 条有效记录 |
| `KESTRI_MEMORY_CONTEXT_LIMIT` | 8 | 整数 1–16 条每次请求选中记录 |
| `KESTRI_CONTEXT_TRIGGER_RATIO` | 0.70 | 本地输入阈值的 0.1–0.9 |
| `KESTRI_CONTEXT_KEEP_MESSAGES` | 12 | 整数 4–40；工具边界可能改变实际保留数量 |
| `KESTRI_MAX_SUMMARY_CALLS` | 2 | 整数 1–4 次每 run |
| `KESTRI_SUMMARY_MAX_CHARS` | 4000 | 整数 500–8000；摘要输出校验 |

### 持续任务

| 变量 | Bot 默认 | 校验 / 含义 |
| --- | --- | --- |
| `KESTRI_OWNER_TIMEZONE` | 未设置（`None`） | 若设置必须由 `ZoneInfo` 识别；无隐含时区 |
| `KESTRI_TASK_LIMIT` | 16 | 整数 1–64 条未删除任务 |
| `KESTRI_BACKGROUND_QUEUE_LIMIT` | 8 | 整数 1–32 条排队/运行后台执行 |
| `KESTRI_SCHEDULER_INTERVAL_SECONDS` | 5 | 到期检查间隔 1–60 秒 |

### 数据维护

| 变量 | Bot/data 默认 | 校验 / 含义 |
| --- | --- | --- |
| `KESTRI_ARCHIVE_RETENTION_DAYS` | 90 | 整数 1–3650 |
| `KESTRI_EVIDENCE_RETENTION_DAYS` | 30 | 整数 1–3650 |
| `KESTRI_LOG_RETENTION_DAYS` | 30 | 整数 1–3650；指事件，不是文件 logger |
| `KESTRI_BACKUP_RETENTION_DAYS` | 30 | 整数 1–3650；识别出的管理备份文件 |
| `KESTRI_MAINTENANCE_INTERVAL_SECONDS` | 3600 | 整数 60–86400；忙时延后清理 |

## 固定应用限制

以下常量不是额外支持的环境变量：Telegram 每批 20 条；结果分块 3500 字符；发送最多 3 次；发送延迟限定 1–120 秒；指定后台重试一次、间隔 30 秒；补跑 21600 秒；URL 2048 字符；原文保留 64000 字符；HTTP JSON 2000000 字节；DNS JSON 65536 字节；备份 64 MiB/50000 行；创建内容额度 32 MiB；最近执行 5 条；归档列表 10 条、每项预览 500 字符、明确分页 3000 字符；回复证据引用 20 条。配置化前需审查负责实现。

`KESTRI_TEST_DATABASE_URL` 是测试框架配置，不是应用设置。测试在环境隔离前捕获它，要求 loopback 与数据库名 `kestri_test`，会删除业务 schema。见[运行检查](../how-to/run-checks.zh-CN.md)。

## 输出与退出码

| 退出码 | 含义 |
| --- | --- |
| 0 | 命令成功完成；smoke 还要求验证通过 |
| 1 | 启动/执行/证据错误，或 smoke 验证失败 |
| 2 | 参数解析或配置校验错误 |
| 130 | CLI 处理的中断/取消 |

Data 输出 JSON：status 为 `counts` 与 `last_maintenance`；backup/export 为绝对 `path` 与 `private=true`；restore 为行/文件数和策略；cleanup 为截止时间/数量及是否 deferred。预览成功不证明 apply 的导入 SQL、外键或磁盘写入成功。Bot 长期运行，打印启动身份通知，不打印逐模型 trace。Smoke 打印证据路径和验证结果。错误报告类型/分类，隐藏原始私人异常正文。

契约背后的算法见[执行/投递](../design/execution-and-delivery.zh-CN.md)、[模型/计费](../design/model-and-accounting.zh-CN.md)、[任务调度](../design/task-scheduling.zh-CN.md)、[上下文](../design/context-management.zh-CN.md)和[数据维护](../design/data-maintenance.zh-CN.md)。
