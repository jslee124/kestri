# 备份格式、恢复校验与保留策略实现

[English](data-maintenance.md) · [文档指南](../README.zh-CN.md)

更新：2026-10-02。源码：[data.py](../../src/kestri/storage/lifecycle.py)、[workspace.py](../../src/kestri/storage/workspace.py) 与迁移 4。命令/默认保留值见[数据生命周期](../reference/data-lifecycle.zh-CN.md)，操作见[备份恢复](../how-to/backup-and-restore.zh-CN.md)。

## 操作员服务与锁

`DataService` 接收 store、workspace、`DataSettings`，没有模型服务 client。`status()` 统计 13 张备份业务表并返回 `meta.maintenance`，不展示记录正文，不含业务迁移/框架表，不测量表/文件大小或循环健康。

`exclusive()` 获取 `kestri-data` 事务 advisory lock，检查存储 owner 绑定；操作员还尝试对应 bot 租约，拒绝使用同一数据库的运行实例。尚未绑定身份时，restore 提供备份 bot ID。按 chat ID 排序锁对话行后提供事务连接。自动清理使用 `operator=False`，仍用 data/对话锁和忙状态检查。

这些锁协调同 PostgreSQL 的应用参与者，不排除无关 SQL client、另一数据库的轮询器或人工修改文件。备份使用普通事务读取，不是物理 PostgreSQL snapshot，也没有显式 repeatable-read/PITR 协议。

`disk_operation()` 将同步文件操作放入 task/thread，通过 `asyncio.shield` 等待。取消时等 worker 完成再重新抛出，避免外层租约/回滚范围退出时线程仍写文件。不能抢占取消磁盘线程或保证断电恢复。

## 私有文件 Envelope

`encoded()` 使用 UTF-8 JSON、排序 key、`ensure_ascii=False`、`default=str` 转换数据库 UUID/时间。外层准确包含 `sha256` 和 `payload`；SHA-256 覆盖规范编码后的 payload 字节。

```json
{
  "sha256": "SHA-256 of the canonical encoded payload",
  "payload": {
    "format": "kestri-data-v1",
    "kind": "backup",
    "schema": 4,
    "created_at": "2026-10-02T00:00:00+00:00",
    "tables": {"...": ["complete business rows"]},
    "evidence_text": {"run-uuid/evidence-uuid": "retained text"},
    "checkpoints": "excluded-reset-on-restore"
  }
}
```

这是结构示意，不是有效恢复 fixture。准确表为 `meta`、`conversations`、`runs`、`tasks`、`inbox`、`messages`、`outbox`、`evidence`、`usage`、`events`、`task_changes`、`memories`、`memory_changes`。列需匹配目标结构，包括 null 字段。业务 `migrations` 和全部 checkpoint 排除；凭据不作为配置导出，但私人业务内容仍存在。

`write_private()` 限制 64 MiB，请求新父目录 0700，拒绝直接父目录符号链接，独占 no-follow 打开最终文件为 0600，写入/flush/fsync，处理失败删除半成品。不会覆盖、加密、认证作者、收紧全部祖先权限，也没有原子 rename 加父目录 fsync。

`read_private()` 以 no-follow/nonblocking 打开，检查普通文件、无 group/other 权限、大小最多 64 MiB，再读最多 limit+1。验证准确外层 key、checksum、format。SHA-256 检测损坏，不能阻止可重算 checksum 的恶意修改。本地操作员路径不是模型能力，范围与只用 UUID 的研究证据不同。

## 创建备份与导出

`backup()` 持有独占操作员事务，逐表用 named cursor 流式读取，累计行数最多 50000，编码行/正文内容在最终序列化前最多 32 MiB，最终 envelope 还须满足 64 MiB。

备份要求每条 `evidence.status='retrieved'` 有可读正文，每次最多 64000 字符，截断/文件缺失导致备份失败，不生成隐含不完整附件。附件使用准确规范 run/evidence UUID key。Export 不含附件，`kind='export'`，可读记录导出不能用于恢复。

默认 `<workspace>/backups/<UUID>.json`，支持自定义操作员路径。CLI 打印返回路径。同卷文件不防磁盘丢失，自定义/外部副本另管权限与保留，没有自动异地上传或周期备份任务。

## 恢复校验阶段

`restore(path, apply=False)` 先读私有 envelope，再检查：

1. Kind 为 `backup`、schema 准确为 4、业务表集合准确、附件字典、字典行列表、总行数上限。
2. 含 `chat_id` 的行都匹配配置 owner；恰好一个 identity 行包含该 owner 和正整数 bot ID。
3. 附件 key 准确匹配 retrieved evidence；每个 key 为两个规范 UUID，正文为最多 64000 字符的字符串。
4. 独占 data/bot 锁，全部业务目标表空，workspace 除可选 `backups` 目录外为空；存在的 `public.checkpoints` 没有快照行。
5. 延迟约束，读取目标 `information_schema.columns`，要求每行列名集合完全相同。

显式 checkpoint 空检查针对 `public.checkpoints`，不是独立完整审计孤立 blob/write 表。预览检查形状/策略/列集合，不插入记录验证所有 SQL 类型、外键、约束。CLI 初始化可能已执行结构迁移或创建工作区。

## 恢复转换与应用

插入前转换导入授权与连续性：

| 表 / 条件 | 转换 |
| --- | --- |
| `conversations` | Head 清空，epoch 递增 |
| Active `memories` | `quarantined` |
| 未删除 `tasks` | `paused`、`restored=true` |
| Queued/running `runs` | `interrupted`、取消 true、`RestoreQuarantine` |
| Pending/sending `outbox` | `uncertain`、`RestoreQuarantine` |
| Reserved `usage` | `unknown`，金额保留 |
| 已不活跃/删除/结束记录 | 保持无效/结果，不重新获得权限 |

`--apply` 用 psycopg identifier-safe SQL 构造列/占位符，JSONB 值包成 `Jsonb`。可延迟循环外键允许 tasks/runs 和记忆 supersession 按导入顺序插入。设置一次性启动标记，通过 `Workspace.write()` 创建证据，按最大导入值修复 `messages.id`、`outbox.sequence`、`events.sequence` serial。图历史不恢复。

数据库导入与证据创建在受控操作内执行，但磁盘/数据库没有统一原子提交。可处理失败回滚数据库并尽量删除新证据/目录；取消等文件 worker 后再回滚清理。突然进程/断电可能留孤立文件；保留来源，检查后用新目标重试。没有保证崩溃安全的可续跑恢复 journal。

恢复 bot 首次启动丢弃陈旧 pending 更新并发送恢复通知。导入事实需重新明确保存，约定需明确 resume，避免旧备份权限暗中覆盖后续撤销。见[执行/投递](execution-and-delivery.zh-CN.md)。

## 清理选择与数据库阶段

`cleanup(apply=False, before=None, erase=False, operator=True, now=None)` 按配置计算归档/证据/事件截止。`before` 只覆盖归档截止；默认 delete-history 将归档截止设为当前 UTC，证据/log 仍遵循自己的策略，或随关联 run 内容过期。拒绝无时区归档时间。Erase 选择全部内容截止，另撤销记忆/任务。

独占事务下，任意 queued/running run 或 pending/sending outbox 都推迟整个清理，包括 erase。停止进程不删除数据库排队工作。`deferred=true` 代表没有清除内容，不能把应用停止当清理成功。预览只统计消息/run 内容/事件/retrieved 证据，不执行请求变化。

Apply 删除过期归档，清空旧 run 请求/结果并标记 history expired，清空 outbox/变更回执，清空足够旧的 inactive 记忆/deleted 任务正文，删除过期事件。非 erase 时 active/quarantined 记忆和未删除约定继续持久保留。Erase 清空全部记忆并 forgotten，清空/删除任务、递增版本，随后删管理备份。最小运行标识/费用保留。

消息、run 内容、证据或 erase 需要失效时，清空全部对话头、递增 epoch，在空闲时删除全部 checkpoint snapshot/blob/write，范围有意比单个历史 thread 广。Saver 迁移记录保留。证据在物理删除前标 expired、`cleanup_pending`；旧历史 URL/title 也清空。

## 文件阶段、备份修剪与周期维护

数据库提交后清理 pending evidence，删除 UUID 限定文件，成功后清除 pending metadata。失败删除使证据过期不可用，等待后续成功清理重试；空 run 目录可能保留。数据库/文件分阶段，元数据可以先撤销使用，字节随后才删除。

`prune_backups()` 只考虑 workspace `backups` 直属、UUID stem、非 symlink 普通 `.json` 文件，拒绝 symlink 备份目录，按文件修改时间判断，读私有 envelope，只有 `kind='backup'` 且到期或 erase 才删除。Export/自定义名称/路径/外部副本不清理；无效候选可能导致维护失败，不盲删。

`maintaining()` 立即清理，再按配置间隔等待。最近数量/时间或安全异常类型写 `meta.maintenance`，后续尝试可重试 pending 清理。一直忙可无限推迟。没有完整历史维护日志或自动磁盘配额；不会清 `/usage`/费用记录以重置额度。

## 验证与操作边界

[数据生命周期集成测试](../../tests/storage/test_data_lifecycle_integration.py)覆盖空目标、损坏/权限/主人拒绝、隔离、事务/文件失败、序列、忙时推迟、清除/保留、no-follow 清理、取消/租约。它们证明受控边界，不证明全部突然崩溃点或外部副本删除。备份 schema 修改需明确兼容性决策，旧格式不会由无版本差异 importer 自动升级。

[当前对话式记忆增量](../reference/memory-assistant.zh-CN.md)：迁移 10、逻辑备份 schema 8、自然语言设置、短期目标选择与回答诊断。旧版本章节保留原有范围。
