# M1 Telegram 研究参考

[English](telegram.md) · [文档](../README.zh-CN.md)

更新日期：2026-10-01。范围：已实现的 `kestri telegram` 与 `kestri telegram-id`。完整真实验收状态见 [M1 记录](../development/m1-validation.zh-CN.md)。

## 配置

进程环境覆盖当前工作目录 `.env`，名称不区分大小写，未知键忽略，无效值阻止启动。凭据属于应用配置，不进入模型提示词。`kestri telegram-id` 仅需 `TELEGRAM_BOT_TOKEN`。

| 变量 | M1 默认值 | 含义 / 允许范围 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 必填 | 非空的官方 API 凭据 |
| `TELEGRAM_BOT_TOKEN` | 必填 | BotFather token，数字前缀与合法后缀 |
| `TAVILY_API_KEY` | 必填 | 非空 API 凭据 |
| `DATABASE_URL` | 必填 | PostgreSQL DSN，需允许创建 schema 和表 |
| `POSTGRES_PASSWORD` | Compose 必填 | 高强度、URL 安全密码，本地 DSN 使用同一密码 |
| `KESTRI_TELEGRAM_OWNER_ID` | 必填 | 正整数用户 ID，私聊 ID 必须匹配 |
| `KESTRI_MODEL` | `deepseek-flash` | 模型名称，1–100 字符 |
| `KESTRI_THINKING_MODE` | `disabled` | `disabled` 或 `enabled` |
| `KESTRI_MAX_MODEL_CALLS` | `8` | 每次执行 1–20 次调用尝试 |
| `KESTRI_MAX_TOOL_CALLS` | `8` | 每次执行 1–20 次调用尝试 |
| `KESTRI_RUN_TIMEOUT_SECONDS` | `120` | 大于 0、不超过 300，研究截止时间 |
| `KESTRI_REQUEST_TIMEOUT_SECONDS` | `30` | 大于 0、不超过 120，DeepSeek/Tavily 超时 |
| `KESTRI_MAX_OUTPUT_TOKENS` | `4096` | 每次模型响应 64–8192 |
| `KESTRI_INPUT_TOKEN_BUDGET` | `128000` | 4096–256000，保守请求准入估算 |
| `KESTRI_TOOL_OUTPUT_CHARS` | `12000` | 2000–32000，模型可见工具 JSON 上限 |
| `KESTRI_MAX_REPLY_CHARS` | `12000` | 1000–16000，截断提示和分块前的显示目标 |
| `KESTRI_WORKSPACE_DIR` | `.kestri/workspace` | 操作者配置的证据根目录，Compose 使用 `/workspace` |
| `KESTRI_URL_DNS_MODE` | `system` | `system` 或 `cloudflare`，公开 URL 的 DNS 核验方式 |
| `KESTRI_QUEUE_LIMIT` | `8` | 排队加进行中研究请求 1–32 |
| `KESTRI_MONTHLY_BUDGET_USD` | `20` | 大于 0、不超过 1000，UTC 月本地预算 |
| `KESTRI_RUN_BUDGET_USD` | `0.50` | 大于 0、不超过 20，单次本地预算 |
| `KESTRI_INPUT_USD_PER_MILLION` | `0.30` | 大于 0、不超过 100，输入估算费率 |
| `KESTRI_OUTPUT_USD_PER_MILLION` | `1.20` | 大于 0、不超过 100，输出估算费率 |
| `KESTRI_SEARCH_CREDIT_USD` | `0.008` | 大于 0、不超过 1，Tavily credit 估算费率 |

共有变量同时覆盖 M0 与 M1。M0 较小的默认值仍见其[参考](configuration.zh-CN.md)；当前 `.env.example` 显式选择 M1 限制。HTTP 客户端支持标准 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`NO_PROXY`。宿主机回环代理在容器中不是同一地址；在支持的环境使用可达地址，例如 `host.docker.internal`。诊断输出不得暴露代理凭据。

## 命令与关联

每次机器人回复都附带紧凑、持续可用的聊天键盘，包含 `/status`、`/runs`、`/usage`、`/stop`、`/new` 和 `/help`。点击会把对应指令作为普通消息发送，与手动输入共用主人鉴权、归档和命令处理流程。命令不调用模型。键盘显示由 Telegram 客户端控制，隐藏时可通过键盘图标打开。`/new` 保留历史，存在排队或运行工作时拒绝切换。

| 接口 | 行为 |
| --- | --- |
| 普通文本 | 归档、排队、回执、执行，延续最近完成的上下文 |
| 回复并发送文本 | 包含已知完成结果及证据引用；未知或未完成结果明确失败 |
| `/start`、`/help` | 说明能力、控制和外部服务，不调用模型 |
| `/stop`、完整的 `stop` / `停止` / `停止当前执行` / `停止当前任务` / `停下` | 停止前台执行，回复则选择相应已知的排队或运行执行 |
| `/status`、`/runs` | 最近五次执行、状态、证据/用量数量、发送问题与安全错误类型 |
| `/usage` | UTC 月已记录估算及未完成/未知预留，不是服务商账单 |
| `/new` | 无排队或运行工作时清空提交上下文，保留记录 |
| 其他斜杠命令 | 不支持提示，不调用模型 |

单个研究 worker 运行时，轮询仍继续。个人持久化或模型工作前，必须匹配已配置的主人、对应私聊及非机器人发送者。未授权消息被忽略；服务游标可越过它们，不归档其内容。一个数据库绑定一对机器人和主人，修改这对身份会被拒绝；M1 没有身份迁移命令。

## 受控信息工具

`search_web(query, topic)` 接受严格的 1–500 字符查询，以及 `general` 或 `news`。使用 basic 搜索，最多五项，不请求服务商生成答案，不自动选择参数。摘要保留来源并标为不可信。

`extract_pages(urls)` 接受一至三个公开 URL，计费前全部验证，使用 basic 文本提取。缺失、失败或空页面记录为失败。成功材料每页最多保留 64,000 字符；节选有边界，并明确截断。`read_evidence(evidence_id)` 有限读取当前执行或同一聊天中已完成执行的材料。模型不能提供任意路径或覆盖、删除文件。

仅允许 HTTP(S)、标准网页端口和解析为公开地址的目标。拒绝嵌入凭据、指定敏感查询参数、localhost/私有/链路本地地址、异常格式与映射 IPv6 地址。DNS 核验不保证 Tavily 的远端 DNS 和重定向目标；提取仍有受委托服务商的信任边界。应用不在本地任意抓取网页。

默认使用系统 DNS。假 IP 代理可能使公开网站被正确拒绝。显式设置 `KESTRI_URL_DNS_MODE=cloudflare`，使用固定的 [Cloudflare DoH JSON API](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/) 核验 A/AAAA 记录（2026-10-01 核对）。这会向 Cloudflare 发送候选网页域名，使用不带服务凭据的独立客户端。字面 IP 仍直接验证，解析出的私有地址仍拒绝；解析失败时不退回较弱模式。这仅适用于受委托的远端提取；未来本地抓取必须核验实际连接和每次重定向。

服务响应最多 2 MB。过大的工具序列化会安全失败，不提供无效 JSON。服务端点固定，模型工具不能修改服务地址。证据和回答脱敏已配置凭据值。研究关闭 LangSmith tracing；checkpoint 仍可包含内部模型推理，应按私有数据保护。

## 持久执行与发送

执行从 `queued` 到 `running`，再到 `completed`、`failed`、`cancelled` 或 `interrupted`。只有完成执行推进提交对话指针。每次执行使用新 graph thread，由上次提交的 checkpoint 初始化；原始入站、出站消息独立归档。尚未实现自动裁剪或压缩。

接受消息与更新去重在事务中完成，持久处理后推进游标。结果和出站分块先保存后发送。重启保留排队请求和结果，将未完成执行标为中断，将发送中的消息改为 `uncertain`。中断研究不自动重跑。

消息为纯文本，关闭链接预览，按 3500 字符分块，保留排队顺序和回复关联。明确未发送，例如 HTTP 429 或连接失败，可复用保存消息，最多总计三次尝试、有限延迟。超时或成功响应格式异常造成的不确定发送标为 `uncertain`，不自动重发。`/runs` 显示失败和不确定性；M1 没有手动重发或核对命令。数据库不能保证 Telegram 恰好发送一次。

## 预算与上下文计量

模型请求前，序列化消息和工具的 UTF-8 字节加固定开销提供刻意保守的输入估算，包含 system、工具和推理材料。这是准入启发式，不是 DeepSeek 的准确 tokenizer，也不会用满其宣称的上下文容量。上下文超限会停止并提示，可用 `/new` 开始新上下文。

计费工作前，用数据库串行化预留检查月预算和单次预算。模型预留按估算输入和最大输出、配置费率计算；响应提供 token 用量时替换估算。搜索预留一个 Tavily credit；最多三页的 basic 提取批次预留一个 credit。即使服务商报告更低用量，搜索和提取仍保留此保守金额。未完成或未知请求保留预留金额。

默认模型费率是 2026-10-01 对照 [DeepSeek 定价](https://api-docs.deepseek.com/quick_start/pricing/) 核对的保守高峰、无缓存估算。搜索 credit 费率可配置，不宣称是特定套餐账单价。按账户和服务更新费率。折扣、缓存、未知外部完成和估算误差意味着本地预算不是服务商账单硬保证。SDK 模型自动重试关闭。

## 部署与数据生命周期

基础 Compose 以非 root 运行应用，根文件系统只读、命名工作区卷可写，`/tmp` 有界、移除 capabilities、禁止新增权限，限制 CPU/内存/PID，不挂载 Docker socket 或宿主机 home。PostgreSQL 使用独立命名卷与内部网络，不发布端口。`compose.dev.yaml` 特意发布回环端口用于本地开发。容器不单独隔离受控工具与应用权限。

原始记录位于 `kestri` schema，LangGraph 管理独立 checkpoint 表。工作区文本按生成的执行/证据 UUID 组织，使用不跟随链接的相对文件操作。清理、保留期执行、导出、备份、恢复、记忆和调度后续实现。设计保留值是提案，不会自动删除。`docker compose stop` 保留卷；`down -v` 删除持久数据，不作为日常停止命令。
