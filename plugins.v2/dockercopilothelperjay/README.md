# DockerCopilotHelper / DC 助手

配合 DockerCopilot 完成：

- 容器更新通知（按 cron 检查 updatablelist 中是否有新版本）
- 容器自动更新（按 cron 对 autoupdatelist 中的容器触发更新任务）
- **强制更新（v1.2.0 新增）**：跳过 `haveUpdate` 检查，对指定容器或 `autoupdatelist` 中所有容器立即触发一次更新任务
- **版本对比通知（v1.4.0 新增）**：更新成功后通知附带"旧镜像 → 新镜像"对比；浮动 tag 时提示核对实际版本
- 容器备份（按 cron 调用 DockerCopilot 备份接口）

## 强制更新用法

- Slash 命令：`/dcfupdate` 强制更新 `forceupdatelist` 全部容器；`/dcfupdate <容器名>` 强制更新指定容器（须在 forceupdatelist 中）
- API：`POST /api/v1/plugin/DockerCopilotHelper/force_update`，body 可选 `{"container_name": "xxx"}`，需要 apikey 鉴权
- **严格模式**：仅当目标容器在 `forceupdatelist` 中时才执行；列表外或不存在的容器直接拒绝并推送错误通知

适用场景：DC 服务未正确检测到更新（如 registry 限速、本地缓存），或者你确认想立即拉一次镜像重建容器。

## 配置项

- `updatecron`：更新通知 cron
- `updatablelist`：参与更新通知的容器列表
- `updatablenotify`：是否在检测到新版本时推送通知
- `autoupdatecron`：自动更新 cron
- `autoupdatelist`：参与自动更新的容器列表
- `autoupdatenotify`：自动更新结果是否推送通知
- `schedulereport`：是否推送更新进度
- `deleteimages`：自动/强制更新前是否清理无用镜像
- `backupcron`：备份 cron（留空不启用）
- `backupsnotify`：备份结果是否推送
- `forceupdatelist`：允许强制更新的容器列表（在 UI 的"强制更新"标签页配置）
- `host`、`secretKey`：DockerCopilot 服务地址 + 共享密钥
- `intervallimit`、`interval`：更新进度轮询上限与间隔

## 注意

- 强制更新会让目标容器停服、重新拉镜像、重启，请评估对生产服务的影响
- 仅信任 `host` / `secretKey` 来源；该密钥在 DC 服务端具有容器管理权限