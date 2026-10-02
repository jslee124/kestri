# 仓库目录结构

[English](repository-layout.md) · [文档](../README.zh-CN.md)

## 源码职责

| 包 | 职责 |
| --- | --- |
| `src/kestri/agent/` | 模型适配、研究图、预算/活动控制、上下文、smoke 与最小运行链路 |
| `src/kestri/memory/` | 个人事实、提取提案、仓库/worker、向量索引及召回 |
| `src/kestri/history/` | 主人归档搜索/读取及历史向量召回 |
| `src/kestri/tasks/` | 任务意图、约定执行与周期调度 |
| `src/kestri/storage/` | PostgreSQL store、迁移、备份/保留及受限证据文件 |
| `src/kestri/integrations/` | Telegram、公开网页工具、embedding 传输、HTTP 与 URL 策略 |

`cli.py`、`settings.py`、`errors.py`、`redaction.py` 和 `application.py` 保留在包顶层，分别承担入口/配置/共享边界及应用编排。导入具体模块；包初始化不重新导出实现，也不创建兼容包装。这是内部模块路径调整，不是稳定 SDK 的 API 迁移。CLI 命令与已有 SQL 对象名称保持一致。

Agent 编排组合领域服务及外部集成。领域代码接收应用提供的主人身份和受限依赖，服务商不决定主人授权。PostgreSQL 基础操作归 storage；有序 SQL 迁移作为 `storage/sql/` 下的资源打包。移动文件不改变数据库 schema，也不迁移生产数据。较大的共享 store 方法可在事务边界稳定后继续提取；本次不为缩短文件而拆开事务。

## 测试与文档

测试按领域放入 `tests/agent`、`memory`、`history`、`tasks`、`storage` 和 `integrations`。共享隔离 fixture 保留在 `tests/conftest.py`，helper 在 `tests/helpers.py`，测试使用绝对包名导入 helper。配置测试保留在测试顶层。正常 `pytest` 命令会发现全部目录。

[实现阅读指南](implementation-guide.zh-CN.md)指向当前具体源码路径。历史验收记录保留当时的证据边界，即使源码链接跟随移动。运行参考维护行为契约，设计文档维护目标架构。移动模块后执行[检查](../how-to/run-checks.zh-CN.md)，包括两套 PostgreSQL、文档链接及 wheel 资源检查。

## 可读性

SQL 使用四空格缩进，每行一个表字段或赋值，布尔条件分行。局部记录变量按职责命名，触发器嵌套分支对齐。在同意水位、失效、租约和计费边界添加简短解释。CI 中的 `python scripts/check_sql_readability.py` 检查 tab、缩进和 100 列宽；它是排版检查，不是 SQL 解析器，也不能代替审查。Python 中的内嵌 SQL 在连接或授权条件复杂时应使用多行文本。

合成采集器放在 `scripts/memory_evaluation/`，`scripts/evaluate_memory_quality.py` 仅提供质量 CLI。记账/评分、提取、选择、历史校准和回答工具各自分离。共享自动记忆测试场景放在 `tests/memory/helpers.py`，测试模块不互相导入。
