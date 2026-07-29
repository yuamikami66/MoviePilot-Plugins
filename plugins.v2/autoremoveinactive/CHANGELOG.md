# 更新日志 / Changelog

本插件所有版本变更记录。日期为发布日（按本地时区）。

## v1.2.0 (2026-07-29)

### 视觉与体验

- **配置页 UI 重设计**：把 4 个独立 VRow 改为 5 个 VCard 分组（基础设置 / 调度与下载器 / 无活动清理 / Tracker 失联立即删除 / 标签过滤），每组统一标题 + 图标 + 副标题样式，12 列栅格对齐
- 每组 VCardTitle 加语义化图标：`mdi-cog-outline` / `mdi-calendar-clock` / `mdi-clock-alert-outline` / `mdi-link-off` / `mdi-tag-multiple-outline`
- 字段统一加 `prependInnerIcon`（定时、计时器、文件时钟、标签勾选/移除），全局 `density="comfortable"`
- 长说明改为内联 `VAlert density="compact"`，不再占整行
- 表单底部加 1 个总说明 VAlert：执行流程 / 辅种规则 / 标签过滤规则

## v1.1.1 (2026-07-29)

### 调整

- **标签过滤配置合并**：Tracker 失联清理改为复用无活动清理的 `include_tags` / `exclude_tags` 白/黑名单；去除冗余的 `delete_dead_trackers_include_tags` / `delete_dead_trackers_exclude_tags` 独立配置项
- 详情页顶部 5 个统计卡文案微调："同步删除文件" → "删除文件"，"失联立即删种" → "tracker 失联删种"

## v1.1.0 (2026-07-29)

### 新增

- **Tracker 失联立即删除功能**：每次定时扫描拉取每个种子的 tracker 状态，所有 tracker 都失联时跳过时间阈值立即执行删除
  - qBittorrent：所有 tracker `status != 2(Working)` 且 `!= 3(Updating)` 视为失联
  - Transmission：所有 tracker `last_announce_succeeded=False` 且 `last_announce_result != 'Success'` 视为失联
  - 空 tracker 列表视为无 tracker 目标，跳过
- 无辅种时可选择是否同步删文件（默认只删种，最安全）
- 通知文案增加"tracker 失联清理"分项
- 统计与详情页增加失联删种/失联删文件计数（顶部 5 个统计卡 + 各下载器 chip + 最近运行表新增 2 列）
- 复用现有"辅种文件 overlap 判定"：有辅种只删种

## v1.0.0 (2026-07-28)

### 新增

- **种子自动删除核心功能**：自动删除下载器中长时间无活动的种子
- 跨下载器多实例支持（qBittorrent + Transmission）
- 辅种文件 overlap 判定：同下载器内若存在其他文件路径重叠的种子，则只删种不删文件
- 标签白名单 / 黑名单过滤（换行 / 逗号均支持）
- 删种阈值 / 删文件阈值 分离配置
- "无辅种时同时删文件"开关
- 自定义扫描周期（5 位 Cron）
- 通知系统：执行完成后发送 Plugin 类型通知
- "通知渠道"配置项：可显式指定本插件的通知接收渠道
- 详情统计页：累计删种 / 删文件 / 运行次数 / 监控下载器 / 上次运行 / 下次运行 / 各下载器分布 / 最近运行记录
- 数据持久化：所有统计存到 plugin data，重启后保留
