# MoviePilot-Plugins

MoviePilot 自有插件仓库。通过 MoviePilot 的 `设置 -> 插件 -> 插件市场` 将本仓库地址加入 `PLUGIN_MARKET` 即可搜索安装。

## 插件列表

| 插件 ID | 名称 | 版本 | 简介 |
| --- | --- | --- | --- |
| [AutoRemoveInactive](./plugins.v2/autoremoveinactive) | 种子自动删除 | 1.0.0 | 自动删除下载器中长时间无活动的种子；存在其他辅种时仅删种不删文件 |

## 安装

在 MoviePilot 的 **设置 -> 插件 -> 插件市场** 中，将本仓库地址加入 `PLUGIN_MARKET`：

```
https://github.com/yuamikami66/MoviePilot-Plugins/
```

保存后即可在插件市场搜索并安装仓库内的插件。

## 插件开发约定

- 插件源码统一放在 `plugins.v2/<plugin_id>/` 目录下（小写 ID）。
- 插件元数据统一维护在根目录的 `package.v2.json` 中。
- 插件版本遵循 [语义化版本](https://semver.org/lang/zh-CN/)；发布新版本时同步更新 `package.v2.json` 的 `version` 字段和 `history` 字典。
