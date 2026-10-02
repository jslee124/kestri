# 通过 Telegram 研究信息

[English](telegram-research.md) · [文档](../README.zh-CN.md)

更新日期：2026-10-02。范围：M1 配置与研究。真实研究流程已在记录范围内验证，见[验证记录](../development/m1-validation.zh-CN.md)。

## 准备本地配置

通过 [uv](https://docs.astral.sh/uv/getting-started/installation/) 安装 Python 3.14，准备支持 Compose 的 Docker 引擎并启动。在仓库根目录执行：

```sh
uv sync --locked
cp .env.example .env
chmod 600 .env
```

如果已有 `.env`，直接编辑，不要覆盖。本地填写 `DEEPSEEK_API_KEY` 与 `TAVILY_API_KEY`。研究会把选定的对话与工具上下文发送到 DeepSeek，把查询和 URL 发给 Tavily，通过 Telegram 传输消息。真实调用消耗服务额度。

为 `POSTGRES_PASSWORD` 设置新的高强度、URL 安全密码，例如执行 `uv run python -c 'import secrets; print(secrets.token_hex(24))'` 生成。此命令会输出凭据，请直接复制到本地配置，不要发到聊天或提交。下面的本地开发方式还需要在 `DATABASE_URL` 填入同一密码：

```text
postgresql://kestri:YOUR_PASSWORD@127.0.0.1:55433/kestri
```

容器方式会将这个 DSN 覆盖为内部数据库地址。示例采用研究限制：8 次模型调用、8 次工具调用、120 秒、4096 输出 token。修改预算前阅读 [M1 参考](../reference/telegram.zh-CN.md)。

## 创建机器人并选择主人

在 Telegram 打开经过验证的 [BotFather](https://t.me/BotFather)，发送 `/newbot`，按提示设置显示名和用户名。将生成的 token 仅保存到 `.env` 的 `TELEGRAM_BOT_TOKEN`。创建机器人不等于授权任何人使用 Kestri。

打开新机器人，自己发送 `/start`，然后执行：

```sh
uv run kestri telegram-id
```

命令输出观察到的私聊用户 ID，不注册主人、不确认消费更新、不调用模型。把 `KESTRI_TELEGRAM_OWNER_ID` 设置为**你自己的数字用户 ID**，不要选择陌生发送者。ID 是身份信息，不是 API 凭据。研究同时要求发送者 ID 匹配，且私聊的聊天 ID 与它一致。

不要为这个机器人设置 webhook，也不要运行另一个轮询程序。Kestri 会拒绝已有 webhook，并通过同数据库、同机器人的锁阻止第二个 Kestri 实例。使用另一数据库的独立轮询程序不受这个锁保护。

## 启动本地流程

使用 Python 开发运行方式：

```sh
docker compose -f compose.yaml -f compose.dev.yaml up -d postgres
uv run kestri telegram
```

这会把 PostgreSQL 发布到本地回环地址 55433 端口，供 Python 进程使用，不隔离该进程与宿主机。也可以使用容器部署：

```sh
docker compose up --build -d
docker compose logs -f app
```

同时只运行一个应用进程。如果之前用了开发数据库覆盖文件，现在希望不发布数据库端口，先停止本地 Python 进程，再只用基础配置执行 `docker compose up -d --force-recreate postgres app`。已有命名卷保留。通过 `docker compose ps` 确认数据库没有发布端口。

启动信息包含机器人用户名及仅限主人私聊的说明。配置缺失或无效时，研究前就会失败。M1 自动创建自己的 schema 和 LangGraph checkpoint 表；PostgreSQL 必须允许这些操作。

## 研究并追问

点击输入框旁的 Menu 查看全部命令，包括 `/runs` 和 `/start`，收起后继续正常聊天。如果旧聊天键盘仍然显示，发送 `/help` 即可移除。选择菜单命令与输入相同命令效果一致。`/stop` 取消工作，`/new` 仅在空闲时开始新上下文，保留历史。

发送：“使用 LangChain 官方文档解释 agent 和 checkpoint 的关系，引用实际读取的页面。”应收到回执，以及已保存、带来源链接的回答。应用独立于模型正文附加获取状态：仅搜索摘要、已提取节选、保存材料截断、或提取失败。

回复回答：“哪一部分是工程推论？”回复会将相应结果和证据引用关联到新请求。普通消息延续最近成功提交的对话。失败、停止和中断的轮次不会成为对话提交头。

发送 `/status`、`/runs`、`/usage` 查看结果。长请求过程中发送 `/stop`；回复某次执行并发送 `/stop` 会针对已知执行。取消会停止本地等待与新工作，但已提交的外部请求仍可能计费。没有进行中或排队工作时，`/new` 开始新的模型上下文，保留归档和证据。

## 停止并了解限制

本地前台进程用 Ctrl+C 停止，容器用 `docker compose stop app`。使用相同命令和卷重新启动。完成的上下文和结果保留；已接受的排队请求仍可执行；正在运行但中断的请求会被告知，不自动重新研究。无法确定是否发送成功的 Telegram 消息会隔离，不盲目重发。

持续任务见 [M2 简报教程](recurring-briefing.zh-CN.md)。M3 已提供个人记忆与自动压缩，从[记忆教程](personal-memory.zh-CN.md)开始。M4 提供[维护与备份恢复](../how-to/operate-local-agent.zh-CN.md)。shell 与桌面控制不在此版本中。无法安全压缩或上下文超限时停止并提示；`/new` 开始新上下文并保留记忆。其他边界见[安全设计](../design/security-and-data.zh-CN.md)和[参考](../reference/telegram.zh-CN.md)。
