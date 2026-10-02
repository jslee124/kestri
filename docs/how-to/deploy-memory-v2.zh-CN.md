# 本地部署 Memory v2

[English](deploy-memory-v2.md) · [文档](../README.zh-CN.md)

更新：2026-10-02。本文同时记录已完成的本地部署。完整语义质量验收仍待完成。

## 当前部署

源码 `b1d7bf27450fde2f595db85a2374d12fb5884824` 正运行于原有 `kestri-app-1`，容器中的 Python/SQL hash 与该版本一致。PostgreSQL 保留 `kestri_database`、同一 PostgreSQL 17 Alpine 基础镜像与数据目录；可选覆盖文件增加 pgvector 0.8.7。数据库从迁移 4 升至 8。迁移刚完成时，原有 27 条运行记录、113 条消息不变。原工作区卷保留。

两个容器均健康。Telegram `/memory` 返回 **auto 关闭、use 开启、semantic 关闭**；主动重启 app 后，`/memory changes` 返回没有后台作业或失败。这些检查没有提取或向量化生产聊天内容。[脱敏证据](../development/evidence/memory-v2-deployment.json)记录镜像摘要与验证边界；此前的[隔离真实验收](../development/memory-live-validation.zh-CN.md)独立覆盖合成语义工作流。分支未合并至 main。

## 操作当前安装

在仓库根目录执行：

```sh
docker compose -f compose.yaml -f compose.vector.yaml ps
docker compose -f compose.yaml -f compose.vector.yaml exec app /app/.venv/bin/kestri data status
docker compose -f compose.yaml -f compose.vector.yaml restart app
```

之后的 build/up 命令保留**两份** Compose 文件，让 PostgreSQL 继续使用扩展镜像。只用基础文件执行 `docker compose up` 可能替换数据库镜像。不要使用 `down -v`。Docker 必须运行；`unless-stopped` 不会唤醒休眠电脑。

自动学习和语义召回分别由主人控制。需要时在 Telegram 发送 `/memory auto on`、`/memory semantic on`。auto 从新水位开始，不提取旧聊天；semantic 可索引已授权的有效事实。数据目的地与预算见[语义记忆](../reference/semantic-memory.zh-CN.md)。本次部署没有代替主人开启这些控制。

## 升级前保留可恢复快照

先构建，再停止 poller：

```sh
docker compose -f compose.yaml -f compose.vector.yaml build app postgres
docker compose -f compose.yaml -f compose.vector.yaml stop app
```

运行任何新版应用命令之前，保存完整 PostgreSQL dump 和工作区归档。`data backup` 调用 `Store.open()`，可能应用迁移，不能代替迁移前快照。构建前给旧 app 镜像保留独立标签。私有快照放在忽略的 `.kestri/deployment/`，目录权限 `0700`、文件权限 `0600`，不混入公开证据。

已完成部署在 `.kestri/deployment/2026-10-02-memory-v2/` 保留 `database-before.dump`、`workspace-before.tar.gz`、迁移后 schema 7 逻辑备份、私有校验和及私有 `rollback.compose.yaml`。dump 已用 `pg_restore --exit-on-error` 恢复到独立临时数据库，迁移/运行/消息数量匹配。工作区归档中的每个文件均可读取。检查用临时容器及其匿名卷已删除。

检查快照后，用覆盖文件重建 PostgreSQL。新版镜像的 `data backup` 会初始化 schema，但不启动 Telegram 或模型调用；随后启动 app：

```sh
docker compose -f compose.yaml -f compose.vector.yaml up -d --no-build postgres
docker compose -f compose.yaml -f compose.vector.yaml run --rm --no-deps app data backup
docker compose -f compose.yaml -f compose.vector.yaml up -d --no-build app
```

检查迁移版本、向量表、原记录数量、`/memory`、健康状态和 app 重启。数据库健康检查不证明模型可用。

## 在独立卷中回退

不要让旧 app 或没有扩展的 PostgreSQL 镜像连接升级后的生产数据库。优先向前修复。确需回退时，停止当前 app、保存新增数据，将**升级前** dump/工作区恢复到独立项目。已保留的私有 Compose 文件使用 `kestri-app:rollback-pre-memory-v2`、原 PostgreSQL 镜像、独立命名卷、已有本地凭据和相同容器隔离。该 Compose 配置已验证，未打印秘密。

以下是保留的回退操作步骤，本次没有在生产执行。仅在回退卷为空时，从仓库根目录执行：

```sh
docker compose -f compose.yaml -f compose.vector.yaml stop app
docker compose --env-file .env \
  -f .kestri/deployment/2026-10-02-memory-v2/rollback.compose.yaml up -d postgres
```

等待独立数据库报告就绪，再恢复：

```sh
docker compose --env-file .env \
  -f .kestri/deployment/2026-10-02-memory-v2/rollback.compose.yaml \
  exec -T postgres pg_restore -U kestri -d kestri --exit-on-error \
  < .kestri/deployment/2026-10-02-memory-v2/database-before.dump

docker run --rm -i --network none \
  -v kestri-memory-v2-rollback_workspace:/target \
  --entrypoint tar postgres:17-alpine -xzf - -C /target \
  < .kestri/deployment/2026-10-02-memory-v2/workspace-before.tar.gz
```

检查恢复记录和 Telegram offset/待处理工作后，使用同一私有 Compose 文件启动回退 app。同一个 bot 只能运行一个 poller。快照回退不包含快照后接收的聊天，且可能重新暴露 Telegram 待处理更新。保留升级后的卷以便对账，不删除任一数据副本。原始 dump 恢复与 `kestri data restore` 不同；后者接受逻辑备份并主动隔离状态。

## 剩余工作

常驻部署已完成，显式授权开关关闭。独立提取/选择/回答评分、历史 JSON 阈值校准、自然语言模糊纠正和主动记忆变更提示仍待完成。候选召回指标与合成真实工作流不代表完整 [Memory v2 质量门槛](../design/memory-v2.zh-CN.md)通过。
