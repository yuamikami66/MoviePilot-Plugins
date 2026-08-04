# 更新日志 / Changelog

本插件所有版本变更记录。

## v1.5.0 (2026-08-04)

### 重命名

- 插件显示名：`DC助手` → `DC助手+`
- 类名 / plugin_id：`DockerCopilotHelper` → `DockerCopilotHelperJay`
- config_prefix：`dockercopilothelper_` → `dockercopilothelperjay_`
- ⚠️ 升级前需先卸载旧插件并备份配置（备份示例见 `backup/config-backup-1.4.0.json`），重装后用 `update_plugin_config` 写回

## v1.4.0 (2026-08-04)

### 新增

- **更新成功通知展示版本对比**：自动更新、强制更新成功后，通知附带"旧镜像 → 新镜像"对比
  - 创建任务通知附"旧镜像"
  - 更新成功汇总通知附"旧镜像 / 新镜像"对比
- **浮动 tag 提示**：当新旧镜像字符串相同（多为 latest 浮动 tag）时，附"⚠️ 镜像 tag 未变"提示，建议到 DockerCopilot 或 registry 核对实际版本
- **新增辅助方法**：
  - `_fetch_container_image(jwt, name)`：更新后重新调 `/api/containers` 拿新镜像
  - `_post_update_summary(name, source, old, new)`：推送更新成功汇总通知

## v1.3.0 (2026-08-04)

### 新增

- **`forceupdatelist` UI 配置项**：新增"强制更新"标签页，从容器列表中多选允许强制更新的容器
- **强制更新改为严格模式**：仅当目标容器在 `forceupdatelist` 中时才执行；不传参数时遍历整个 `forceupdatelist`；列表外的容器或不存在的容器直接拒绝并推送错误通知
- 命令 `/dcfupdate` 与 API `force_update` 的描述同步更新

## v1.2.0 (2026-08-04)

### 新增

- **`/dcfupdate` 远程命令**：跳过 `haveUpdate` 检查，立即强制更新 `autoupdatelist` 全部容器；可加容器名参数只更新某一个，例如 `/dcfupdate cloud-media-sync`
- **`POST /api/v1/plugin/DockerCopilotHelper/force_update` API**：同上效果，body 可选 `{"container_name": "xxx"}`，需要 apikey 鉴权
- 把"单容器更新 + 进度追踪"抽成私有方法 `_do_update`，自动更新和强制更新复用同一套执行流程

### 修复

- 进度追踪超时后仍会多 `time.sleep` 一次才退出循环。改为达到 `intervallimit` 直接 break，不多睡一次
- `remove_image` 成功路径用 `logger.error` 记录（视觉上是红色 ERROR 实际是成功）。改为 `logger.info`
- `__update_config` 整体覆盖隐患：改为只把 `onlyonce` 字段单独写回，保留其他字段不变

## v1.1.2 (2026-08-04)

- 初始本地化版本（与上游市场版一致）