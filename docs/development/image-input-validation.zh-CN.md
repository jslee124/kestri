# 图片输入验证

[English](image-input-validation.md) · [设计](../design/image-input.zh-CN.md)

## 本地结果

2026-10-03，分支 `codex/telegram-image-input`。完整测试 **343 passed，无跳过**，
使用独立的一次性 PostgreSQL 17 + pgvector 数据库、Python 3.14，以及离线
Telegram/DeepSeek HTTP 模拟传输。自动化测试没有使用个人部署或其数据库；
下方独立的真实验收使用了经授权升级的部署。

Ruff 检查/格式、严格 mypy（`src` 与 `scripts`）、双语文档、SQL 可读性、
25 条控制路由评估和源码/轮子构建均通过。wheel 包含 `agent/images.py` 和
迁移 `011_image_inputs.sql`。

## 已验证行为

28 项图片检查覆盖实际解码 PNG/JPEG/WebP；无效、截断、动画、超限和不安全
输入；私有文件；Telegram/网页凭证隔离；重定向及有界下载；主人/私聊授权；照片只选一个尺寸；图片
文件；相册排序、去重、重启、收集时限、数量限制和迟到图片；后发文字等待
相册；图片说明不进入控制或自动记忆；锁定版 DeepSeek 适配器实际发出的多图
请求；看图追问；内存与 PostgreSQL 检查点不保存像素；真实摘要状态更新保留
引用；缺失、过期、越权与被篡改图片；总大小准入；备份/导出字节一致和哈希
校验；恢复待下载附件；擦除和文件删除失败后的重试。

既有研究、任务、记忆、语义历史、检查点 schema 和旧备份恢复测试也通过。
备份 schema 9 包含图片记录；恢复的未完成执行沿用现有隔离策略。

## 复现

使用测试 fixture 要求的独立 `kestri_test` 数据库。不要指向个人数据库：
fixture 会删除应用 schema。

```sh
uv sync --locked
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src scripts
KESTRI_TEST_DATABASE_URL=postgresql://postgres:test-password@127.0.0.1:5432/kestri_test uv run pytest -q
uv run python scripts/check_docs.py
uv run python scripts/check_sql_readability.py
uv run python scripts/evaluate_controls.py
uv build
```

## 真实验收

经授权的合成图片检查通过了真实 DeepSeek 模型和升级后的 Telegram 部署。
两张照片组成的相册只产生一次受理和一次回答，按顺序准确识别颜色、形状和
数字。重启应用后，文字追问仍准确回答第二张图片的数字。将静态 PNG 作为
Telegram 文件发送，也准确识别了颜色、形状和数字。

数据库检查确认相册只创建一个完成的执行，两条图片记录均已就绪，投递没有
重复，相关检查点没有保存图片 data URL。升级前使用旧应用镜像创建了备份。
应用和原 PostgreSQL 数据卷保持健康，pgvector 已启用；部署使用
`compose.vector.yaml`。原始模型响应、截图与备份细节保留在忽略的 `.kestri/` 下。

验收发现图片下载复用了带 Tavily 凭证的网页客户端，现已改为将独立 Telegram
客户端传入研究代理；未提供客户端的调用方创建不带网页认证头的独立连接。
多图集成检查现在使用单独带认证的网页传输，并断言 Telegram 请求不含
Authorization 请求头。

## 证据边界

这些检查证明一次短时合成会话通过，不代表普遍的视觉准确率或长期日常使用
可靠性。尚未运行远程 CI。Telegram 没有相册完成事件，收集使用有界时间窗口。当前图片上下文
最多 10 张、20 MiB；`/new` 重置上下文。摘要文字概括既有对话，后续视觉调用
会读取保留的原始文件，不把摘要当作图片内容的证据。
