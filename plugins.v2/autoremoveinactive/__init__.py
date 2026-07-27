"""
AutoRemoveInactive - 种子自动删除
自动删除下载器中长时间无活动的种子；如存在其他辅种，仅删种不删文件。
"""
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.helper.downloader import DownloaderHelper
from app.helper.service import ServiceConfigHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.schemas.system import ServiceInfo


class AutoRemoveInactive(_PluginBase):
    """
    种子自动删除。
    自动删除下载器中长时间无活动的种子。
    当同下载器内存在其他文件路径重叠的种子（辅种）时，仅删种不删文件，避免影响其他辅种。
    支持 qBittorrent 与 Transmission。
    """

    plugin_name = "种子自动删除"
    plugin_desc = "自动删除下载器中长时间无活动的种子；存在其他辅种时仅删种不删文件。支持标签过滤（包含/排除）。"
    plugin_icon = "autoremoveinactive.png"
    plugin_version = "1.0.0"
    plugin_label = "下载器"
    author_url = "https://github.com/yuamikami66/MoviePilot-Plugins"
    plugin_author = "jay"
    author_url = "https://github.com/jay/MoviePilot-Plugins"
    plugin_config_prefix = "autoremoveinactive_"
    plugin_order = 30
    auth_level = 1

    # ---------------- 私有属性 ---------------- #
    _enabled: bool = False
    _notify: bool = True
    _notify_channel: str = "插件"
    _cron: str = "*/20 * * * *"
    _downloaders: List[str] = []
    _inactive_minutes: int = 30
    _delete_files_enabled: bool = True
    _delete_file_threshold_minutes: int = 30
    _include_tags: List[str] = []
    _exclude_tags: List[str] = []
    _running: bool = False

    # ---------------- 生命周期 ---------------- #
    def init_plugin(self, config: dict = None) -> None:
        """根据插件配置初始化运行状态。"""
        if not config:
            return
        # 严格 bool 解析：字符串 "false" 必须判为 False（bool("false") == True 是 BUG）
        def to_bool(v, default=False):
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.strip().lower() in ("true", "1", "yes", "on")
            if v is None:
                return default
            return bool(v)

        self._enabled = to_bool(config.get("enabled"))
        self._notify = to_bool(config.get("notify", True))
        # 通知渠道：默认 "插件"，并校验是否在已启用的通知渠道列表里
        notify_channel_raw = (config.get("notify_channel") or "插件").strip()
        valid_channels: List[str] = []
        try:
            for cfg in ServiceConfigHelper.get_notification_configs():
                if getattr(cfg, "enabled", False):
                    valid_channels.append(cfg.name)
        except Exception as err:
            logger.warning(f"AutoRemoveInactive 拉取通知渠道列表失败: {err}")
        if valid_channels and notify_channel_raw not in valid_channels:
            logger.warning(
                f"AutoRemoveInactive 通知渠道 '{notify_channel_raw}' "
                f"不存在或未启用，回退到默认 '插件'"
            )
            self._notify_channel = "插件"
        else:
            self._notify_channel = notify_channel_raw or "插件"
        self._cron = (config.get("cron") or "*/20 * * * *").strip()
        # 兼容 list / dict / 单值 - 插件持久化时可能改变类型
        raw_downloaders = config.get("downloaders")
        if raw_downloaders is None:
            self._downloaders = []
        elif isinstance(raw_downloaders, dict):
            # 形如 {"item": "qb刷流"} - 取所有 string 值
            self._downloaders = [str(v) for v in raw_downloaders.values() if v]
        elif isinstance(raw_downloaders, str):
            self._downloaders = [raw_downloaders]
        else:
            try:
                self._downloaders = [str(x) for x in raw_downloaders if x]
            except TypeError:
                self._downloaders = []
        try:
            self._inactive_minutes = max(1, int(config.get("inactive_minutes") or 30))
        except (TypeError, ValueError):
            self._inactive_minutes = 30
        self._delete_files_enabled = to_bool(config.get("delete_files_enabled", True))
        try:
            self._delete_file_threshold_minutes = max(1, int(
                config.get("delete_file_threshold_minutes") or 30
            ))
        except (TypeError, ValueError):
            self._delete_file_threshold_minutes = 30
        # 标签过滤：换行 / 逗号都支持，解析为 list[str]（去重、去空）
        self._include_tags = self._parse_tag_list(config.get("include_tags"))
        self._exclude_tags = self._parse_tag_list(config.get("exclude_tags"))

        # 修正历史脏数据：前端 form 提交时会把 bool/int 字段保存成字符串，
        # 且 downloaders 会被某层序列化成 {"item": "..."} dict。这里主动 merge 写回标准类型，
        # 让前端 VSwitch/VSelect/VTextField 能正常显示。
        normalized: Dict[str, Any] = {}
        for key in ("enabled", "notify", "delete_files_enabled"):
            raw = config.get(key)
            if isinstance(raw, str):
                normalized[key] = to_bool(raw, default=False)
        if isinstance(raw_downloaders, dict) and self._downloaders:
            normalized["downloaders"] = self._downloaders
        for key, current in (("inactive_minutes", self._inactive_minutes),
                             ("delete_file_threshold_minutes", self._delete_file_threshold_minutes)):
            if isinstance(config.get(key), str) and not isinstance(config.get(key), bool):
                normalized[key] = current
        if normalized:
            try:
                # 注意：self.update_config 是整体覆盖，这里必须 merge 现有 config
                current = self.get_config() or {}
                current.update(normalized)
                self.update_config(current)
                logger.info(
                    f"AutoRemoveInactive 已规范化配置字段: {normalized}"
                )
            except Exception as err:
                logger.warning(f"AutoRemoveInactive 规范化配置失败: {err}")

        if self._enabled and self._downloaders and self._cron:
            logger.info(
                f"AutoRemoveInactive 已启用: cron={self._cron} "
                f"下载器={self._downloaders} 阈值={self._inactive_minutes}分钟"
            )
        elif not self._enabled:
            logger.info("AutoRemoveInactive 未启用")
        elif not self._downloaders:
            logger.info("AutoRemoveInactive 未配置下载器")

    def get_state(self) -> bool:
        """获取插件启用状态。"""
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """返回插件远程命令列表。"""
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        """返回插件 API 列表。"""
        return []

    def get_service(self) -> List[Dict[str, Any]]:
        """注册插件公共服务（由 MoviePilot 调度器管理）。"""
        if not (self._enabled and self._downloaders and self._cron):
            return []
        try:
            trigger = CronTrigger.from_crontab(self._cron, timezone=settings.TZ)
        except Exception as err:
            logger.error(f"AutoRemoveInactive 解析 cron 失败: {err}")
            return []
        return [
            {
                "id": "AutoRemoveInactive",
                "name": "种子自动删除",
                "trigger": trigger,
                "func": self._safe_run,
                "kwargs": {},
            }
        ]

    def get_state(self) -> bool:
        """获取插件启用状态。"""
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """返回插件远程命令列表。"""
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        """返回插件 API 列表。"""
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """返回插件配置表单与默认配置。"""
        downloader_options: List[dict] = []
        try:
            for cfg in DownloaderHelper().get_configs().values():
                downloader_options.append({"title": cfg.name, "value": cfg.name})
        except Exception as err:
            logger.warning(f"AutoRemoveInactive 拉取下载器列表失败: {err}")

        # 通知渠道选项：只列出已启用的渠道
        notify_channel_options: List[dict] = []
        try:
            for cfg in ServiceConfigHelper.get_notification_configs():
                if getattr(cfg, "enabled", False):
                    notify_channel_options.append({"title": cfg.name, "value": cfg.name})
        except Exception as err:
            logger.warning(f"AutoRemoveInactive 拉取通知渠道列表失败: {err}")
        # 兜底：保证下拉框至少有 "插件" 选项
        if not any(opt["value"] == "插件" for opt in notify_channel_options):
            notify_channel_options.append({"title": "插件", "value": "插件"})

        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VSwitch", "props": {
                                    "model": "enabled", "label": "启用插件",
                                }}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VSwitch", "props": {
                                    "model": "notify", "label": "发送通知",
                                }}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VSwitch", "props": {
                                    "model": "onlyonce", "label": "保存后立即运行一次",
                                }}],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [{"component": "VSelect", "props": {
                                    "model": "notify_channel",
                                    "label": "通知渠道",
                                    "items": notify_channel_options,
                                    "hint": "选择发送本插件通知的渠道。仅启用此消息类型开关的渠道可被选中。",
                                    "persistentHint": True,
                                }}],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 7},
                                "content": [{"component": "VSelect", "props": {
                                    "model": "downloaders",
                                    "label": "监控的下载器（多选）",
                                    "multiple": True,
                                    "chips": True,
                                    "items": downloader_options,
                                }}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 5},
                                "content": [{"component": "VTextField", "props": {
                                    "model": "cron",
                                    "label": "定时 Cron（5 位）",
                                    "placeholder": "*/20 * * * *",
                                }}],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VTextField", "props": {
                                    "model": "inactive_minutes",
                                    "label": "删种阈值（分钟）",
                                    "type": "number",
                                    "min": 1,
                                }}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VSwitch", "props": {
                                    "model": "delete_files_enabled",
                                    "label": "无辅种时同时删文件",
                                }}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VTextField", "props": {
                                    "model": "delete_file_threshold_minutes",
                                    "label": "删文件阈值（分钟）",
                                    "type": "number",
                                    "min": 1,
                                }}],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [{"component": "VTextarea", "props": {
                                    "model": "include_tags",
                                    "label": "只处理包含以下标签的种子",
                                    "placeholder": "每行一个标签，或用逗号分隔。留空则处理所有种子。",
                                    "rows": 2,
                                    "noResize": True,
                                    "hint": "支持 qBittorrent 与 Transmission 标签（tr 标签需在 MP 中标记）",
                                    "persistentHint": True,
                                }}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [{"component": "VTextarea", "props": {
                                    "model": "exclude_tags",
                                    "label": "排除含以下标签的种子",
                                    "placeholder": "每行一个标签，或用逗号分隔。",
                                    "rows": 2,
                                    "noResize": True,
                                    "hint": "例如排除 \"重要\" 标签，防止误删需要长期做种的内容",
                                    "persistentHint": True,
                                }}],
                            },
                        ],
                    },
                    {
                        "component": "VAlert",
                        "props": {
                            "type": "info",
                            "variant": "tonal",
                            "text": (
                                "删种阈值：超过此时长无活动的种子会被删除。\n"
                                "无辅种时同时删文件：开启后，会先判断同下载器内是否存在"
                                "其他文件路径重叠的种子（辅种），有则只删种不删文件；"
                                "无则按需同步删文件。\n"
                                "删文件阈值：仅在无辅种时生效。无活动超过此时长才允许删文件，"
                                "防止误删。\n"
                                "标签过滤：先按\"包含标签\"白名单筛种，再按\"排除标签\"黑名单过滤。"
                                "种子命中任一包含标签且不命中任何排除标签才会被处理。"
                            ),
                        },
                    },
                ],
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "notify": True,
            "notify_channel": "插件",
            "cron": "*/20 * * * *",
            "downloaders": [],
            "inactive_minutes": 30,
            "delete_files_enabled": True,
            "delete_file_threshold_minutes": 30,
            "include_tags": "",
            "exclude_tags": "",
        }

    def get_page(self) -> Optional[List[dict]]:
        """返回插件详情页面。"""
        return None

    def stop_service(self) -> None:
        """停止插件后台服务（由 MP 调度器管理，无须手动停止）。"""
        return None

    # ---------------- 执行入口 ---------------- #
    def _safe_run(self) -> None:
        """执行入口，避免重入。"""
        if self._running:
            logger.info("AutoRemoveInactive 已有任务在执行，本次跳过")
            return
        self._running = True
        try:
            self._run_once()
        except Exception as err:
            logger.error(f"AutoRemoveInactive 执行异常: {err}", exc_info=True)
        finally:
            self._running = False

    def _run_once(self) -> None:
        """执行一次清理任务。"""
        helper = DownloaderHelper()
        results: List[Dict[str, Any]] = []
        for name in self._downloaders or []:
            service = helper.get_service(name=name)
            if not service or not service.instance:
                logger.warning(f"AutoRemoveInactive 找不到下载器: {name}")
                results.append({
                    "downloader": name, "deleted_with_file": 0,
                    "deleted_only": 0, "matched": 0,
                    "error": "下载器未配置或不可用",
                })
                continue
            try:
                result = self._process_one(service)
                results.append(result)
            except Exception as err:
                logger.error(f"AutoRemoveInactive 处理 {name} 失败: {err}", exc_info=True)
                results.append({
                    "downloader": name, "deleted_with_file": 0,
                    "deleted_only": 0, "error": str(err),
                })

        # 记录运行统计，供 get_page 详情页展示
        self._record_run_stats(results)

        if self._notify and results:
            self._send_notify(results)

    def _process_one(self, service: ServiceInfo) -> Dict[str, Any]:
        """处理单个下载器。"""
        instance = service.instance
        # 区分 qb / tr
        is_qb = instance.__class__.__name__ == "Qbittorrent"
        is_tr = instance.__class__.__name__ == "Transmission"
        if not (is_qb or is_tr):
            raise RuntimeError(f"不支持的下载器类型: {type(instance).__name__}")

        # 拉种子（qb 返回 (list, errored)，tr 也是 (list, errored)）
        torrents_result = instance.get_torrents()
        if isinstance(torrents_result, tuple):
            torrents = torrents_result[0]
        else:
            torrents = torrents_result or []
        if not torrents:
            return {
                "downloader": service.name, "deleted_with_file": 0,
                "deleted_only": 0, "matched": 0,
                "with_file": [], "only": [],
            }

        now = int(time.time())
        inactive_threshold = now - self._inactive_minutes * 60
        delete_file_threshold = now - self._delete_file_threshold_minutes * 60

        # 拉每个种子的文件
        file_index: Dict[str, Set[str]] = {}
        for t in torrents:
            h = self._get_hash(t, is_qb)
            if not h:
                continue
            try:
                file_index[h] = set(self._get_files(instance, h, is_qb))
            except Exception as err:
                logger.debug(f"AutoRemoveInactive 拉取种子 {h} 文件失败: {err}")
                file_index[h] = set()

        # 判定候选
        del_with_file: List[str] = []
        del_only: List[str] = []
        for t in torrents:
            h = self._get_hash(t, is_qb)
            last_act = self._get_last_activity(t, is_qb)
            if not h or not last_act or last_act > inactive_threshold:
                continue
            # 标签过滤：含/排除标签都没命中时跳过
            if not self._passes_tag_filter(self._get_tags(t, is_qb)):
                continue
            my_files = file_index.get(h, set())
            overlap_hashes: List[str] = []
            if my_files:
                for other_h, other_files in file_index.items():
                    if other_h == h or not other_files:
                        continue
                    if my_files & other_files:
                        overlap_hashes.append(other_h)
            if (
                self._delete_files_enabled
                and not overlap_hashes
                and last_act <= delete_file_threshold
            ):
                del_with_file.append(h)
            else:
                del_only.append(h)

        # 执行删除（一次批量）
        if del_with_file:
            ok = instance.delete_torrents(delete_file=True, ids=del_with_file)
            logger.info(
                f"AutoRemoveInactive [{service.name}] 删种+删文件 {len(del_with_file)} 条: "
                f"{'成功' if ok else '失败'}"
            )
        if del_only:
            ok = instance.delete_torrents(delete_file=False, ids=del_only)
            logger.info(
                f"AutoRemoveInactive [{service.name}] 仅删种 {len(del_only)} 条: "
                f"{'成功' if ok else '失败'}"
            )

        return {
            "downloader": service.name,
            "deleted_with_file": len(del_with_file),
            "deleted_only": len(del_only),
            "matched": len(del_with_file) + len(del_only),
            "with_file": del_with_file,
            "only": del_only,
        }

    # ---------------- 适配层 ---------------- #
    @staticmethod
    def _get_hash(torrent: Any, is_qb: bool) -> str:
        """统一取种子 hash。"""
        if is_qb:
            return str(torrent.get("hash") or "").lower()
        return str(getattr(torrent, "hashString", "") or "").lower()

    @staticmethod
    def _get_last_activity(torrent: Any, is_qb: bool) -> int:
        """统一取最后活跃时间（Unix 秒）。"""
        if is_qb:
            return int(torrent.get("last_activity") or 0)
        # transmission: activity_date 是 UTC 秒级
        val = getattr(torrent, "activity_date", 0) or 0
        try:
            return int(val)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _get_files(instance: Any, torrent_hash: str, is_qb: bool) -> List[str]:
        """统一取种子文件路径列表（相对路径）。"""
        files = instance.get_files(torrent_hash)
        if not files:
            return []
        names: List[str] = []
        for f in files:
            if is_qb:
                # qbittorrentapi.TorrentFilesList 中元素有 .name
                name = getattr(f, "name", None) or (f.get("name") if hasattr(f, "get") else None)
            else:
                # transmission_rpc.File
                name = getattr(f, "name", None)
            if name:
                names.append(str(name))
        return names

    @staticmethod
    def _get_tags(torrent: Any, is_qb: bool) -> List[str]:
        """统一取种子标签列表（已 trim + 去空）。"""
        raw: Any = None
        if is_qb:
            raw = torrent.get("tags") if hasattr(torrent, "get") else None
            # qb 的 tags 是字符串 "a, b, c"，可能为空字符串
        else:
            raw = getattr(torrent, "labels", None) or []
            # tr 的 labels 是 list[str]
        if raw is None:
            return []
        if isinstance(raw, str):
            parts = raw.split(",")
        else:
            try:
                parts = list(raw)
            except TypeError:
                return []
        return [str(p).strip() for p in parts if str(p).strip()]

    @staticmethod
    def _parse_tag_list(value: Any) -> List[str]:
        """从字符串（换行 / 逗号分隔）解析标签列表，去重保留顺序。"""
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            candidates = []
            for item in value:
                candidates.extend(str(item).replace(",", "\n").splitlines())
        else:
            text = str(value)
            candidates = text.replace(",", "\n").splitlines()
        seen: set = set()
        result: List[str] = []
        for item in candidates:
            t = item.strip()
            if t and t not in seen:
                seen.add(t)
                result.append(t)
        return result

    def _passes_tag_filter(self, torrent_tags: List[str]) -> bool:
        """判断种子是否通过标签过滤。"""
        tag_set = set(torrent_tags or [])
        if self._include_tags and not (tag_set & set(self._include_tags)):
            return False
        if self._exclude_tags and (tag_set & set(self._exclude_tags)):
            return False
        return True

    # ---------------- 通知 ---------------- #
    def _send_notify(self, results: List[Dict[str, Any]]) -> None:
        """推送执行结果通知。"""
        total_matched = sum(int(r.get("matched", 0)) for r in results)
        total_deleted = sum(
            int(r.get("deleted_with_file", 0)) + int(r.get("deleted_only", 0))
            for r in results
        )
        if total_deleted == 0:
            return
        text = (
            f"- 匹配待清理种子：{total_matched}条\n"
            f"- 清理种子：{total_deleted} 条"
        )
        try:
            self.post_message(
                mtype=NotificationType.Plugin,
                title="种子自动删除 - 执行完成",
                text=text[:3500],
                source=self._notify_channel,
            )
        except Exception as err:
            logger.error(f"AutoRemoveInactive 发送通知失败: {err}")

    # ---------------- 统计 & 详情页 ---------------- #
    _STATS_KEY = "stats"
    _STATS_RECENT_LIMIT = 20

    def _record_run_stats(self, results: List[Dict[str, Any]]) -> None:
        """累计本次运行的删除数到持久化统计中。"""
        total_with = sum(r.get("deleted_with_file", 0) for r in results)
        total_only = sum(r.get("deleted_only", 0) for r in results)
        total_matched = sum(int(r.get("matched", 0)) for r in results)
        total_deleted = total_with + total_only
        total_files = total_with  # 仅"删种+删文件"路径会同时删文件
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        by_downloader: Dict[str, int] = {}
        by_downloader_files: Dict[str, int] = {}
        for r in results:
            name = r.get("downloader") or "?"
            deleted = int(r.get("deleted_with_file", 0)) + int(r.get("deleted_only", 0))
            files = int(r.get("deleted_with_file", 0))
            by_downloader[name] = by_downloader.get(name, 0) + deleted
            by_downloader_files[name] = by_downloader_files.get(name, 0) + files

        try:
            stats = self.get_data(self._STATS_KEY) or {}
            if not isinstance(stats, dict):
                stats = {}
            stats["total_deleted"] = int(stats.get("total_deleted", 0)) + total_deleted
            stats["total_files_deleted"] = int(stats.get("total_files_deleted", 0)) + total_files
            stats["total_runs"] = int(stats.get("total_runs", 0)) + 1

            merged_dl = dict(stats.get("by_downloader", {}) or {})
            for k, v in by_downloader.items():
                merged_dl[k] = int(merged_dl.get(k, 0)) + v
            stats["by_downloader"] = merged_dl

            merged_files = dict(stats.get("by_downloader_files", {}) or {})
            for k, v in by_downloader_files.items():
                merged_files[k] = int(merged_files.get(k, 0)) + v
            stats["by_downloader_files"] = merged_files

            stats["last_run"] = {
                "timestamp": timestamp,
                "deleted": total_deleted,
                "files_deleted": total_files,
                "matched": total_matched,
                "by_downloader": by_downloader,
            }
            recent = list(stats.get("recent_runs", []) or [])
            recent.append({
                "timestamp": timestamp,
                "deleted": total_deleted,
                "files_deleted": total_files,
                "matched": total_matched,
            })
            stats["recent_runs"] = recent[-self._STATS_RECENT_LIMIT:]

            self.save_data(self._STATS_KEY, stats)
            logger.info(
                f"AutoRemoveInactive 统计已更新: 本次 {total_deleted} 条，"
                f"累计 {stats['total_deleted']} 条 / 删文件 {stats['total_files_deleted']} 次"
            )
        except Exception as err:
            logger.warning(f"AutoRemoveInactive 统计记录失败: {err}")

    @staticmethod
    def get_render_mode() -> Tuple[str, Optional[str]]:
        """声明使用 Vuetify JSON 渲染插件详情页。"""
        return "vuetify", None

    def get_page(self) -> Optional[List[dict]]:
        """返回插件详情页面。"""
        stats: Dict[str, Any] = {}
        try:
            stats = self.get_data(self._STATS_KEY) or {}
        except Exception as err:
            logger.warning(f"AutoRemoveInactive 读取统计失败: {err}")
        if not isinstance(stats, dict):
            stats = {}

        total_deleted = int(stats.get("total_deleted", 0))
        total_files = int(stats.get("total_files_deleted", 0))
        total_runs = int(stats.get("total_runs", 0))
        by_downloader: Dict[str, int] = stats.get("by_downloader", {}) or {}
        by_downloader_files: Dict[str, int] = stats.get("by_downloader_files", {}) or {}
        last_run: Dict[str, Any] = stats.get("last_run", {}) or {}
        recent_runs: List[Dict[str, Any]] = stats.get("recent_runs", []) or []
        cron = (self._cron or "").strip() or "未配置"

        # 下次运行：从 MP 全局 scheduler 查
        next_run_text = "未配置"
        try:
            from app.scheduler import Scheduler
            sched = Scheduler()
            for j in sched.list() or []:
                if getattr(j, "id", "") == "AutoRemoveInactive_AutoRemoveInactive":
                    nr = getattr(j, "next_run", "") or ""
                    if nr:
                        next_run_text = str(nr)
                    break
        except Exception:
            pass

        monitored_count = len(self._downloaders or [])

        def _stat_card(value: Any, label: str, color: str,
                       sublabel: str = "") -> Dict[str, Any]:
            """大数字统计卡。"""
            return {
                "component": "VCard",
                "props": {"variant": "tonal", "color": color, "class": "h-100"},
                "content": [{
                    "component": "VCardText",
                    "props": {"class": "d-flex flex-column align-center justify-center pa-6"},
                    "content": [
                        {"component": "div",
                         "props": {"class": f"text-h2 font-weight-bold text-{color}"},
                         "text": str(value)},
                        {"component": "div",
                         "props": {"class": "text-subtitle-2 text-medium-emphasis mt-1"},
                         "text": label},
                        {"component": "div",
                         "props": {"class": "text-caption text-disabled mt-2"},
                         "text": sublabel} if sublabel else {
                         "component": "div",
                         "props": {"class": "d-none"},
                         "text": ""},
                    ],
                }],
            }

        def _time_card(title: str, icon_color: str, lines: List[Dict[str, str]]) -> Dict[str, Any]:
            return {
                "component": "VCard",
                "props": {"variant": "outlined", "class": "h-100"},
                "content": [
                    {"component": "VCardTitle",
                     "props": {"class": f"text-subtitle-1 font-weight-bold d-flex align-center text-{icon_color}"},
                     "content": [
                         {"component": "VIcon",
                          "props": {"size": "small", "class": "mr-2"},
                          "text": "mdi-clock-outline"},
                         {"component": "span", "text": title},
                     ]},
                    {"component": "VDivider"},
                    {"component": "VCardText",
                     "props": {"class": "pa-4"},
                     "content": lines},
                ],
            }

        def _info_line(klass: str, text: str) -> Dict[str, Any]:
            return {"component": "div", "props": {"class": klass}, "text": text}

        # --- 1. 顶部 4 个大数字卡 ---
        stat_cards = [
            _stat_card(total_deleted, "累计删除种子", "primary",
                       f"覆盖 {len(by_downloader)} 个下载器" if by_downloader else "尚无数据"),
            _stat_card(total_files, "同步删除文件", "error",
                       "仅统计无辅种时的实际删文件数"),
            _stat_card(total_runs, "运行次数", "info",
                       f"定时 {cron}"),
            _stat_card(monitored_count, "监控下载器", "success",
                       "、".join(self._downloaders) if self._downloaders else "未配置"),
        ]

        # --- 2. 上次 / 下次运行卡 ---
        if last_run.get("timestamp"):
            last_text = last_run["timestamp"]
            last_delta = self._humanize_delta(last_run["timestamp"])
            last_stats_text = (
                f"删种 {last_run.get('deleted', 0)} 条"
                f" / 删文件 {last_run.get('files_deleted', 0)} 条"
            )
            last_content = [
                _info_line("text-h4 font-weight-medium", last_text),
                _info_line("text-caption text-medium-emphasis mt-1", last_delta),
                _info_line("text-body-2 text-primary mt-3", last_stats_text),
            ]
        else:
            last_content = [
                _info_line("text-body-1 text-medium-emphasis", "暂无运行记录"),
            ]
        last_card = _time_card("上次运行", "info", last_content)

        next_content = [
            _info_line("text-h4 font-weight-medium text-success", next_run_text),
            _info_line("text-caption text-medium-emphasis mt-1", f"Cron: {cron}"),
        ]
        next_card = _time_card("下次运行", "success", next_content)

        # --- 3. 各下载器分布 ---
        if by_downloader:
            sorted_dl = sorted(by_downloader.items(), key=lambda x: x[1], reverse=True)
            total_for_bar = max(total_deleted, 1)
            list_items: List[Dict[str, Any]] = []
            for name, count in sorted_dl:
                pct = round(count * 100.0 / total_for_bar, 1)
                files = int(by_downloader_files.get(name, 0))
                list_items.append({
                    "component": "VListItem",
                    "props": {"class": "px-2"},
                    "content": [
                        {"component": "VListItemTitle",
                         "props": {"class": "d-flex align-center justify-space-between"},
                         "content": [
                             {"component": "span",
                              "props": {"class": "text-body-1 font-weight-medium"},
                              "text": name},
                             {"component": "div",
                              "content": [
                                  {"component": "VChip",
                                   "props": {"size": "small", "color": "primary",
                                             "variant": "tonal", "class": "mr-2"},
                                   "text": f"删种 {count}"},
                                  {"component": "VChip",
                                   "props": {"size": "small", "color": "error",
                                             "variant": "tonal"},
                                   "text": f"删文件 {files}"},
                              ]},
                         ]},
                        {"component": "VListItemSubtitle",
                         "props": {"class": "mt-2"},
                         "content": [
                             {"component": "VProgressLinear",
                              "props": {"modelValue": pct, "color": "primary",
                                        "height": 6, "rounded": True,
                                        "class": "mt-1"},
                              "text": f"{pct}%"},
                         ]},
                    ],
                })
            downloader_block = {
                "component": "VCard",
                "props": {"variant": "outlined"},
                "content": [
                    {"component": "VCardTitle",
                     "props": {"class": "text-subtitle-1 font-weight-bold d-flex align-center"},
                     "content": [
                         {"component": "VIcon",
                          "props": {"size": "small", "class": "mr-2 text-warning"},
                          "text": "mdi-server-network"},
                         {"component": "span", "text": "各下载器分布"},
                     ]},
                    {"component": "VDivider"},
                    {"component": "VList",
                     "props": {"lines": "three", "density": "comfortable"},
                     "content": list_items},
                ],
            }
        else:
            downloader_block = {
                "component": "VCard",
                "props": {"variant": "outlined"},
                "content": [
                    {"component": "VCardTitle",
                     "props": {"class": "text-subtitle-1 font-weight-bold"},
                     "text": "各下载器分布"},
                    {"component": "VCardText",
                     "props": {"class": "text-center text-medium-emphasis py-8"},
                     "text": "插件尚未实际删除过种子，运行后将在此展示分布"},
                ],
            }

        # --- 4. 最近运行记录 ---
        if recent_runs:
            rows = []
            for r in reversed(recent_runs[-10:]):
                rows.append({
                    "component": "tr",
                    "content": [
                        {"component": "td",
                         "props": {"class": "text-body-2"},
                         "text": r.get("timestamp", "")},
                        {"component": "td",
                         "props": {"class": "text-right"},
                         "content": [
                             {"component": "VChip",
                              "props": {"size": "small", "color": "primary",
                                        "variant": "tonal"},
                              "text": f"{r.get('deleted', 0)}"},
                         ]},
                        {"component": "td",
                         "props": {"class": "text-right"},
                         "content": [
                             {"component": "VChip",
                              "props": {"size": "small", "color": "error",
                                        "variant": "tonal"},
                              "text": f"{r.get('files_deleted', 0)}"},
                         ]},
                    ],
                })
            recent_block = {
                "component": "VCard",
                "props": {"variant": "outlined"},
                "content": [
                    {"component": "VCardTitle",
                     "props": {"class": "text-subtitle-1 font-weight-bold d-flex align-center"},
                     "content": [
                         {"component": "VIcon",
                          "props": {"size": "small", "class": "mr-2 text-info"},
                          "text": "mdi-history"},
                         {"component": "span", "text": f"最近运行记录（最近 {len(rows)} 次）"},
                     ]},
                    {"component": "VDivider"},
                    {"component": "VTable",
                     "props": {"density": "comfortable"},
                     "content": [
                         {"component": "thead",
                          "content": [
                              {"component": "tr",
                               "content": [
                                   {"component": "th",
                                    "props": {"class": "text-left"},
                                    "text": "时间"},
                                   {"component": "th",
                                    "props": {"class": "text-right"},
                                    "text": "删种"},
                                   {"component": "th",
                                    "props": {"class": "text-right"},
                                    "text": "删文件"},
                               ]},
                          ]},
                         {"component": "tbody", "content": rows},
                     ]},
                ],
            }
        else:
            recent_block = {
                "component": "VCard",
                "props": {"variant": "outlined"},
                "content": [
                    {"component": "VCardTitle",
                     "props": {"class": "text-subtitle-1 font-weight-bold"},
                     "text": "最近运行记录"},
                    {"component": "VCardText",
                     "props": {"class": "text-center text-medium-emphasis py-8"},
                     "text": "暂无数据"},
                ],
            }

        # --- 拼装最终页面 ---
        return [{
            "component": "VContainer",
            "props": {"class": "pa-4", "fluid": True},
            "content": [
                # 顶部 4 个统计卡
                {"component": "VRow",
                 "props": {"dense": True},
                 "content": [
                    {"component": "VCol", "props": {"cols": 6, "md": 3},
                     "content": [stat_cards[0]]},
                    {"component": "VCol", "props": {"cols": 6, "md": 3},
                     "content": [stat_cards[1]]},
                    {"component": "VCol", "props": {"cols": 6, "md": 3},
                     "content": [stat_cards[2]]},
                    {"component": "VCol", "props": {"cols": 6, "md": 3},
                     "content": [stat_cards[3]]},
                 ]},
                # 上次/下次时间卡
                {"component": "VRow",
                 "props": {"class": "mt-2", "dense": True},
                 "content": [
                    {"component": "VCol", "props": {"cols": 12, "md": 6},
                     "content": [last_card]},
                    {"component": "VCol", "props": {"cols": 12, "md": 6},
                     "content": [next_card]},
                 ]},
                # 各下载器分布
                {"component": "VRow",
                 "props": {"class": "mt-2", "dense": True},
                 "content": [
                    {"component": "VCol", "props": {"cols": 12},
                     "content": [downloader_block]},
                 ]},
                # 最近运行记录
                {"component": "VRow",
                 "props": {"class": "mt-2", "dense": True},
                 "content": [
                    {"component": "VCol", "props": {"cols": 12},
                     "content": [recent_block]},
                 ]},
            ],
        }]

    @staticmethod
    def _humanize_delta(ts_str: str) -> str:
        """把 'YYYY-MM-DD HH:MM:SS' 转成 'X 分钟前'。"""
        try:
            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            delta = datetime.now() - ts
            seconds = int(delta.total_seconds())
            if seconds < 0:
                return "刚刚"
            if seconds < 60:
                return f"{seconds} 秒前"
            if seconds < 3600:
                return f"{seconds // 60} 分钟前"
            if seconds < 86400:
                return f"{seconds // 3600} 小时前"
            return f"{seconds // 86400} 天前"
        except Exception:
            return ""
