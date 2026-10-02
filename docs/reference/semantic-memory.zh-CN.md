# 语义记忆运行链路

[English](semantic-memory.md) · [文档](../README.zh-CN.md)

更新：2026-10-02。功能分支实现已部署，auto/semantic 关闭；真实私人聊天质量评测仍未完成，见[部署记录](../how-to/deploy-memory-v2.zh-CN.md)。

## 控制与数据披露

配置好 embedding 且向量表就绪后，`/memory semantic on` 开启语义索引/召回，默认关闭。有效保留事实和有界查询发送到北京 DashScope，候选筛选发送到 DeepSeek。可索引已有有效事实，不提取旧原始聊天。`/memory semantic off` 取消索引作业，恢复原有关键词/近期检索，本地向量保留以便复用。`/memory use off` 停止全部记忆注入和索引 HTTP 调用；自动提取是独立开关，由 `/memory auto off` 控制。开启/关闭 use 或 semantic 都重置前台上下文/epoch、增加检索代次。`/memory` 显示三项设置，`/memory changes` 显示提取/索引作业数量和安全失败。拒绝转发控制。

自动提取仍默认关闭，只处理 `/memory auto on` 之后的直接聊天。推断候选不进入上下文或索引。`/correct`/`/forget`、复核期限、来源清理和清空数据使派生索引失效。服务商迟到响应仍可能计费，但不能发布已撤销事实。恢复关闭提取、使用与语义召回；重新授权事实后，用 `/memory use on` 明确启用使用，需要语义能力时再单独开启。

## 索引契约与 worker

迁移 [006_semantic_memory.sql](../../src/kestri/storage/sql/006_semantic_memory.sql) 总是增加设置和 `memory_index_jobs`。服务器提供 pgvector 时，在 `public` 启用扩展并创建 `vector(1024)` 的 `memory_embeddings`，数据库角色需扩展/建表权限。普通 PostgreSQL 仍受支持，开启语义会返回可操作提示。本契约要求 pgvector 位于 `public` schema。

数据库 trigger 将合法事实变更与索引作业一起提交。作业标识包括记忆 ID、版本、MD5 内容指纹、向量空间和检索代次；MD5 用于变更检测，不用于鉴权。候选/无效事实不入队。变更删除旧向量，取消失效作业/run/预留。worker 等待前台空闲，按主人顺序领取，租约 120 秒，同一维护 run 最多三次尝试（间隔 5/30 秒）。计算在事务外，发布前重查开关、来源状态/版本/hash、租约和代次。向量计算不能重新启用来源。

空间指纹包含服务商、北京工作区接口、模型、1024 维和 `compatible-float-symmetric-l2-v1`。事实/查询用相同 OpenAI 兼容 float 编码，存储/比较前本地 L2 归一化，避免 float32 溢出/下溢。API 向量/用量继续经过适配器校验，不能固定服务商模型权重。空间改变后，需要在新配置下显式 `/memory semantic on`，排入独立代次，不混用空间。不创建 HNSW/IVFFlat，SQL 使用精确余弦距离及当前事实关联。[pgvector 官方查询/索引契约](https://github.com/pgvector/pgvector#querying)说明这些运算符与默认精确搜索。

## 召回与失败行为

每次合法请求读取一致的主人/范围事实快照：active、非空、任务状态、生效时间、到期与复核期限，数量上限为配置的自动加显式容量（最多 1064）。稳定交流偏好使用内容标记启发式，最多六条 / 2000 字符。它不是完美偏好分类器，仍需标注评测。

查询由当前请求加最多四条近期 human/assistant 对话组成，上限 4000 字符和 8192 UTF-8 字节，不改原研究输入。`nfkc-ascii-overlapping-cjk-bigram-v1` 规范化 Unicode、保留 ASCII 词项和重叠中文双字词，使用固定小型停用表。IDF 加权词项分数选最多 20 条正匹配。SQL 按主人/范围、当前版本/hash、准确空间过滤，取最多 20 条精确余弦候选，用 Reciprocal Rank Fusion 合并，`k=60`。

一次结构化 `MemorySelection` 只选择已提供 ID，最多八条或空；无研究工具/checkpoint、不重试，输出最多 512 token，候选/查询上限 12000 字节。前台查询 embedding 与筛选共用默认 10 秒期限和前台预算。服务失败、超时、非法选择或预算不足，降级为有界正词项匹配；不填入近期无关条目或虚构向量分数。核心偏好与相关事实合计最多 6000 字符，主请求仍经过完整输入准入。

retriever 在 run 内缓存选中 ID，每次模型请求重查合法事实/版本，每 run 至多一次 embedding 和筛选。新增导致版本变化时本地重选，竞态最多再本地重查一次，重复变化则停止。epoch/use 变化停止旧工作，不用降级绕过撤销。记忆只进入临时模型请求，不写图消息。非语义模式仍使用原有有界关键词/近期行为。

## 配置与记账

产品读取 `DASHSCOPE_API_KEY`、`KESTRI_EMBEDDING_BASE_URL`，模型为 `text-embedding-v4`，维度固定 **1024**。独立 smoke 仍支持服务商其他维度。未提供/空 key 或未提供 URL 时产品 embedding 不可用；非法已提供 URL 或非 1024 产品维度会校验失败。URL 需为官方北京工作区地址。key 继续只放在 Git 忽略的本地配置。

| 变量 | 默认 | 接受范围 / 含义 |
| --- | --- | --- |
| `KESTRI_EMBEDDING_CNY_PER_MILLION` | 0.5 | 大于 0、不超过 100；配置的 CNY 输入估算 |
| `KESTRI_EMBEDDING_USD_PER_CNY` | 0.15 | 大于 0、不超过 1；固定操作者换算，不是实时汇率报价 |
| `KESTRI_EMBEDDING_CONVERSION_VERSION` | `fixed-v1` | 1–64 字符；保留在账本元数据 |
| `KESTRI_MEMORY_RETRIEVAL_TIMEOUT_SECONDS` | 10 | 大于 0、不超过 30；查询 embedding/筛选总期限 |
| `KESTRI_MEMORY_DENSE_MIN_SIMILARITY` | 0.50 | -1–1；合成事实候选初步校准，最终选择质量仍未测量 |

0.5 CNY/百万估算与 2026-10-02 核对的[官方模型价格](https://help.aliyun.com/zh/model-studio/text-embedding-v4)中北京在线文本输入一致，不保证将来账单价格。换算是明确的本地记账策略。HTTP 前按 UTF-8 字节加每文本 256 单位预留，USD 估算向上舍入为 micro-USD，保留原币种估算/费率/版本。按合法用量结算，未知调用保留保守预留。秘密/尺寸本地拒绝先于预留，免费额度不关闭预算。

`memory_index` 与 `memory_extract` 共用默认 0.15 USD/作业、1.50 USD/UTC 月维护上限，还计入主人总月预算。`memory_query`、`memory_select` 受前台/后台 run 与主人月预算限制，不把 CNY 直接加入 USD 账本。原币种元数据不是服务商账单。独立 smoke 继续在数据库账本之外。

## 部署与兼容

基础 Compose 镜像/卷未改。用有 checksum 的 pgvector 0.8.7 源码构建可选同基础 PostgreSQL 17 Alpine 扩展镜像：

```bash
docker compose -f compose.yaml -f compose.vector.yaml build postgres
```

已有实例先停止 app，用当前代码/配置创建私有逻辑备份。用覆盖文件重建 PostgreSQL，再用两份 Compose 文件重新构建/启动 app。保留已有数据库/工作区卷，不删除。本地安装已执行此流程；[部署记录](../how-to/deploy-memory-v2.zh-CN.md)区分部署检查与语义质量验收。见[操作指南](../how-to/operate-local-agent.zh-CN.md)和[备份/恢复](../how-to/backup-and-restore.zh-CN.md)。确认 schema 健康后再 `/memory semantic on`。覆盖文件保留原数据库大版本/发行版/目录；打包和独立数据库测试不证明主人现有卷升级或已安装机器人验收。

当前备份 schema 7 包含设置及事实/历史索引作业，不含可重建向量行。恢复兼容 schema 4/5/6/7，严格校验列并补保守默认值，要求派生索引为空，隔离有效/候选事实、取消索引作业、关闭所有记忆控制。清理/清空通过状态变更 trigger 删除依赖来源的向量；显式事实按独立保留意图继续存在。索引作业保留 ID/hash 和安全错误，不复制事实正文。

## 验证边界

[单元测试](../../tests/memory/test_semantic_memory.py) 覆盖词项/融合/查询/空间契约。[数据库测试](../../tests/memory/test_semantic_memory_integration.py) 覆盖入队/版本、重启租约、取消、在途关闭/忘记、共享预算、CNY 元数据/未知费用、HTTP mock 语义改写筛选、词项降级/零匹配、图注入、来源清理和 schema 5/6 恢复。CI 分普通 PostgreSQL 和 pgvector 两组，仅普通组跳过向量测试。源码/wheel 检查需包含迁移 6 和三个新模块。

这些证明策略/数据边界和受控流程，不证明实际服务商输出的语义准确性。中文标注语料、历史工具、真实 Telegram/服务商验收和长期召回评测仍是独立增量。

本分支新增[有界聊天历史工具](history-retrieval.zh-CN.md)，在 auto/use 同时开启时供模型按需调用；历史检索与个人事实向量检索是独立链路，渐进历史语义缓存/混合召回已实现，持久后台索引已实现，质量评测仍待完成。
