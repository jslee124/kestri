# 运行和维护本地助理

[English](operate-local-agent.md) · [文档导航](../README.zh-CN.md)

更新：2026-10-02。

## 启动和检查

完成 [Telegram 设置教程](../tutorials/telegram-research.zh-CN.md)，然后使用一个部署：

```sh
docker compose up --build -d
docker compose ps
docker compose logs --tail 50 app
docker compose exec app /app/.venv/bin/kestri data status
```

应用和数据库使用 `restart: unless-stopped`。Docker 本身必须运行，不会自动配置开机启动或唤醒睡眠电脑。应用每分钟查询数据库记录数量作为健康检查；只证明数据库可访问，不证明 Telegram/模型/搜索服务可用。Docker 重启策略会重启已退出容器，不会仅因 unhealthy 自动重启。持续不健康时检查日志/状态再主动重启。

基础 Compose 不发布数据库端口。应用使用非 root、只读根文件系统、独立工作区卷、受限临时空间/资源、移除 capabilities，不挂载主机 home 或 Docker socket。开发覆盖配置开放回环 PostgreSQL，主机 Python 进程没有容器隔离。容器不构成独立 VM 的安全保证；网络/模型/消息仍使用外部服务。

## 日常使用和恢复

Telegram 的可折叠 Menu 提供全部已注册命令。提问公开研究问题，回复答案继续追问，明确创建每日/每周任务，通过 `/remember` 保存事实。`/status` 和 `/runs` 检查执行/发送，`/usage` 查看本地费用估算。`/stop` 取消前台或指定 ID 执行；`/new` 在空闲时重置对话上下文，保留记忆、任务和归档。控制方式见[任务](../reference/tasks.zh-CN.md)和[记忆](../reference/memory-and-context.zh-CN.md)参考。

`docker compose stop app` 停止，`docker compose start app` 重启，保留卷。已接受请求保留；中断执行会告知，不盲目重新研究；保存结果保留，不确定发送不会盲目重发。任务可按约定窗口合并补跑。睡眠/停止 Docker 会延迟调度。不要用 `docker compose down -v` 日常停止。

升级时停止应用、[备份](backup-and-restore.zh-CN.md)、检查变更/迁移说明、构建并启动。迁移 4 为增量迁移，但增加列和状态，不支持任意降级或迁移后启动旧代码。保留恢复需要的源码版本和私有快照。

## 保留期和显式删除

自动清理在空闲时执行。`data status` 显示最近维护数量或安全错误类型。手动维护需停止应用并预览：

```sh
docker compose stop app
docker compose run --rm --no-deps app data cleanup
docker compose run --rm --no-deps app data cleanup --apply
docker compose start app
```

删除原始历史可替换为 `data delete-history --before 2026-10-01T00:00:00+08:00`，检查后添加 `--apply`。这会保留活跃记忆和任务，它们通过独立指令控制。`data erase` 预览本地内容清除；`data erase --apply` 还会忘记记忆、删除约定与托管备份。执行前阅读[数据参考](../reference/data-lifecycle.zh-CN.md)。外部副本与服务商/Telegram 数据独立处理。应用/数据库错误只输出异常类型，不输出私有原始详情；先修复配置/存储/网络，再重启，不盲目提高额度。
