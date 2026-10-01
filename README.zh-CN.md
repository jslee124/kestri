# Kestri

[English](README.md)

Kestri 是一个在本地运行、通过 Telegram 机器人交互的个人 AI agent，旨在帮助用户处理日常问题、信息研究、个人偏好，以及明确委托的持续任务。

工作名来自 **kestrel（红隼）**，未来可以发展为角色或吉祥物。

## 项目状态

**M0 已验证。** Python 3.14 CLI 可运行有边界的两轮 LangChain agent，通过 DeepSeek 调用受控算术工具。非思考与思考模式均有真实调用证据，并有离线失败和限制检查。可以从[首次运行教程](docs/tutorials/first-agent-run.zh-CN.md)与[验证记录](docs/development/m0-validation.zh-CN.md)开始。

**M1：Telegram 研究已实现并验证。** 已提供仅限主人私聊、受控 Tavily 工具、PostgreSQL checkpoint 和归档、取消、用量预留及 Docker Compose。从 [Telegram 教程](docs/tutorials/telegram-research.zh-CN.md)、[M1 参考](docs/reference/telegram.zh-CN.md)和 [M1 证据](docs/development/m1-validation.zh-CN.md)开始。完整数据生命周期验收仍待实现。[可运行里程碑](docs/development/milestones.zh-CN.md)区分交付范围和验证证据。

**M2：持续简报已实现。** 支持自然语言每日/每周约定、查看与修改、暂停/恢复/删除、独立后台执行及停机补跑。从[持续简报教程](docs/tutorials/recurring-briefing.zh-CN.md)、[任务参考](docs/reference/tasks.zh-CN.md)和 [M2 验证记录](docs/development/m2-validation.zh-CN.md)开始。

**M3：个人记忆与上下文管理已实现并验证。** 支持显式保存/查看/纠正/忘记、范围检索、可撤销上下文、原始历史查看与预算内自动压缩。见[记忆教程](docs/tutorials/personal-memory.zh-CN.md)、[参考](docs/reference/memory-and-context.zh-CN.md)和 [M3 证据](docs/development/m3-validation.zh-CN.md)。M4 完成保留期、备份恢复及整体个人使用验收。

## 目标

- 通过一个可用的产品学习 agent 应用开发和工程实践。
- 做出项目作者愿意持续使用的个人助理。

## 第一版方向

第一版围绕三个相互关联的流程展开：

1. 使用公开网页研究问题，并继续讨论查到的内容。
2. 创建和管理持续新闻简报，在同一个 Telegram 聊天中接收结果。
3. 显式保存、查看、修改和忘记个人偏好或事实。

新闻简报是通用信息工具的第一个验收场景。Kestri 的产品定位仍然是通用个人 agent。

## 已选技术方向

| 领域 | 已选方向 |
| --- | --- |
| 应用 | Python 3.14、LangChain Agent，以及底层 LangGraph 的持久化与执行控制 |
| 模型服务 | DeepSeek 官方 API |
| 交互 | Telegram 私聊、长轮询、配置好的用户 ID 白名单 |
| 网页信息 | 通过 Kestri 自有工具封装 Tavily Search 和 Extract |
| 持久化 | 本地 PostgreSQL 与专用文件工作区 |
| 部署 | Docker Compose 运行应用与数据库 |
| 初始工具策略 | 受控工具；任意代码执行后续再加入 |

本地运行意味着应用及其持久数据在本地。模型请求、网页获取和 Telegram 消息仍使用外部服务。数据处理边界见[安全与数据设计](docs/design/security-and-data.zh-CN.md)。

## 文档

从[文档指南](docs/README.zh-CN.md)开始阅读。建议顺序为产品、需求、架构、安全与数据，然后阅读架构决策。

英语是主要文档语言。每份英语文档都有对应的简体中文翻译，范围、状态和标识符保持一致。
