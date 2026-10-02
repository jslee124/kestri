# 备份和恢复本地数据

[English](backup-and-restore.md) · [文档导航](../README.zh-CN.md)

更新：2026-10-02。

## 创建并检查备份

在配置好的仓库中，确认 Docker 运行：

```sh
docker compose stop app
docker compose run --rm --no-deps app data backup
docker compose run --rm --no-deps app data status
docker compose start app
```

备份命令输出私有路径 `/workspace/backups/UUID.json`，请本地记录。它位于应用工作区卷，同盘备份不能防止磁盘损坏。异地副本使用可信的私有传输/存储方式并限制访问，不提交备份或混入公开验收证据。可从现有应用容器复制已知路径：

```sh
mkdir -p .kestri/backups
chmod 700 .kestri/backups
docker cp kestri-app-1:/workspace/backups/UUID.json .kestri/backups/UUID.json
chmod 600 .kestri/backups/UUID.json
```

替换为准确的 UUID。主机副本不自动过期。只导出业务记录时，在停止期间运行 `data export /workspace/backups/owner-export.json`；不含证据原文，不能用于恢复。

## 恢复至新目标

不要覆盖现有数据库，也不要为了腾出空目标清空生产卷。保留原安装和备份。准备独立空 PostgreSQL 数据库与空工作区，为本地维护进程配置相应 `DATABASE_URL` 和 `KESTRI_WORKSPACE_DIR`，保留同一 `KESTRI_TELEGRAM_OWNER_ID`。切换安装前停止原 bot。本地开发维护命令是主机进程，使用你的文件权限。

```sh
uv run kestri data restore .kestri/backups/UUID.json
uv run kestri data restore .kestri/backups/UUID.json --apply
uv run kestri data status
```

第一条验证但不导入；检查恢复政策后再执行。源备份必须可读且权限 `0600`。导入证据写入空目标工作区。单独保留 `.env` 和密钥，它们不在备份中。同一个 bot 不运行两个 Telegram poller。

用目标配置启动恢复的安装。等待恢复通知：积压的 Telegram 指令会丢弃一次。检查 `/memory`、`/tasks`、`/runs` 和 `/usage`。需要继续使用的隔离事实重新 `/remember`；检查约定后仅显式恢复需要的任务 ID。历史消息不会自动重发。普通重启是另一路径，会保留原有授权。

## 处理失败

验证失败不改动目标。受控执行失败回滚记录并清除新证据。突然退出/断电可能留下孤立文件：保留源，检查失败目标，再换独立空数据库/工作区重试。不要删除唯一数据副本。仅接受 schema 4、5、6 备份，不接受任意 PostgreSQL dump 或导出。范围和保留政策见[数据参考](../reference/data-lifecycle.zh-CN.md)。

schema 6 恢复还关闭记忆 use 和语义召回。重新输入需要的事实后 `/memory use on`；向量部署就绪时再单独开启语义。派生向量不从备份恢复。
