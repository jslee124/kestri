# 北京 Embedding 接入

[English](embedding.md) · [文档](../README.zh-CN.md)

更新：2026-10-02。状态：已实现独立服务适配器与真实 smoke 命令。本增量不启用自动记忆、不创建 pgvector 表、不更换 Compose/数据库卷，也不在 Telegram 聊天中自动调用 embedding。后续集成见 [Memory v2](../design/memory-v2.zh-CN.md)。

## 本地配置

在[北京 API key 控制台](https://bailian.console.aliyun.com/cn-beijing/model/settings/api-key)创建独立 key，选择华北2（北京），记录 key 所属业务空间 ID。个人可用默认空间；自定义模型权限需包含 `text-embedding-v4`。密钥与接口必须同地域。凭据只写入被忽略的本地 `.env`，不写文档、源码、日志或聊天。

```dotenv
DASHSCOPE_API_KEY=YOUR_LOCAL_KEY
KESTRI_EMBEDDING_BASE_URL=https://YOUR_WORKSPACE_ID.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
KESTRI_EMBEDDING_MODEL=text-embedding-v4
KESTRI_EMBEDDING_DIMENSIONS=1024
KESTRI_EMBEDDING_TIMEOUT_SECONDS=20
KESTRI_EMBEDDING_EVIDENCE_DIR=.kestri/evidence
```

替换真实业务空间 ID；`.env.example` 只含占位值。保留 DeepSeek 聊天 key/模型。本接入使用 httpx HTTP，不调用 OpenAI 服务，不需要额外 SDK 或下载本地模型。主人专属地址与密钥只存在本地。用 `chmod 600 .env` 限制文件权限。若 key 已通过聊天或截图分享，应在控制台轮换并替换本地值；代码无法清除上游聊天副本。

## 支持的配置

`EmbeddingSettings` 独立读取环境与当前目录 `.env`，不需要聊天/数据库凭据。缺失/非法配置不访问服务并返回 2。无需 `KESTRI_EMBEDDING_PROVIDER`：当前适配器固定为北京 DashScope。

| 变量 | 默认值 / 校验 |
| --- | --- |
| `DASHSCOPE_API_KEY` | 必填非空白 SecretStr，不出现在 repr |
| `KESTRI_EMBEDDING_BASE_URL` | 必填 HTTPS 北京业务空间 URL，路径 `/compatible-mode/v1`；无用户信息、query、fragment；仅允许默认端口或 443 |
| `KESTRI_EMBEDDING_MODEL` | `text-embedding-v4`，拒绝其他模型 |
| `KESTRI_EMBEDDING_DIMENSIONS` | 1024；允许 64/128/256/512/768/1024/1536/2048 |
| `KESTRI_EMBEDDING_TIMEOUT_SECONDS` | 20；>0 且 ≤60 秒；HTTP 阶段超时，不是总工作流期限 |
| `KESTRI_EMBEDDING_EVIDENCE_DIR` | `.kestri/evidence`，相对当前工作目录 |

可选 DashScope key 同时加入 Telegram/data 的配置秘密脱敏集合，与是否启用 bot embedding 无关。脱敏不加密归档或文件。环境字符串中的数字维度先解析，再校验允许值。

## 适配器契约

[EmbeddingClient](../../src/kestri/integrations/embedding.py)向 `<base_url>/embeddings` POST，包含 bearer 鉴权、模型、字符串列表、维度与 `encoding_format=float`。不重定向、不隐式重试。调用方提供并负责关闭配置适当超时的 AsyncClient；smoke 明确设置超时。HTTP 前检查最多 10 条非空白输入，每条最多 8192 UTF-8 字节。这是保守本地字节限制，不是服务商 8192 Token 限制。包含配置的 embedding key 的输入被拒绝。未来自动记忆调用方仍需更广的来源/秘密准入。

响应最多 2000000 字节。要求模型匹配、每输入一项、索引唯一且覆盖批次、维度匹配、数字有限且不是布尔值、范数有限非零，用量是非负整数且 total ≥ input。按输入索引重排，返回不可变向量 tuple 与 input/total Token。错误使用安全类别，CLI 不输出 HTTP 错误正文或传输详情。向量使用/保存前完成校验。

## 运行真实检查

```sh
uv run kestri embedding-smoke
```

一次请求编码三条固定非个人文本：项目求职目标、语义改写、无关晚餐。没有任意提示参数，不读取主人归档、不连接数据库、不发送 Telegram、不保存向量。检查有效向量，以及相关余弦相似度高于无关相似度。JSON 证据含 UTC 时间、服务商/地域/模型/维度、请求/向量数量、用量、相似度和通过状态，不含 key、业务空间地址、输入原文或完整向量。目录被 Git 忽略。

退出 0 表示本项有限比较通过；1 表示服务/校验/证据失败或比较失败；2 表示配置/参数错误；中断为 130。未知用量或错误不自动重试。独立检查消耗服务额度，但不进入产品 PostgreSQL 费用账本。[验证记录](../development/embedding-validation.zh-CN.md)区分接口检查与未来记忆召回质量。

## 存储与下一阶段

向量是数值索引，不替代记忆原文。计划在 PostgreSQL 中用 pgvector `vector(1024)`，按内容版本/hash、向量空间版本关联有效事实。先安装服务器扩展再激活 SQL；当前 `postgres:17-alpine` 镜像未变。先采用精确余弦搜索，不未经测量建立近似索引。同维度不同模型也不能混用，换模型/编码方法需重建，旧作业不能发布替代前的向量。本增量尚未实现向量表或产品检索路径。

## 官方来源与价格

2026-10-02 核对：[API key 说明](https://help.aliyun.com/zh/model-studio/get-api-key)、[embedding 接口](https://help.aliyun.com/zh/model-studio/text-embedding-synchronous-api/)、[国内价格](https://help.aliyun.com/zh/model-studio/model-pricing)、[pgvector](https://github.com/pgvector/pgvector)。北京 `text-embedding-v4` 标价为每百万输入 Token 0.5 元；免费额度资格/有效期以账号控制台为准。提取和候选选择使用聊天模型，另行计费。价格与权限可能变化，当前接入没有向产品账本硬编码货币换算。


产品向量索引/混合召回与带版本 CNY→USD 记账现已单独实现，见[语义运行参考](semantic-memory.zh-CN.md)。本篇的独立 smoke 仍不读取个人聊天或数据库，也不启用开关；上文存储设想描述接入增量的原始边界。
