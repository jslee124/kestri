# 文档指南

[English](README.md) · [项目首页](../README.zh-CN.md)

更新：2026-10-02。状态：M0、M1、M2、M3、M4 已完成第一版交付验收；长期使用另行记录。

## 第一版使用和维护

- [第一版验收记录](development/first-version-acceptance.zh-CN.md)：全部要求、案例和证据边界。
- [运行维护](how-to/operate-local-agent.zh-CN.md)：启动、检查、重启和清理。
- [备份恢复](how-to/backup-and-restore.zh-CN.md)：私有快照与空目标恢复。
- [数据生命周期参考](reference/data-lifecycle.zh-CN.md)：接口、保留期与隔离规则。
- [ADR-0006](decisions/0006-conservative-data-recovery.zh-CN.md)：保守恢复的取舍。

## Embedding 与下一阶段记忆

- [北京 Embedding 接入](reference/embedding.zh-CN.md)：已实现的配置、适配器和独立 smoke。
- [接入验证](development/embedding-validation.zh-CN.md)：真实服务证据与边界。
- [Memory v2 规格](design/memory-v2.zh-CN.md)：自动记忆、语义召回、历史检索及生命周期，尚未实现。
- [ADR-0007](decisions/0007-automatic-semantic-memory.zh-CN.md)：自动与语义记忆方向。

## 使用已实现的增量

- [个人记忆](tutorials/personal-memory.zh-CN.md)：保存、纠正、忘记与查看原始消息。
- [记忆与上下文参考](reference/memory-and-context.zh-CN.md)：检索、失效、压缩与限制。
- [M3 验证记录](development/m3-validation.zh-CN.md)：受控检查、真实 DeepSeek 压缩和 Telegram 重启/忘记观察。

- [持续简报](tutorials/recurring-briefing.zh-CN.md)：创建、管理和接收每日/每周简报。
- [任务参考](reference/tasks.zh-CN.md)：约定、调度、后台执行与恢复规则。
- [M2 验证记录](development/m2-validation.zh-CN.md)：受控检查与真实调度投递证据。

- [Telegram 研究](tutorials/telegram-research.zh-CN.md)：主人配置与首个产品流程。
- [M1 参考](reference/telegram.zh-CN.md)：控制、持久化、部署和边界。
- [M1 验证记录](development/m1-validation.zh-CN.md)：离线、真实服务与部署证据。
- [首次运行 agent](tutorials/first-agent-run.zh-CN.md)：有指导的真实模型和工具练习。
- [运行离线检查](how-to/run-checks.zh-CN.md)：验证开发变更。
- [M0 配置](reference/configuration.zh-CN.md)：已实现配置与结果的准确说明。
- [M0 验证记录](development/m0-validation.zh-CN.md)：证据与已知限制。

## 阅读实现细节

从[实现阅读地图](development/implementation-guide.zh-CN.md)开始：逐一说明全部 Python 模块、函数/方法入口、SQL、工程配置及测试职责，并链接到负责的详细文档。

- [CLI 与完整配置](reference/cli.zh-CN.md)：全部命令、参数、退出码、配置类与默认值。
- [执行与投递](design/execution-and-delivery.zh-CN.md)：输入授权、归档、队列、取消、恢复与 outbox 状态机。
- [任务与调度](design/task-scheduling.zh-CN.md)：意图识别、提案校验、修改事务、时区/DST、补跑与重试。
- [模型与费用账本](design/model-and-accounting.zh-CN.md)：请求适配、中间件、用量、费用预留/结算和错误分类。
- [数据维护内部实现](design/data-maintenance.zh-CN.md)：锁、快照格式、校验、恢复转换、清理和故障边界。

## 阅读设计

| 文档 | 用途 | 状态 |
| --- | --- | --- |
| [产品](design/product.zh-CN.md) | 产品定位、用户流程与第一版范围 | 产品方向已确认 |
| [需求](design/requirements.zh-CN.md) | 带标识符的需求与验收标准 | 基于已达成共识行为的已接受的第一版规格 |
| [架构](design/architecture.zh-CN.md) | 部署、模块地图、并发、完整请求链路与恢复 | 已实现的软件架构 |
| [数据库](reference/database.zh-CN.md) | 表、字段、关系、索引、事务和 checkpoint 存储 | 已实现结构参考 |
| [上下文管理](design/context-management.zh-CN.md) | 执行初始化、提示组装、记忆选择、压缩与代次撤销 | 已实现上下文设计 |
| [工具设计](design/tools.zh-CN.md) | 能力集合、schema、适配器、URL/文件边界、证据与计费 | 已实现工具设计 |
| [安全与数据](design/security-and-data.zh-CN.md) | 权限、隔离、记忆、上下文与数据生命周期 | 第一版实现的边界设计 |
| [可运行里程碑](development/milestones.zh-CN.md) | 可运行增量、退出条件、需求覆盖与证据 | M0、M1、M2、M3、M4 已验证 |
| [ADR-0001](decisions/0001-agent-stack.zh-CN.md) | Python、LangChain Agent 与 DeepSeek 官方 API | 已接受 |
| [ADR-0002](decisions/0002-local-deployment-and-tool-boundaries.zh-CN.md) | 本地部署与受控工具 | 已接受 |
| [ADR-0003](decisions/0003-persistence-and-state-separation.zh-CN.md) | PostgreSQL 与状态分类隔离 | 已接受 |
| [ADR-0004](decisions/0004-recurring-task-execution.zh-CN.md) | 持久化约定、本地调度及独立执行 | 已接受 |
| [ADR-0005](decisions/0005-explicit-memory-and-revocable-context.zh-CN.md) | 显式记忆、上下文代次失效与预算内摘要 | 已接受 |

“已接受”表示已确认的设计决策，并不证明实现有效。需求文档是验收标准的来源；[M0 证据](development/m0-validation.zh-CN.md)覆盖初始模型和工具接入；[M1 证据](development/m1-validation.zh-CN.md)单独跟踪产品流程。

## 文档组织

Kestri 使用 [Diátaxis](https://diataxis.fr/) 区分学习教程、面向任务的操作指南、事实参考与解释。产品需求、交付里程碑和 ADR 单独作为工程记录维护。目录布局属于项目约定，不是 Diátaxis 强制要求的结构。

| 类别 | 读者需求 | 当前情况 |
| --- | --- | --- |
| 教程 | 通过有指导的完整实践学习 | 已提供首次运行 agent、Telegram 研究、持续简报与个人记忆 |
| 操作指南 | 完成具体任务 | 已提供开发检查、本地维护与备份恢复 |
| 参考 | 查询准确的接口、配置与行为 | 已提供 M0 配置、M1 Telegram、M2 任务与 M3 记忆/上下文和 M4 数据参考 |
| 解释 | 理解概念、机制与取舍 | 已提供依据源码的软件架构、上下文管理与工具设计 |
| 设计 | 审查预期产品行为与系统边界 | 见上方文档 |
| 开发 | 跟踪可运行交付增量与验证进度 | 已提供里程碑、M0、M1、M2、M3、M4 证据 |
| 决策 | 理解重要选择的原因 | 见上方文档 |

不得把提案当作已实现功能的参考文档。教程与参考只描述经过验证的实现，未来能力留在设计文档中。

## 语言与维护

- 英语是主要来源。每份 `name.md` 对应同目录的 `name.zh-CN.md` 翻译；`README.md` 也遵循这个规则。
- 每对文档互相链接。中文导航链接到中文文档，英文导航链接到英文文档。
- 在同一次变更中更新两个版本。需求 ID、决策 ID、技术标识符，以及日期和状态的含义必须一致。
- 翻译出现差异时修正对应文档，不保留两种语言下的不同需求。
- 标题、范围、表格和验收案例保持对应。翻译正文，必要时保留准确的 API 标识符和路径。
- 每项规范性事实在一个指定文档中维护，其他文档链接引用。产品定义范围，需求定义验收，设计文档说明机制与默认值并标注实现状态，里程碑定义交付顺序与证据状态。
- 明确区分已确认决策、可调默认值、待决问题、已实现行为和验证证据。
- 外部技术能力引用一手来源，并记录核对日期。实现时重新核对可能变化的服务信息。

## 决策记录

ADR 使用带编号的文件名，记录状态、背景、决策、备选方案、影响与复审条件。只记录重要选择；常规调参写在设计文档中。替代 ADR 应指出它取代的决策，并更新两个语言版本。

## 验证策略

接受文档变更前，检查本地链接、英中配对、标识符一致性与格式。软件实现后，将验收标准关联到实际验证证据，区分离线检查、真实 API 行为、恢复测试与部署验收。
