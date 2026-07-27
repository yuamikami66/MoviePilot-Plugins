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
    plugin_desc = "自动删除下载器中长时间无活动的种子，存在其他辅种时仅删种不删文件"
    plugin_icon = "cleanup.png"
    plugin_version = "1.0.0"
    plugin_author = "jay"
    author_url = "https://github.com/jay/MoviePilot-Plugins"
    plugin_config_prefix = "autoremoveinactive_"
    plugin_order = 30
    auth_level = 1

    # ---------------- 私有属性 ---------------- #
    _enabled: bool = False
    _notify: bool = True
    _cron: str = "*/20 * * * *"
    _downloaders: List[str] = []
    _inactive_minutes: int = 30
    _delete_files_enabled: bool = True
    _delete_file_threshold_minutes: int = 30
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
                                "防止误删。"
                            ),
                        },
                    },
                ],
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "notify": True,
            "cron": "*/20 * * * *",
            "downloaders": [],
            "inactive_minutes": 30,
            "delete_files_enabled": True,
            "delete_file_threshold_minutes": 30,
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
                    "deleted_only": 0, "error": "下载器未配置或不可用",
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
                "deleted_only": 0, "with_file": [], "only": [],
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

    # ---------------- 通知 ---------------- #
    def _send_notify(self, results: List[Dict[str, Any]]) -> None:
        """推送执行结果通知。"""
        total_with = sum(r.get("deleted_with_file", 0) for r in results)
        total_only = sum(r.get("deleted_only", 0) for r in results)
        if total_with == 0 and total_only == 0:
            return
        lines = [
            f"匹配阈值：删种 ≥ {self._inactive_minutes} 分钟无活动，"
            f"删文件 ≥ {self._delete_file_threshold_minutes} 分钟无活动"
            f"{'且无其他辅种' if self._delete_files_enabled else '（保留文件）'}",
            f"汇总：删种+删文件 {total_with} 条 / 仅删种 {total_only} 条",
            "",
        ]
        for r in results:
            if r.get("error"):
                lines.append(f"- {r['downloader']}: ⚠ {r['error']}")
                continue
            dwf = r.get("deleted_with_file", 0)
            do = r.get("deleted_only", 0)
            if dwf == 0 and do == 0:
                continue
            lines.append(
                f"- {r['downloader']}：删种+删文件 {dwf} 条，仅删种 {do} 条"
            )
        text = "\n".join(lines)
        try:
            self.post_message(
                mtype=NotificationType.Plugin,
                title=f"种子自动删除 共 {total_with + total_only} 条",
                text=text[:3500],
            )
        except Exception as err:
            logger.error(f"AutoRemoveInactive 发送通知失败: {err}")
