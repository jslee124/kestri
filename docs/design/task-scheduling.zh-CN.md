# 任务识别、约定与调度算法

[English](task-scheduling.md) · [文档指南](../README.zh-CN.md)

更新：2026-10-02。实现：[task_intent.py](../../src/kestri/tasks/intent.py)、[task_agent.py](../../src/kestri/tasks/agent.py)、[tasks.py](../../src/kestri/tasks/service.py)、[schedule.py](../../src/kestri/tasks/schedule.py)，以及 [store.py](../../src/kestri/storage/store.py) 领取/完成路径。命令/默认值见[任务参考](../reference/tasks.zh-CN.md)与 [CLI 参考](../reference/cli.zh-CN.md)。

## 确定性意图路由

`task_intent(text, task_reference=False)` 返回 `create`、`update`、`pause`、`resume`、`delete`、`list` 或 `None`；它是正则识别器，不是 LLM 分类器。先 strip 请求，识别前移除准确前缀 `/task `。单独 `/task` 返回指导。只对已授权直接输入识别；应用对转发/外部回复禁用任务意图。

识别器拒绝代码围栏、选定引号标记和解释/条件用语，包括中文解释/翻译/举例/如何/如果，以及英文 `explain`、`translate`、`example`、`how to`、`if `。创建需要重复时间用语、委托用语、允许的开头，且不能以修改/控制用语开头。控制需要允许的开头，动作匹配位于前 20 字符内，并且有明确 `/task`、回复关联或任务/简报词汇。

控制优先级是删除、暂停、恢复、修改、列表。一次请求提及多个动作时，该顺序有影响。不支持或不匹配的文本走普通研究，不创建待确认任务。澄清是结果，不是持久多轮表单；主人需要发新的完整指令。

| 示例 | 识别 / 独立校验 |
| --- | --- |
| `每天 08:00 Asia/Shanghai 给我 AI 新闻简报` | `create`；变更前仍检查提案字段 |
| `解释每天 08:00 的任务怎么运行` | 无委托；普通研究 |
| `/task 暂停任务 UUID_PREFIX` | `pause`；目标必须唯一 |
| 回复任务消息：`暂停` | 回复提供任务关联，识别 `pause` |
| 没有任务关联的 `暂停` | 无任务意图；不是全局暂停 |
| `每周给我新闻简报` | 可能识别 create，但缺少明确星期/时刻，须澄清 |

## 提案 Schema 与模型角色

`TaskAgent` 重算允许意图，只提供当前请求和配置主人时区，注册 `ToolStrategy(TaskPlan, handle_errors=False)`，没有研究工具。最多两次模型调用，经 `BoundsMiddleware` 检查费用/输入，共享 run 超时，不提供 saver、个人记忆或旧对话。

| `TaskPlan` 字段 | 约束 / 含义 |
| --- | --- |
| `action` | 一个控制动作或 `clarify`；除澄清外必须匹配允许意图 |
| `target`、`title` | 可选字符串，最多 100 字符 |
| `instructions` | 可选字符串，本次提案最多 4000 字符 |
| `local_time` | 可选 24 小时制 `HH:MM` |
| `timezone` | 可选字符串，最多 100 字符，用 `ZoneInfo` 校验 |
| `weekdays` | 可选列表，1–7 个不重复的 0–6，返回排序后值 |
| `clarification` | 可选字符串，最多 500 字符 |

拒绝额外字段。与 web 工具 schema 不同，此模型没有全局 strict 设置；应用策略独立检查结果。更新中的 null 字段保留原值。标题是显示元数据，不授权新指令或工具。

## 约定变更事务

`TaskService.apply()` 要求 `run.kind='task_control'`，重新识别意图，拒绝动作不匹配。先锁主人对话，再锁活跃 run，拒绝不活跃/取消执行；同一 run 已提交提案时直接返回 `task_changes` 结果。

创建要求 instructions、明确可解析的时间/星期，以及请求 IANA zone 或配置主人 zone。提议时区必须出现在请求中或等于配置时区。内容必须是主人原文中的准确连续子串。检查未删除任务数量，生成 UUID，缺失标题默认 `个人简报`，补跑固定 21600 秒，计算未来首次 occurrence。新任务状态 `active`、版本 1。

控制候选是主人全部未删除任务，使用行锁。目标优先按回复解析：连接对应归档消息/run，使用 `COALESCE(messages.task_id, runs.task_id)`。无回复时，明确 target 必须出现在主人文本中，匹配 UUID 前缀或准确标题。两者都没有时，只允许唯一候选。回复合并列表不能选中单个任务。

修改至少改变一个字段。新内容必须来自主人原文，以 `\n用户修订：...` 追加，不覆盖旧指令。时间/星期必须匹配确定性解析，改时区必须出现在文本中。重复修订当前没有独立的累计长度上限，后续模型输入准入仍提供边界。暂停/恢复/删除设置任务状态，不停止已运行执行。

每次成功修改/控制重新计算未来 `next_due`、递增 `revision`，用 `AgreementChanged` 取消排队 task run。明确恢复还清除 `restored`。变更将 task ID 写入控制 run，在返回前把脱敏回执写入 `task_changes`。澄清/列表/未变更也可能有回执行；存在回执代表命令结果已提交，不必然代表创建了任务。

`TaskAgent` 另行完成 run。异常/取消与已提交变化竞态时，`Store.finish()` 读取权威回执，不会错误报告回滚。重复接收或 apply 不产生第二份约定。

## 时间解析与 Occurrence 计算

`requested_time()` 优先找数字 `H:MM`/`HH:MM`，返回补零 `HH:MM`。否则识别中文数字/`两`/`十`、`点`、可选 `半` 或分钟；下午/晚上词汇且小时小于 12 时加 12。无效小时/分钟返回 `None`。这是有界解析器，没有自由相对日期或英文散文时刻推断。

`requested_weekdays()` 优先工作日用语（周一至周五），再每日用语（七天），最后明确的中英文星期名，去重排序。只有笼统每周、没有星期名不足以建立约定。

`occurrence(day, local_time, timezone)` 用 `fold=0` 构造当地时刻，转 UTC 再转回当地。回转失败代表 DST 中不存在的时刻，返回 `None`；重复时刻只用较早 fold 一次。`next_occurrence()` 最多向前查 15 个当地日历日，要求严格晚于输入时刻；`latest_occurrence()` 最多向后查 15 天，要求不晚于 now。搜索耗尽报安全失败，不虚构时刻。

## 到期检查与队列容量

`tick(now=None)` 允许测试注入时钟；应用使用当前 UTC。在事务中锁主人对话，取消过期排队后台执行，按 `next_due` 锁到期 active 任务，统计全部排队/运行后台执行作为全局容量。

每个到期任务：

1. 找最近计划 occurrence，与持久 `next_due` 比较。
2. 计算 age，检查六小时窗口及该任务是否已有排队/运行执行。
3. 有效、空闲但无容量时，不修改 `next_due`，后续 tick 可在到期前重试判断。
4. 有效、空闲且有容量时，按已存指令、UTC occurrence、时区、task ID/版本与唯一 occurrence 建立后台 run，不产生前台接收确认。
5. 其他情况在忙时合并，或跳过过期 occurrence；将 `next_due` 推进至未来，记录 `schedule_decision`（`queued`、`coalesced_busy` 或 `skipped_expired`）。

例如应用错过三次每日执行后醒来，只在六小时内调度最近一次，不补三个任务。最近 occurrence 已过去七小时则跳过；仍有效但队列满时等待，不延长授权窗口。

## 领取、重试、暂停与重启

后台 `claim_run()` 锁对话，按 active 状态、当前 revision 和补跑期限重查排队执行，无效时以 `CatchUpExpiredOrChanged` 取消。领取捕获当前 memory epoch，不设置前台来源 thread，由一个 worker 开始执行。指令快照不会自动跟随之后约定修改。

| 修改 / 失败 | 影响 |
| --- | --- |
| 暂停/修改/删除提交 | 取消旧约定排队工作；已运行快照继续 |
| 恢复 | 只安排未来 occurrence，不重放暂停期 |
| `/stop RUN_ID` | 独立于任务生命周期，取消一个排队/运行执行 |
| 暂时性失败 | active 且版本相同时，30 秒后重试一次；领取还检查到期 |
| 预算/策略/上下文/调用次数限制 | 最终失败，不自动重试 |
| 进程中断 | 保存中断通知，不自动重放图 |
| 恢复导入约定 | 暂停并标记 restored，需明确恢复 |

准确重试允许列表为 `APIConnectionError`、`APITimeoutError`、`RateLimitError`、`InternalServerError`、`ConnectError`、`ConnectTimeout`、`PoolTimeout`。`Store.finish()` 按类名匹配，不是“重试所有 5xx 或工具失败”。重试保留 run ID 与累计费用，attempt 加至 2，使用新图 thread。结果投递另有重试规则。

## 验证与修改规则

[调度测试](../../tests/tasks/test_schedule.py)覆盖确定性时刻/DST 解析；[任务集成测试](../../tests/tasks/test_tasks_integration.py)覆盖重复变更、补跑/容量、目标解析、取消竞态、暂停恢复、版本变化和前后台独立。修改识别器/解析器需保留负面授权案例，不只新增成功例子。新调度类型要一起修改 schema、提案策略、确定性解析、occurrence 标识、恢复与双语命令文档。
