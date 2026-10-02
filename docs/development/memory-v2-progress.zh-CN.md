# Memory v2 实施进度

[English](memory-v2-progress.md) · [文档](../README.zh-CN.md)

日期：2026-10-02。范围：`codex/memory-v2` 上的提案提取、持久化运行、语义事实召回与有界历史词项工具。[规格](../design/memory-v2.zh-CN.md)仍是完整目标。代码尚未部署到主人的 Telegram 机器人。

## 提案提取

[MemoryExtractor](../../src/kestri/memory_extractor.py) 校验不可变来源/批次/提案结构、主人与范围、开启水位、消息数量、逐字 Unicode 引用和偏移、目标版本、时序、秘密与时间边界。仅新鲜的主人直接陈述可支持事实，推断留在候选区。强化不能改写内容；近期状态默认 30 天复核。

复用 DeepSeek/LangChain 适配器生成 `MemoryProposal`，只提供结构化响应工具，无研究工具/checkpoint，最多一次模型请求，并复用准入、费用、活动检查、超时和禁用追踪。精确引用证明可追溯来源，不证明语义正确或完美识别敏感内容。

## 持久化运行链路

迁移 5 增加主人开关/版本/代次/水位、接收来源、记忆元数据、`memory_jobs`、`memory_sources`、`memory_events`。默认关闭。`/memory auto on` 保存新归档水位，不回填旧历史。普通主人直接消息的归档和提取作业在同一事务创建；转发/外部回复和显式任务/记忆控制不入队。前台回答失败不会丢弃合法作业。

[MemoryRepository](../../src/kestri/memory_repository.py) 等前台空闲，按主人单通道和来源顺序领取。每个作业提供 1 条新消息、最多 12 条邻近上下文 / 24000 UTF-8 字节，以及最近 20 条合法记忆 / 12000 字节。租约 120 秒，同一维护 run 最多 3 次尝试，重试间隔 5/30 秒。每次重建当前版本，提交时在主人事务锁内复核提案、开关/版本/epoch/租约；事实、引用、事件和成功状态一起提交。新增/强化保留 head，替代重置 head/epoch。容量拒绝终止作业，可通过 `/memory changes` 查看。

[MemoryWorker](../../src/kestri/memory_worker.py) 将提取限制为 60 秒、2048 输出 token，配置更小时从小值。现有 micro-USD 账本记录 `memory_extract`：默认每作业全部尝试合计 0.15 USD、UTC 月提取合计 1.50 USD，并受主人总月预算限制。未知请求保留预留。本增量只调用 DeepSeek 提取，CNY embedding 换算留待向量集成。

`/memory pending` 查看候选；`/correct ID 完整内容` 显式确认或纠正，`/forget ID` 丢弃候选。`/memory changes` 查看最近自动事件、作业状态和固定失败类别。不会主动发送自动变更提示。`/memory auto off` 取消排队/在途作业，已有记忆仍可使用。忘记会推进较广的旧历史截止位置。备份 schema 5 包含新表，接受 schema 4 并补保守默认值。恢复关闭自动提取、取消作业、隔离 active/candidate 记忆。来源保留清理删除引用并使依赖的自动事实到期；清空数据关闭提取。

## 验证

提取器有 25 项受控测试。 本地独立 PostgreSQL 17 完整测试：**191 项通过、无跳过**；Ruff 检查/格式、mypy（29 模块）、88 份双语文档、wheel/sdist 构建通过，wheel 包含迁移 5 和两个新运行模块。持久作业测试覆盖开关/来源/去重、前台优先、并发领取、事务提交、候选隔离/确认/丢弃、纠正/忘记竞态、租约回收、有限重试、记账、真实框架 HTTP mock、来源清理和 schema 4/5 恢复。按[检查指南](../how-to/run-checks.zh-CN.md)在独立 PostgreSQL 跑完整测试。这些检查不证明真实提取质量、中文语义精度或已部署机器人验收。

## 语义存储与召回

迁移 6、事务索引 trigger/作业、pgvector 精确余弦存储、版本化对称 L2 编码、CNY→USD 预留、主人 use/semantic 控制与混合召回已实现。[语义运行参考](../reference/semantic-memory.zh-CN.md)为当前数字/行为契约。基础 Compose/生产卷未改；可选同基础 PostgreSQL 17 Alpine + pgvector 0.8.7 覆盖镜像已在隔离容器构建、验证。只从本地读取已有 embedding key/URL，源码不含 key。

受控验证：该 pgvector 镜像 **208 项通过、无跳过**；普通 PostgreSQL 17 **195 项通过、13 项向量测试跳过**。语义测试包含真实框架筛选/研究请求的 HTTP mock，以及保存图消息不含注入记忆的检查。Ruff 检查/格式、mypy（32 模块）、双语文档和 wheel/sdist 覆盖新增量。上文 191 项为上一批提取增量。这些结果不代表真实私人聊天服务测试、中文召回质量达标、已有卷升级或已部署机器人验收。

## 有界历史工具

[HistoryRetriever](../../src/kestri/history.py) 已接入前台图。auto/use 同时开启时才可使用，auto 改变重置 head/epoch。主人/任务身份由应用固定；搜索仅最新最多 200 个合格轮次、最多 5 个正匹配节选，读取同 run 句柄后重新检查权限和完整来源 hash。每轮最多 12 条消息/8000 字符，超限整轮跳过；无相关结果不填充最近聊天。未新增表/迁移，历史向量索引仍未实现，详见[契约](../reference/history-retrieval.zh-CN.md)。

历史增量有 9 项受控测试，含真实框架 HTTP mock、任务范围和 200 轮窗口检查。完整本地 pgvector 测试 **217 项通过**；普通 PostgreSQL **204 项通过、13 项向量测试跳过**。Ruff、mypy（33 模块）、92 份文档和打包检查通过。前述 208 项属于上一批语义事实增量。本批没有私人聊天服务调用或部署验收，完整 Memory v2 仍待评测。

## 剩余增量

下一步：历史片段向量索引与混合检索、中文标注评测语料、隔离的真实 Telegram/服务商召回及重启/忘记/恢复验收。向量阈值与交流偏好标记在评测前仍是暂定策略。记忆使用开关、语义存储/召回、embedding 币种记账现已实现。自然语言模糊纠正目标解析和主动变更通知仍暂缓，显式 ID 控制可用。完整 Memory v2 尚未验收。
