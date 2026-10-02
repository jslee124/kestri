# 记住、纠正和忘记偏好

[English](personal-memory.md) · [文档](../README.zh-CN.md)

更新日期：2026-10-02。范围：M3，需先完成 [Telegram 配置教程](telegram-research.zh-CN.md)。

## 保存和使用偏好

向机器人发送 `/remember 我希望回答使用简短中文。`。核对回执的原文、global 范围、ID、来源和时间。保存会重置活跃前台上下文，保留原始历史。提出普通问题，模型可使用当前显式偏好。`/memory` 不调用模型即可查看有效条目。推断建议不会保存，接受建议意味着亲自发送完整 `/remember` 请求。

对于已有任务，使用 `/remember task 任务ID 这项简报最多三句话。`，只作用于该任务未来执行，不改变全局风格或任务时间。修改任务约定本身使用[任务控制](../reference/tasks.zh-CN.md)。

## 纠正和忘记

从 `/memory` 复制 ID，发送 `/correct 记忆ID 我希望回答使用详细中文。`。核对新回执和 ID：旧条目被取代，不是静默覆盖。

发送 `/forget 新记忆ID`，用 `/memory` 核对条目消失。后续问题不能通过自动历史/摘要重建重新使用旧条目。变更重置活跃对话，回复旧结果不能绕过版本边界。原始记录仍可显式查看：先 `/history`，再 `/history 记录ID`，需要时使用显示的继续指令。查看历史不会使它成为有效记忆。

通过 `docker compose restart app` 重启，再查看 `/memory`。有效条目和删除标记保存在数据库卷，不用 `down -v` 作普通重启。

## 继续长对话

继续普通对话。在约 70% 的配置输入准入预算处，Kestri 总结旧历史并保留近期完整工具交互。原始消息留在归档。`/runs` 和 `/usage` 保留执行结果和摘要费用。摘要失败/超限时安全停止，`/new` 新建上下文，不忘记个人记忆。

可选到期设置见[记忆/上下文参考](../reference/memory-and-context.zh-CN.md)。不要保存 API key 或密码。忘记表示移出活跃检索，不表示删除 Telegram 消息、历史副本或备份。M4 提供独立的[数据生命周期控制](../reference/data-lifecycle.zh-CN.md)。

## 从普通聊天学习

部署本功能分支后，发送 `/memory auto on`，再像平常一样陈述直接偏好/目标。等待前台工作完成，通过 `/memory`、`/memory pending`、`/memory changes` 检查。用 `/correct ID 完整内容` 确认需要的候选，或 `/forget ID` 丢弃。`/memory auto off` 阻止新提取，已有事实仍可使用。不回填旧聊天。提取使用 DeepSeek；DashScope embedding 语义召回尚待实现。见[运行进度](../development/memory-v2-progress.zh-CN.md)。
