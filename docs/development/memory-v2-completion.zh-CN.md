# Memory v2 完成记录

[English](memory-v2-completion.md) · [文档](../README.zh-CN.md)

## 已交付行为

实现覆盖了显式启用的自动提取、结构化事实与候选、持久化提取/索引任务、DashScope embedding、PostgreSQL/pgvector 存储、有界混合事实选择与历史搜索/读取、记忆使用开关、自然语言纠错/遗忘和主动变更提示。[记忆控制](../reference/memory-controls.zh-CN.md)列出了支持的表达和授权边界。目标模糊时列出有界候选，不修改记忆；明确 ID 命令选择目标。自动新增/替换在同一事务中写入一条 outbox 提示，强化与候选保持安静。发送前检查同意状态、epoch 和当前事实。

迁移 9 将旧 LangGraph checkpoint 表从 `kestri` 保留迁移到 `public`，连接明确使用 `search_path=public`，使已有 checkpoint 保留与撤销清理作用于真实框架表。两套同名表冲突时直接中止，不合并或删除数据。业务备份 schema 仍为 7。

## 质量证据

[汇总报告](evidence/memory-v2-quality.json)保留所有尝试及各轮报告。采集器使用生产适配器、提取器、选择器、有界组装和提示词处理中文合成案例。历史排序使用完整、标明角色的轮次 JSON。仅开发集独立校准历史相似度为 **0.60**；个人事实阈值仍为 **0.50**。

| 最终采集器 | 开发集 | 留出集 |
| --- | --- | --- |
| 提取匹配的有效事实 | 45/45 | 45/45 |
| 产生有效事实的排除案例 | 0/35 | 0/35 |
| 组装相关事实的 recall at 8 | 46/48 | 47/48 |
| 注入相关事实的负例查询 | 0/12 | 0/12 |
| 历史事实与主人来源引用均正确 | 20/20 | 20/20 |
| 缺少历史证据时正确说明无记录 | 10/10 | 10/10 |

标签由单作者编写。提取语料 v2 在检查 v1 后澄清临时情绪标签，其留出集被复用，并非未触碰留出集。选择评测的查询拆分共享事实身份，注入指标排除始终存在的交流偏好。历史拆分使用不同项目名。两组 dense 历史召回均为 20/20，但十条负例仍全部能返回同主题词法候选，所以候选召回不能证明回答正确。最终回答独立检查完整来源读取、主人引用和缺证据时的回答。

历史回答 v1 使用未注册、预先完成的工具消息，属于无效测试装置；保留报告但不用于产品质量结论。v2 注册真实 search/read 工具，要求先获取句柄再读取；候选固定，因此查询改写与数据库竞态保证另行测试。所有基线与重测共 **843 次提供方请求**，按配置估算 **0.454762 美元**，不计入生产账本，也不是账单。没有使用私人聊天归档。独立人工/领域评审和长期个人聊天准确率尚未测量。

## 验证与部署

本地 pgvector：**259 passed**。普通 PostgreSQL：**231 passed，28 个向量专属案例跳过**。覆盖模糊目标不写入、明确选择、十六进制内容与 ID 区分、唯一自然控制、持久提示、撤销、重启、checkpoint 迁移与冲突保留。本增量还执行 Ruff 检查/格式、mypy、双语文档、可读 SQL 和 wheel/源码包检查。

真实 Chrome Telegram 验收使用独立数据库和工作区，只复制正式环境的轮询 offset。已观察自动两条事实提示、自然 SQLite→PostgreSQL 纠错、模糊 Python 目标仅列出候选、明确遗忘和进程重启后的持久状态。没有把正式聊天导入合成验收库。脱敏[实测记录](evidence/memory-v2-final-live.json)和[部署流程](../how-to/deploy-memory-v2.zh-CN.md)将运行证据与质量分数、CI 分开记录。

## 复现

```sh
.venv/bin/python -m scripts.evaluate_memory_quality --stage extraction --output /private/tmp/extraction.json
.venv/bin/python -m scripts.evaluate_memory_quality --stage selection --output /private/tmp/selection.json
.venv/bin/python -m scripts.evaluate_memory_quality --stage history --output /private/tmp/history.json
.venv/bin/python -m scripts.evaluate_memory_quality --stage history_answer --output /private/tmp/history-answer.json
```

每个实时采集器通过忽略提交的提供方配置与有界评测账本发送固定合成内容，不轮询 Telegram、不读取私人聊天归档。保留报告注明语料哈希、评分版本、分母和限制。计划内实现与内部回归验收已完成；这些合成分数不承诺所有个人聊天的准确率。
