# M1 验证记录

[English](m1-validation.md) · [文档](../README.zh-CN.md)

更新日期：2026-10-01。状态：M1 已在研究范围内验证，记录本地、真实服务、容器和远程 CI 证据。本文区分实际观察证据与待完成工作。

## 版本与环境

工作分支：`codex/m1-telegram-research`，基于 `5517481`。实现版本：[`1e1e082`](https://github.com/jslee124/kestri/commit/1e1e0820f7c4f7677e9c40dad2a88526a415570b)。实现/配置 SHA-256：`08a5a37b27b349c79e551314a3b6b15499ffb132ab824664908a8d0ef374924f`。将路径、NUL、文件内容、NUL 按顺序拼接：先是 `src/kestri` 下递归排序的 Python 与 SQL 文件，然后依次为 `pyproject.toml`、`uv.lock`、`Dockerfile`、`.dockerignore`、`compose.yaml`、`compose.dev.yaml`、`.env.example`、`.github/workflows/checks.yml`。指纹不含测试和文档。本地环境：macOS、Python 3.14.7、uv 0.12.3、OrbStack Docker 的 Linux arm64 容器。锁定核心版本：LangChain 1.4.3、LangGraph 1.2.12、langchain-deepseek 1.1.1、langgraph-checkpoint-postgres 3.1.2、psycopg 3.3.6、httpx 0.28.1。

## 受控检查

使用真实、隔离的 PostgreSQL 17 数据库，65 项测试通过，无跳过。Ruff lint/format 和严格 mypy 通过。使用模拟外部 HTTP 响应执行真实 LangChain runtime 与 DeepSeek 请求序列化。

覆盖存储/模型工作前的主人及私聊拒绝、去重与游标恢复、并发费用预留、轮询仍可用时取消实际等待的模型请求、worker 后续复用、模型/工具/上下文/时间限制与服务错误、来源指令后强制发起私有 URL 请求、失败/截断提取、UUID 证据范围与符号链接/路径拒绝、新 agent checkpoint 追问、`/new` 保留归档、保存结果重试与分块顺序、发送不确定性隔离。完整任务、记忆、压缩与删除案例后续实现。

已知故障检查和新 agent checkpoint 测试提供受控恢复证据，不证明真实网络中断行为、每一条机器指令处的崩溃行为，或对所有模型级提示词注入免疫。

## 真实服务与消息

真实 DeepSeek 官方 API（`deepseek-flash`、关闭思考）与 Tavily 完成了使用 PostgreSQL 状态的研究和追问。首次系统 DNS 尝试因本机代理将公开网站解析为基准测试网段假 IP 而拒绝所有来源，保留为获取失败观察，不计为研究成功。显式 Cloudflare 解析模式在不允许私有地址的前提下核验公开记录，再次查询成功获取材料。

主人明确授权后通过 BotFather 创建新的 Telegram 机器人，token 仅保存在被忽略的本地配置。主人身份通过已登录 Telegram 页面发送的特定测试消息核验，没有注册第一位发送者。容器收到并回答了这条私聊消息。

真实 Telegram 研究请求提取了官方 agents 和 persistence 页面，为刻意不存在的页面保留失败提取，引用成功来源，并区分摘要和推论。原始消息、执行记录、用量元数据、checkpoint 与来源正文保存在私有数据库/工作区卷。来源链接起初出现 Telegram 标点问题，最终格式将每个 URL 独立成行。

重建应用容器后，回复关联追问使用先前提交的 checkpoint 并识别失败页面。再次提取验证保存和发送结果包含三个完整 URL 独立行。运行中的研究通过 `/stop` 停止，状态为 `cancelled`，保留未知请求的预留。`/status`、`/usage`、`/help` 实际送达控制回执。[脱敏真实元数据](evidence/m1-live.json)记录四次研究执行，不包含主人/聊天 ID、凭据、原始推理或来源全文。本地部署观察到 18 次操作共 $0.1162 的估算，包含另一次入门测试；不是服务商账单。该实现版本的远程 push CI 已通过：[运行 36847566505](https://github.com/jslee124/kestri/actions/runs/36847566505)；PR CI 也已通过：[运行 36847671866](https://github.com/jslee124/kestri/actions/runs/36847671866)。两者使用 Linux/Python 3.14 和真实 PostgreSQL，不使用真实服务凭据。

## 容器检查

Compose 镜像在 Linux arm64、Python 3.14.7 上构建成功。实际执行验证 UID 10001、工作区读写、PostgreSQL checkpoint 初始化，以及禁止写入 `/app`。最终测试镜像为 `sha256:7c12801e8984509528e7775ab48c7e57798117c97734bf5d617f2d26dca91dbb`。部署应用正在轮询机器人，数据库健康、无宿主机发布端口。默认挂载为命名卷，没有 home 目录或 Docker socket。配置设置根文件系统只读、移除 capabilities、禁止新增权限、有界 tmpfs 及 CPU/内存/PID 资源。

这些观察仅覆盖所测试容器平台，不证明 Windows/Linux 宿主兼容性、每个工具独立沙箱或任意代码执行安全；未暴露此类执行能力。

## 需求与案例覆盖

M1 重点为 AUTH-001、CHAT-001、CHAT-002、WEB-001、WEB-002、SEC-001、SEC-002、DATA-001、OPS-001 和 OPS-002。AC-01、AC-02 已结合受控拒绝/边界检查，以及上方真实主人研究、失败来源、追问和消息观察完成验证。受控证据覆盖 AC-05 的前台部分，AC-07 的入站、上下文、结果、重试与不确定性部分，AC-09 的回复/checkpoint 部分，AC-10 的研究工具边界，以及 AC-12 的当前限制和预留。后续里程碑能力尚无实现，因此这些完整案例仍未验证。

## 限制与剩余验收

M1 没有持续任务、个人记忆、压缩、保留期执行、备份恢复、导出或重发核对。`/new` 清空活跃上下文，不删除保留数据。预算按配置估算和预留，不是服务商账单硬上限。取消不能撤销已经提交的外部工作。URL 检查控制传给 Tavily 的准入，不控制其远端重定向和网络行为。

公开证据不得包含 API key、bot token、主人/聊天 ID、数据库密码、原始推理或无必要的私有内容。测试来源材料留在本地。后续里程碑验收保持明确待完成。代码已发布到 [draft PR 1](https://github.com/jslee124/kestri/pull/1)，本记录不宣称合并或发布版本。最初的综合研究运行早于最终格式和关闭修复；追问和再次提取观察了格式更新。最终受控测试覆盖关闭取消的传播。
