# ADR-0001：使用 Python、LangChain Agent 与 DeepSeek 官方 API

[English](0001-agent-stack.md) · [文档](../README.zh-CN.md)

- 状态：已接受
- 决策日期：2026-09-30
- 更新日期：2026-10-01
- 实现：M0 模型和工具接入已验证；见[证据](../development/m0-validation.zh-CN.md)

## 背景

作者此前开发过 [Forge](https://github.com/jslee124/forge)，这是一个独立的 TypeScript coding agent 项目，用于学习 agent runtime 和 harness 的内部机制。这段经验促成了 Kestri 的方向：使用成熟框架构建可用的个人 agent 应用。

Kestri 需要成熟 agent 框架来构建可用的本地个人助理。作者也希望学习 Python，并让日常模型费用可负担。

## 决策

使用 Python 3.14 与 LangChain Agent，利用底层 LangGraph 持久化和执行控制。DeepSeek 官方 API 是首个模型服务。Kestri 是独立项目，不依赖 Forge 的代码或 runtime。

Python 3.14 是实现基线，于 2026-10-01 选定；新项目没有兼容旧解释器的需求。按当日核对的 [Python 版本状态](https://devguide.python.org/versions/)，Python 3.12 仍受安全维护，3.14 处于 bugfix 维护。实际依赖安装和检查已在 3.14.7 上通过。

初期使用一个配置好的模型，包括普通聊天、信息处理和上下文摘要。保留服务与模型配置替换能力，第一版不引入自动模型路由或第二套核心 agent 循环。

LangChain 的 agent harness 基于 LangGraph，[官方概览](https://docs.langchain.com/oss/python/langchain/overview)说明了这个关系。框架基础能力不替代 Kestri 的授权、任务管理或消息发送逻辑。

建议的初始模型 ID 与其他可调值统一维护在[架构](../design/architecture.zh-CN.md)中。DeepSeek 当前文档支持工具调用和 1M 上下文。技术能力核对于 2026-09-30；具体模型和接入行为须在实现时验证。见 [DeepSeek 官方文档](https://api-docs.deepseek.com/quick_start/pricing/)。

## 考虑过的备选方案

| 备选方案 | 初期未选择的原因 |
| --- | --- |
| TypeScript 与相同框架 | 可行，但 Python 更符合当前学习目标 |
| 自定义 runtime 或集成 Forge | 重复 runtime 工作，并将独立个人 agent 项目耦合到 Forge |
| Pi SDK 作为核心 harness | 属于另一种核心 runtime 选择；混合循环会增加状态和控制边界，目前没有需求 |
| 立即使用 Deep Agents | 首批受控工具流程不需要更完整的 harness；实际能力需求出现后再评估 |
| Claude 或 GPT 作为主服务 | 用户倾向中国模型服务与较低的日常费用 |
| 本地模型推理 | 引入硬件和模型服务工作，超出初期应用学习重点 |

## 影响

项目可以集中在工具、持久化、记忆与持续任务，同时学习 Python。费用和质量仍取决于实际工作量和服务行为；本设计没有建立模型对比测试结论。

M0 已验证 DeepSeek 工具调用与思考状态回传，并完成受控取消、限制与失败检查。小范围服务适配器弥补了锁定 SDK 的序列化行为。token 估算、摘要和产品级重试与恢复仍需验证。仅有 API 格式兼容不足以构成证据。

以后替换核心 harness 可能需要审查状态、提示词、中间件、工具权限与检查点。Deep Agents 是可选方向，不是已经保证的直接升级路径。可复用应用服务应尽量避免不必要地依赖特定 agent 循环。

本地运行并不消除外部处理：组装上下文会发给选定服务。见[安全与数据](../design/security-and-data.zh-CN.md)。

## 复审条件

实际任务质量、兼容性、费用或流程复杂度需要不同模型或 harness 时重新评估。重要技术栈变化记录替代 ADR。常规模型设置和上下文预算可以调整，无需替代本决策。
