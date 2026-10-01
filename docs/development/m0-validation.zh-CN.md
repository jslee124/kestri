# M0 验证记录

[English](m0-validation.md) · [文档](../README.zh-CN.md)

验证日期：2026-10-01。状态：M0 在以下范围内已验证。

## 代码版本与环境

代码版本：引入本记录的 Git 提交，可用 `git log --diff-filter=A --format=%H -- docs/development/m0-validation.md` 查询。纯文档基线为 `e07e2d4`。

实现指纹（SHA-256）：`212b31a71cf466ed3f4a23544ae16baa9e401c68f7782b3d0aaa9a670ec0dfe8`。计算方法为依次拼接每个路径、一个 NUL 字节、文件内容及另一个 NUL 字节；文件顺序为排序后的 `src/kestri/*.py`，再接 `pyproject.toml` 和 `uv.lock`。该指纹独立于后续文档修改，标识真实调用检查使用的实现。

本地环境：macOS、arm64、CPython 3.14.7、uv 0.12.3。锁定的接入版本：LangChain 1.4.3、langchain-deepseek 1.1.1、LangGraph 1.2.12。项目基线为 Python 3.14，依赖已在该解释器上成功安装。

## 受控检查

| 检查 | 观察结果 |
| --- | --- |
| Ruff lint 与格式 | 通过 |
| 应用源码 strict mypy | 通过 |
| pytest | 18 个通过；离线，不需要服务凭据 |
| 双语、本地链接及标识符检查 | 通过；有限检查范围见 `scripts/check_docs.py` |
| 源码分发包与 wheel 构建 | 本地 `uv build` 通过 |

测试在模拟 HTTP 上执行真实框架循环与 SDK 请求序列化，覆盖两轮连续性、工具调用及跨轮思考状态回传、空 assistant 工具调用内容、严格工具参数、已知工具错误、服务认证失败、模型和工具上限、期限取消、显式取消、配置服务地址与无密钥证据。失败或中断后的会话不能继续。服务错误正文被隐藏。

[CI 工作流](../../.github/workflows/checks.yml)在 Linux、Python 3.14 上重复离线检查和包构建。远程结果见 [GitHub Actions](https://github.com/jslee124/kestri/actions/workflows/checks.yml)；本初始记录不在工作流完成前声称远程通过。

## 真实 DeepSeek 证据

| 模式 | 证据 | 观察结果 |
| --- | --- | --- |
| `disabled` | [非思考记录](evidence/m0-disabled.json) | 两轮通过验证，四次模型响应，工具成功返回 42 和 50 |
| `enabled` | [思考记录](evidence/m0-enabled.json) | 两轮通过验证，四次模型响应，工具成功返回 42 和 50 |

两次检查均在官方地址使用 `deepseek-flash`，限制如记录所示，SDK 重试为零。模型请求 `checked_add`，收到真实结果后回答，再在上一结果上加 8。保留用量元数据、模式、版本与耗时，不声称精确账单。

思考模式执行中并非每次响应都包含思考内容。记录使用布尔值标明哪些响应包含。请求回传由请求载荷级回归测试单独验证。思考原文保留在进程内 agent 状态中，不进入公开证据。兼容适配器隔离了一个 SDK 私有钩子；升级依赖时必须重跑该回归和真实调用检查。

## 追溯与限制

本次验证满足 [M0 退出条件](milestones.zh-CN.md)，为 CHAT-001、SEC-001、OPS-001 与 OPS-002 打基础，仅覆盖 AC-12 的模型和工具部分。没有关闭任何完整的第一版验收案例。

M0 尚无 Telegram、网页获取、PostgreSQL、持续任务、个人记忆、自动压缩、输入 token 预算、月度费用限制、工作区访问或 Docker 隔离。LangGraph 检查点是临时的。失败和限制证据来自受控离线检查，真实执行验证服务正常路径。这些检查不证明长期可靠性、通用推理质量、部署安全或个人试用结果。

下一目标为 M1，即首个 Telegram 研究流程。额外授权、持久化、工具边界与恢复条件见[里程碑](milestones.zh-CN.md)。
