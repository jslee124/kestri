# Kestri

[English](README.md)

Kestri 是一个在本地运行、通过 Telegram 机器人交互的个人 AI agent，旨在帮助用户处理日常问题、信息研究、个人偏好，以及明确委托的持续任务。

工作名来自 **kestrel（红隼）**，未来可以发展为角色或吉祥物。

## 项目状态

**第一版（M0–M4）已实现。** 公开研究与追问、每日/每周简报、显式个人记忆、自动上下文压缩，以及本地保留期清理、导出、备份和保守恢复均已提供。模型工具限制、取消、持久恢复和费用估算贯穿这些流程。

从 [Telegram 设置教程](docs/tutorials/telegram-research.zh-CN.md)开始，再阅读[持续简报](docs/tutorials/recurring-briefing.zh-CN.md)和[个人记忆](docs/tutorials/personal-memory.zh-CN.md)。日常维护见[运行指南](docs/how-to/operate-local-agent.zh-CN.md)和[备份恢复](docs/how-to/backup-and-restore.zh-CN.md)。[第一版验收记录](docs/development/first-version-acceptance.zh-CN.md)区分受控测试、真实 API/Telegram、实际部署和本次流程试用；长期日常使用另行记录。[里程碑](docs/development/milestones.zh-CN.md)保留交付依据。

## 目标

- 通过一个可用的产品学习 agent 应用开发和工程实践。
- 做出项目作者愿意持续使用的个人助理。
- 成为求职和技术面试中可以演示、深入讨论的工程项目。

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

从[文档指南](docs/README.zh-CN.md)开始。先看[实现阅读地图](docs/development/implementation-guide.zh-CN.md)，查找各模块/方法及其详细设计。学习实现时，建议依次阅读[软件架构](docs/design/architecture.zh-CN.md)、[数据库结构](docs/reference/database.zh-CN.md)、[上下文管理](docs/design/context-management.zh-CN.md)和[工具设计](docs/design/tools.zh-CN.md)。各文档说明已实现行为，并链接到负责的源码和测试。产品、需求、安全/数据策略和架构决策提供相关背景。

英语是主要文档语言。每份英语文档都有对应的简体中文翻译，范围、状态和标识符保持一致。
