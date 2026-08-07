"""站点魔力值监控插件。"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.triggers.cron import CronTrigger

from app.db.models.site import Site
from app.db.models.siteuserdata import SiteUserData
from app.plugins import _PluginBase
from app.schemas import NotificationType
from app.schemas.types import MessageChannel

# 时魔统计窗口长度（小时）
BONUS_WINDOW_HOURS = 24


def _parse_ts(day: Optional[str], time_str: Optional[str]) -> Optional[datetime]:
    """解析 SiteUserData 的 updated_day + updated_time 字段。"""
    if not day:
        return None
    t = (time_str or "00:00:00").strip() or "00:00:00"
    if t.count(":") == 1:
        t = f"{t}:00"
    try:
        return datetime.strptime(f"{day} {t}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(f"{day} {t}", "%Y-%m-%d %H:%M")
        except ValueError:
            return None


class SiteBonusMonitor(_PluginBase):
    """读取所有启用站点的魔力值、做种数与最近 24 小时时魔。"""

    plugin_name = "站点魔力值监控"
    plugin_desc = "汇总所有启用站点的魔力值、做种数、做种体积与最近 24 小时时魔，支持详情页查看、定时通知与首页 Dashboard 卡片。"
    plugin_icon = "bonus.png"
    plugin_version = "1.0.0"
    plugin_label = "站点"
    plugin_author = "local"
    plugin_config_prefix = "sitebonusmonitor_"
    plugin_order = 30
    auth_level = 1

    # 默认配置：仅启用 + cron
    _enabled = False
    _cron = "0 8 * * *"
    _notify_only_success = True

    def init_plugin(self, config: dict = None) -> None:
        """根据插件配置初始化状态与定时服务。"""
        self.stop_service()
        self._enabled = False
        self._cron = "0 8 * * *"
        if not config:
            return
        self._enabled = bool(config.get("enabled", False))
        self._cron = str(config.get("cron") or "0 8 * * *").strip() or "0 8 * * *"
        self._notify_only_success = bool(config.get("notify_only_success", True))

    def get_state(self) -> bool:
        """返回插件启用状态。"""
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """声明插件远程命令。"""
        return []

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """声明插件使用 Vue 联邦组件渲染。"""
        return "vue", "dist/assets"

    def get_api(self) -> List[Dict[str, Any]]:
        """声明 Vue 前端调用的插件 API。"""
        return [
            {
                "path": "/metrics",
                "endpoint": self.api_metrics,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取所有启用站点的魔力值、做种数与最近 24 小时时魔",
            },
            {
                "path": "/config",
                "endpoint": self.api_get_config,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取当前插件配置",
            },
            {
                "path": "/config",
                "endpoint": self.api_save_config,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "保存插件配置",
            },
            {
                "path": "/test",
                "endpoint": self.api_test_notify,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即发送一条魔力值汇报通知（用于前端调试）",
            },
        ]

    def api_metrics(self) -> Dict[str, Any]:
        """为 Vue 前端返回站点汇总指标。"""
        return {"success": True, "data": self._collect_site_metrics()}

    def api_get_config(self) -> Dict[str, Any]:
        """返回当前插件配置。"""
        return {
            "success": True,
            "data": {
                "enabled": self._enabled,
                "cron": self._cron,
                "notify_only_success": self._notify_only_success,
            },
        }

    def api_save_config(self, payload: Optional[dict] = None) -> Dict[str, Any]:
        """保存前端提交的插件配置。"""
        if not isinstance(payload, dict):
            return {"success": False, "message": "请求体格式错误"}
        current = self.get_config() or {}
        for key in ("enabled", "cron", "notify_only_success"):
            if key in payload:
                current[key] = payload[key]
        self.update_config(current)
        self.init_plugin(current)
        return {"success": True, "data": current}

    def api_test_notify(self) -> Dict[str, Any]:
        """立即触发一次汇报通知（测试用）。"""
        try:
            self._report_job()
            return {"success": True, "message": "已发送测试通知"}
        except Exception as e:
            return {"success": False, "message": f"发送失败: {e}"}

    def get_service(self) -> List[Dict[str, Any]]:
        """注册定时任务，按 cron 推送一次魔力值/时魔汇总。"""
        if not self._enabled or not self._cron:
            return []
        try:
            trigger = CronTrigger.from_crontab(self._cron)
        except Exception as e:
            self.error(f"Cron 表达式解析失败: {self._cron!r} ({e})")
            return []
        return [
            {
                "id": "sitebonusmonitor_report",
                "name": "站点魔力值推送",
                "trigger": trigger,
                "func": self._report_job,
                "kwargs": {},
            }
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """Vue 模式：返回默认配置模型（表单由 Vue Config 组件渲染）。"""
        current = self.get_config() or {}
        default = {
            "enabled": bool(current.get("enabled", False)),
            "cron": str(current.get("cron") or "0 8 * * *"),
            "notify_only_success": bool(current.get("notify_only_success", True)),
        }
        return [], default

    # ----------------------------- 数据 -----------------------------

    @staticmethod
    def _collect_site_metrics(
        window_hours: int = BONUS_WINDOW_HOURS,
    ) -> List[Dict[str, Any]]:
        """汇总所有启用站点的最新用户数据 + 24h 时魔（同步路径，host 直接调用）。"""
        result: List[Dict[str, Any]] = []
        sites = Site.get_actives(None) or []
        if not sites:
            return result

        now = datetime.now()
        window_start = now - timedelta(hours=window_hours)
        sites = sorted(sites, key=lambda s: (s.pri or 0, s.name or ""))

        for site in sites:
            rows = SiteUserData.get_by_domain(None, domain=site.domain) or []
            rows = sorted(
                rows,
                key=lambda r: _parse_ts(r.updated_day, r.updated_time)
                or datetime.min,
            )

            parsed: List[Tuple[datetime, float]] = []
            for row in rows:
                ts = _parse_ts(row.updated_day, row.updated_time)
                if ts is None:
                    continue
                parsed.append((ts, float(row.bonus or 0)))

            anchor_bonus: Optional[float] = None
            anchor_ts: Optional[datetime] = None
            for ts, bonus in parsed:
                if ts <= window_start:
                    anchor_bonus = bonus
                    anchor_ts = ts
                else:
                    break

            in_window = [(ts, bonus) for ts, bonus in parsed if ts >= window_start]
            if not in_window and anchor_ts is None:
                continue

            if not in_window:
                start_ts = anchor_ts
                start_bonus = anchor_bonus
                end_ts = anchor_ts
                end_bonus = anchor_bonus
            else:
                start_ts, start_bonus = in_window[0]
                end_ts, end_bonus = in_window[-1]
                if anchor_ts is not None and anchor_ts < start_ts:
                    start_ts, start_bonus = anchor_ts, anchor_bonus

            hours = max((end_ts - start_ts).total_seconds() / 3600.0, 0.0)
            if hours < (1.0 / 60.0):
                hourly_bonus: Optional[float] = None
            else:
                hourly_bonus = round((end_bonus - start_bonus) / hours, 4)

            latest_row = rows[-1] if rows else None
            result.append(
                {
                    "site_id": site.id,
                    "site_name": site.name,
                    "domain": site.domain,
                    "url": site.url,
                    "username": latest_row.username if latest_row else "",
                    "user_level": latest_row.user_level if latest_row else "",
                    "bonus": end_bonus,
                    "seeding": int(latest_row.seeding or 0) if latest_row else 0,
                    "leeching": int(latest_row.leeching or 0) if latest_row else 0,
                    "upload_gb": round((latest_row.upload or 0) / 1073741824.0, 2) if latest_row else 0.0,
                    "download_gb": round((latest_row.download or 0) / 1073741824.0, 2) if latest_row else 0.0,
                    "ratio": round(latest_row.ratio or 0, 3) if latest_row else 0.0,
                    "seeding_size_gb": round((latest_row.seeding_size or 0) / 1073741824.0, 2)
                    if latest_row
                    else 0.0,
                    "hourly_bonus": hourly_bonus,
                    "window_start": start_ts.strftime("%Y-%m-%d %H:%M:%S"),
                    "window_end": end_ts.strftime("%Y-%m-%d %H:%M:%S"),
                    "window_hours": round(hours, 2),
                    "updated_at": (
                        f"{latest_row.updated_day} {latest_row.updated_time}".strip()
                        if latest_row
                        else ""
                    ),
                    "err_msg": latest_row.err_msg if latest_row and latest_row.err_msg else "",
                }
            )
        return result

    @staticmethod
    def _format_notification(metrics: List[Dict[str, Any]]) -> str:
        """格式化通知文本。"""
        lines = [f"📊 站点魔力值汇报（{datetime.now().strftime('%Y-%m-%d %H:%M')}）"]
        if not metrics:
            lines.append("暂无站点数据")
            return "\n".join(lines)
        valid = [m for m in metrics if m.get("hourly_bonus") is not None]
        valid.sort(key=lambda m: (m.get("hourly_bonus") or 0), reverse=True)
        for m in valid:
            hb = m.get("hourly_bonus") or 0
            sign = "+" if hb >= 0 else ""
            lines.append(
                f"- {m['site_name']}: 魔力 {m['bonus']:.2f} | 做种 {m['seeding']} | 时魔 {sign}{hb:.4f}"
            )
        invalid = [m for m in metrics if m.get("hourly_bonus") is None]
        if invalid:
            names = "、".join(m["site_name"] for m in invalid)
            lines.append(f"⚠️ {names} 24h 内无足够快照，时魔未知")
        return "\n".join(lines)

    # ----------------------------- 详情页 -----------------------------



    def get_page(self) -> List[dict]:
        """Vue 模式下详情页由远程 Page 组件渲染。"""
        return []

    # ----------------------------- Dashboard 卡片 -----------------------------

    def get_dashboard_meta(self) -> Optional[List[Dict[str, str]]]:
        """声明 Dashboard 元信息。"""
        return [
            {"key": "top_bonus", "name": "时魔 Top 站点"},
            {"key": "summary", "name": "站点魔力汇总"},
        ]

    def get_dashboard(self, key: str = "", **kwargs) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], List[dict]]]:
        """Vue 模式：返回 Dashboard 容器布局（实际渲染由 Vue Dashboard 组件接管）。"""
        if not self._enabled:
            return None
        if key == "top_bonus":
            return (
                {"cols": 12, "md": 6},
                {
                    "title": "时魔 Top 站点",
                    "subtitle": "最近 24 小时",
                    "refresh": 60,
                    "border": True,
                },
                [],
            )
        if key == "summary":
            return (
                {"cols": 12, "md": 6},
                {
                    "title": "站点魔力汇总",
                    "subtitle": "汇总所有启用站点",
                    "refresh": 60,
                    "border": True,
                },
                [],
            )
        return None

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        """将插件入口注册到主界面侧栏 discovery 区。"""
        if not self._enabled:
            return []
        return [
            {
                "nav_key": "main",
                "title": "站点魔力值监控",
                "icon": "mdi-trophy-outline",
                "section": "discovery",
                "permission": "manage",
                "order": 22,
            }
        ]

    # ----------------------------- 通知 / 定时任务 -----------------------------

    def _report_job(self) -> None:
        """定时任务入口：汇总站点数据并发送通知。"""
        try:
            metrics = self._collect_site_metrics()
        except Exception as e:
            self.error(f"汇总站点魔力值失败: {e}")
            return

        if self._notify_only_success:
            # 与上次缓存对比，无变化则不通知
            last_payload = self.get_data("last_payload") or ""
            new_payload = json.dumps(metrics, sort_keys=True, ensure_ascii=False, default=str)
            if last_payload == new_payload:
                self.info("站点数据无变化，跳过通知")
                return
            self.save_data("last_payload", new_payload)

        text = self._format_notification(metrics)
        self.post_message(
            mtype=NotificationType.Plugin,
            title="站点魔力值汇报",
            text=text,
        )

    def stop_service(self) -> None:
        """停止插件后台服务并释放资源。"""
        try:
            super().stop_service()
        except Exception:
            pass
