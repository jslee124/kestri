# ADR-0004：本地持续任务执行

[English](0004-recurring-task-execution.md) · [文档](../README.zh-CN.md)

日期：2026-10-01。状态：M2 已接受。

## 背景

M2 加入主人委托的持续简报，要求修改、停机恢复、独立上下文和费用边界。Kestri 已采用 PostgreSQL、本地异步进程和持久 outbox，目前不需要任意 cron 或分布式 worker 集群。

## 决策

使用 PostgreSQL 约定和执行记录作为唯一持久调度事实来源。本地异步循环检查每日/每周墙上时钟规则及显式 IANA 时区。事务锁与执行唯一标识串行化任务变更和启动，按保存的补跑政策合并错过执行。

运行一个前台 worker 与一个独立后台 worker。快照任务指令和版本，不延续或推进主聊天 graph 上下文。复用受限研究工具、费用账本和 outbox。指定暂时性后台错误最多尝试两次，每次上下文独立。

用独立 LangChain 结构化输出 agent，通过 `ToolStrategy(TaskPlan)` 理解主人的直接任务请求，不提供网页或宿主机工具。应用代码校验提案，保存按 run 标识的变更账本；来源文本和后台研究不能获得任务写入能力。保守路由与显式时间/星期核验优先保证授权可解释，不接受所有表达。澄清要求重新提供完整请求。

## 替代方案

APScheduler 可提供更广触发器，但会在约定/执行记录之外增加调度存储与同步约定。Celery 或外部工作流服务增加消息队列、进程和部署成本。任意 cron 增加时区与授权复杂度。等实际需求超过小型本地每日/每周流程再引入。

## 后果与复审

本地应用必须持续运行，休眠延迟执行。PostgreSQL 与 outbox 提供持久状态，不保证远端恰好一次投递。夏令时缺失时刻跳过，重复时刻只执行较早一次。恢复从未来计划开始。M2 支持单主人、单机器人进程，不声称多分布式调度器能力。

如果需要任意触发器、大量并行 worker、持久多步骤工作流或更广自然语言控制，再复审。替换调度器时继续分离任务授权、原始消息、研究证据和 graph 状态。

2026-10-01 核对来源：[LangChain 结构化输出](https://docs.langchain.com/oss/python/langchain/structured-output)、[Python zoneinfo](https://docs.python.org/3/library/zoneinfo.html)。它们说明构建组件；以上锁与授权决策是 Kestri 自身设计。
