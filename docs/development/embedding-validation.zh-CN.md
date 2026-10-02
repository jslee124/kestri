# Embedding 接入验证

[English](embedding-validation.md) · [文档](../README.zh-CN.md)

日期：2026-10-02。范围：独立北京 DashScope 适配器、配置、CLI、脱敏注册与 Memory v2 规格。完整自动记忆及向量存储尚未实现。

## 离线检查

`tests/integrations/test_embedding.py`覆盖请求序列化、乱序响应、非法维度/数值/零范数/索引/模型/用量、输入准入、隐藏凭据的错误、重定向、接口限制、环境维度解析与证据序列化。现有测试同时检查共享 HTTP 行为和配置回归。见[运行检查](../how-to/run-checks.zh-CN.md)。最终本地结果在执行后记录于下方，不宣称远端 CI 或已安装容器验收。

本地最终检查：Ruff lint/format、mypy（26 个源码文件）、文档检查（86 份）及 `git diff --check` 通过。离线测试 81 passed、66 skipped；跳过项需要独立可丢弃数据库，本次未运行数据库集成测试。25 个 embedding 测试覆盖本增量。未运行远端 CI 或更换运行容器。密钥检查确认未出现在可审查源码/文档中，本地 `.env` 权限为 0600。

## 真实服务证据

[脱敏 JSON](evidence/embedding-live.json)记录 2026-10-02 05:47:30 UTC（Asia/Shanghai 13:47:30）的一次请求：北京 `text-embedding-v4`、1024 维、3 条向量、39 input/total Token。相关余弦相似度 0.646563，无关 0.201611，比较通过。仅发送固定非个人测试句，结果不含密钥、主人空间 ID、完整向量或个人归档。本地凭据存于被忽略、仅主人可读的 `.env`。

## 证据边界

证明配置接口鉴权、向量/用量校验与一项固定语义比较，不证明一般中文召回、自动提取、pgvector 持久化、历史搜索、产品账本预算、Telegram 行为、重启/忘记/恢复或部署验收。独立调用消耗服务额度，未核对账单/免费额度结算。后续验收遵循 [Memory v2](../design/memory-v2.zh-CN.md)。
