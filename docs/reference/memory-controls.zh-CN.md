# 记忆纠正与变更提示

[English](memory-controls.md) · [文档](../README.zh-CN.md)

更新：2026-10-02。已实现的主人控制与持久自动提示。

## 直接自然语言控制

[意图解析](../../src/kestri/memory/intent.py)接受完整、从开头匹配的中文指令，例如 `把关于Python的记忆改成我现在使用 Rust。`、`忘记关于Python的记忆`、`更正记忆 Python 改成我现在使用 Rust。`。`/remember`、`/correct ID 完整内容`、`/forget ID` 和旧中文前缀仍可用。引用、假设、嵌入、否定以及转发/外部控制不能授权写入。

[MemoryService](../../src/kestri/memory/service.py)在主人事务内解析目标。只有明确 ID 语法（`/correct`、`/forget`、`更正记忆`、`忘记记忆`）中未引用的完整/部分 UUID 才沿用唯一 ID 校验。`关于deadbeef的记忆` 中的目标即使看起来像十六进制，仍按字面内容处理。其他目标经过 Unicode NFKC、大小写和空白规范化；至少两个字符的字面子串必须在个人/任务范围中唯一命中一条主人 active/candidate、未到期记录。排除已删除任务。快照检查配置的自动、显式和候选容量再多一条，超限则禁用自动解析。

没有目标或目标模糊时，不变更记忆/revision/epoch。最多显示五个字面或词项候选，包含 ID、范围和有界内容。词项/语义相关性不能授权修改。主人以新的 `/correct ID 完整内容` 或 `/forget ID` 选择，新指令重新校验当前目标。不会把“第一条候选”自动视为授权，也不保存待处理的自由文本选择。成功纠正创建显式替代、取代旧事实并重置上下文；忘记还推进自动历史截止水位。已有基于 run 的幂等和凭据拒绝继续生效。

## 自动变更提示

[发布事务](../../src/kestri/memory/repository.py)将一条简短 outbox 提示与成功提取作业、事实和事件一起提交。新增有效事实与替代包含 ID、每项最多 120 字符内容，以及纠正/忘记入口。每作业最多八项。强化、推断候选和空提案静默处理。网络发送随后由已有发送器执行。

outbox 关联提取维护 run，已有 job/events 提供来源，因此不新增提示表或逻辑备份版本。[Store](../../src/kestri/storage/store.py)在领取提示及 HTTP 发送前检查完成/成功状态、auto/use 授权、设置代次、最终 epoch，以及全部提示事实的有效/时间/任务状态。替代的预期 epoch 包含本次提交的一次递增。撤销提示变为 `failed`，错误为 `MemoryNoticeRevoked` 并清空正文，不阻挡后续排队消息。

这些检查不能撤销已经在途的 Telegram 请求。不确定发送沿用保守恢复行为，不盲目重试。恢复取消/隔离业务状态并阻止待发消息，提示不会重放以宣告恢复的事实。

## Checkpoint 存储

Store 连接现在固定 `search_path=public`。[迁移 9](../../src/kestri/storage/sql/009_checkpoint_schema.sql)将旧安装中四张 LangGraph 表从 `kestri` 移到 `public`，不丢失记录。PostgreSQL 默认 `$user` 路径在角色同名时可能将表建到 `kestri`，超出保留期代码的 `public` 检查范围。两边同时存在时报告 `CheckpointSchemaConflict`，整个迁移回滚，不混合状态。处理冲突前备份并检查两份数据。框架表仍不进入逻辑备份，逻辑恢复重置上下文。

## 验证

[控制集成测试](../../tests/memory/test_memory_controls_integration.py)覆盖唯一纠正/忘记、模糊目标与显式选择、相似性不能授权、旧中文 ID、提示重启/强化、关闭/忘记撤销、替代 epoch 和候选静默。[Schema 测试](../../tests/storage/test_checkpoint_schema_integration.py)保留旧迁移记录，并在冲突时拒绝操作、不删除任一副本。[收尾证据](../development/memory-v2-completion.zh-CN.md)区分受控测试、合成质量、真实 Telegram 与部署检查。
