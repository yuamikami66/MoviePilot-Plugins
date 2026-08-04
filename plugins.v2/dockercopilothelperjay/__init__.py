from datetime import datetime, timedelta

from typing import Optional, Any, List, Dict, Tuple
import time
import pytz
import jwt
import requests
from requests import Session, Response
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.core.event import eventmanager, Event

from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType
from app.utils.http import RequestUtils


class DockerCopilotHelperJay(_PluginBase):
    # 插件名称
    plugin_name = "DC助手+"
    # 插件描述
    plugin_desc = "配合DockerCopilot,完成更新通知、自动更改、自动备份功能"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/yuamikami66/MoviePilot-Plugins/main/plugins/DockerCopilotHelperJay/Docker_Copilot.png"
    # 插件版本
    plugin_version = "1.5.0"
    # 插件作者
    plugin_author = "yuamikami66"
    # 作者主页
    author_url = "https://github.com/yuamikami66/MoviePilot-Plugins"
    # 插件配置项ID前缀
    plugin_config_prefix = "dockercopilothelperjay_"
    # 加载顺序
    plugin_order = 15
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _onlyonce = False
    # 可用更新
    _update_cron = None
    _updatable_list = []
    _updatable_notify = False
    _schedule_report = False
    # 自动更新
    _auto_update_cron = None
    _auto_update_list = []
    _auto_update_notify = False
    _delete_images = False
    # 强制更新
    _force_update_list = []
    _last_force_update_list: List[str] = []  # 上次保存的 forceupdatelist，用于检测用户新选择
    _pending_force_targets: List[str] = []  # 保存时快照的强制更新目标
    _intervallimit = None
    _interval = None
    # 备份
    _backup_cron = None
    _backups_notify = False
    _host = None
    _secretKey = None
    _scheduler: Optional[BackgroundScheduler] = None

    def init_plugin(self, config: dict = None):
        # 停止现有任务
        self.stop_service()
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._update_cron = config.get("updatecron")
            self._updatable_list = self._normalize_list(config.get("updatablelist"))
            self._updatable_notify = config.get("updatablenotify")
            self._auto_update_cron = config.get("autoupdatecron")
            self._auto_update_list = self._normalize_list(config.get("autoupdatelist"))
            self._auto_update_notify = config.get("autoupdatenotify")
            self._schedule_report = config.get("schedulereport")
            new_force_list = self._normalize_list(config.get("forceupdatelist"))
            self._force_update_list = new_force_list
            self._delete_images = config.get("deleteimages")
            self._backup_cron = config.get("backupcron")
            self._backups_notify = config.get("backupsnotify")
            self._intervallimit = config.get("intervallimit") or 6
            self._interval = config.get("interval") or 10

            self._host = config.get("host")
            self._secretKey = config.get("secretKey")

            # 获取DC列表数据
            if not self._secretKey or not self._host:
                logger.error(f"DC助手服务结束 secretKey或host未填写")
                return False

            # 加载模块
            if self._enabled or self._onlyonce:
                # 定时服务
                self._scheduler = BackgroundScheduler(timezone=settings.TZ)
                # 检测到 forceupdatelist 新配置（非空且与上次不同），调度一次强制更新后清空
                self._maybe_schedule_force_update(config, new_force_list)
                # 立即运行一次
                if self._onlyonce:
                    logger.info(f"DC助手服务启动，立即运行一次")
                    if self._backup_cron:
                        self._scheduler.add_job(self.backup, 'date',
                                                run_date=datetime.now(
                                                    tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                                                name="DC助手-备份")
                    if self._update_cron:
                        self._scheduler.add_job(self.updatable, 'date',
                                                run_date=datetime.now(
                                                    tz=pytz.timezone(settings.TZ)) + timedelta(seconds=6),
                                                name="DC助手-自动更新")
                    if self._auto_update_cron:
                        self._scheduler.add_job(self.auto_update, 'date',
                                                run_date=datetime.now(
                                                    tz=pytz.timezone(settings.TZ)) + timedelta(seconds=10),
                                                name="DC助手-更新通知")
                    # 关闭一次性开关
                    self._onlyonce = False
                    # 保存配置
                    self.__update_config()
                # 周期运行
                if self._backup_cron:
                    try:
                        self._scheduler.add_job(func=self.backup,
                                                trigger=CronTrigger.from_crontab(self._backup_cron),
                                                name="DC助手-备份")
                    except Exception as err:
                        logger.error(f"定时任务配置错误：{str(err)}")
                        # 推送实时消息
                        self.systemmessage.put(f"执行周期配置错误：{err}")
                if self._update_cron:
                    try:
                        self._scheduler.add_job(func=self.updatable,
                                                trigger=CronTrigger.from_crontab(self._update_cron),
                                                name="DC助手-更新通知")
                    except Exception as err:
                        logger.error(f"定时任务配置错误：{str(err)}")
                        # 推送实时消息
                        self.systemmessage.put(f"执行周期配置错误：{err}")
                if self._auto_update_cron:
                    try:
                        self._scheduler.add_job(func=self.auto_update,
                                                trigger=CronTrigger.from_crontab(self._auto_update_cron),
                                                name="DC助手-自动更新")
                    except Exception as err:
                        logger.error(f"定时任务配置错误：{str(err)}")
                        # 推送实时消息
                        self.systemmessage.put(f"执行周期配置错误：{err}")
                # 启动任务
                if self._scheduler.get_jobs():
                    self._scheduler.print_jobs()
                    self._scheduler.start()


    def get_state(self) -> bool:
        return self._enabled

    # def clear_checkbox(self):
    #         self.update_config(
    #             {
    #                 "autoupdatelist":[],
    #                 "updatablelist":[]
    #             }
    #     )

    def __update_config(self):
        """
        写回 onlyonce 字段。

        注意：_PluginBase.update_config 旧实现是整体 set（不是 merge），
        只传部分字段会清空其他字段。因此这里使用"读出现有配置 + 合并 onlyonce + 整体写回"的方式，
        保证其他运行时未修改的字段不被丢失。
        """
        current = self.get_config() or {}
        current["onlyonce"] = self._onlyonce
        self.update_config(current)

    @staticmethod
    def _normalize_list(value: Any) -> List[str]:
        """
        规整 MP update_plugin_config 工具产生的 list 序列化怪格式 / None / 单值 等为标准 list[str]。
        支持以下格式：
        - None / 空字符串 -> []
        - "xxx" -> ["xxx"]
        - ["a", "b"] -> ["a", "b"]
        - {"item": [...]} -> [...]（旧版序列化格式）
        - [["a", "b"]] -> ["a", "b"]（新版工具嵌套数组 bug）
        """
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, dict):
            inner = value.get("item") if isinstance(value.get("item"), list) else None
            if inner is None:
                return []
            return [str(x) for x in inner if x]
        if isinstance(value, (list, tuple, set)):
            flat: List[str] = []
            for x in value:
                if x is None or x == "":
                    continue
                if isinstance(x, (list, tuple, set)):
                    # 嵌套数组：递归展平一层
                    flat.extend(DockerCopilotHelperJay._normalize_list(list(x)))
                elif isinstance(x, dict):
                    inner = x.get("item") if isinstance(x.get("item"), list) else None
                    if inner is not None:
                        flat.extend([str(v) for v in inner if v])
                else:
                    flat.append(str(x))
            return flat
        return []

    def _maybe_schedule_force_update(self, config: dict, new_force_list: List[str]):
        """
        检测 forceupdatelist 是否是"用户新配置"（之前为空/不同，本次非空），
        若是，调度一次 3 秒后的强制更新任务，并立即把 forceupdatelist 清空写回 DB。

        设计目的：用户在前端勾选容器 → 保存 → 后端立即触发一次强制更新（严格模式作用于这些容器）
        → 清空选项，避免下次 reload 或别的 cron 误重复触发；下次想再强更必须重新选。
        """
        if not new_force_list:
            return
        if not self._enabled and not self._onlyonce:
            return
        if not self._scheduler:
            return
        prev_force_list = self._normalize_list(config.get("__last_force_update_list"))
        if list(prev_force_list) == list(new_force_list):
            return
        logger.info(f"DC助手-检测到 forceupdatelist 变更: {prev_force_list} -> {new_force_list}，调度强制更新")
        # 把当前 force_list 暂存到私有属性，供 force_update 内部使用
        self._pending_force_targets = list(new_force_list)
        # 调度异步触发
        run_at = datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3)
        self._scheduler.add_job(
            self._trigger_pending_force_update,
            'date',
            run_date=run_at,
            name="DC助手-用户触发强制更新"
        )
        # 立即把 forceupdatelist 清空写回（用保存当前内存值的方式避免误清掉其他字段）
        try:
            current = self.get_config() or {}
            current["forceupdatelist"] = []
            self.update_config(current)
            logger.info("DC助手-forceupdatelist 已在调度后清空，下次需重新选择才会触发")
        except Exception as e:
            logger.error(f"DC助手-forceupdatelist 清空失败: {e}")

    def _trigger_pending_force_update(self):
        """
        实际跑一次强制更新，针对 _pending_force_targets（保存时的快照）。
        """
        targets = getattr(self, "_pending_force_targets", []) or []
        # 用完后清掉，防止重跑
        self._pending_force_targets = []
        if not targets:
            logger.info("DC助手-强制更新触发-无目标，跳过")
            return
        logger.info(f"DC助手-用户触发强制更新-目标: {targets}")
        # 直接遍历 targets 走 _do_update，跳过 force_update 的 forceupdatelist 校验
        if not self._host or not self._secretKey:
            logger.error("DC助手-用户触发强制更新-失败: host 或 secretKey 未配置")
            self.post_message(
                mtype=NotificationType.Plugin,
                title="【DC助手-强制更新】",
                text="host 或 secretKey 未配置，请先在插件设置中填写"
            )
            return
        # 临时把 _force_update_list 设为 targets，force_update 直接用 self._force_update_list
        original_list = self._force_update_list
        self._force_update_list = list(targets)
        try:
            self.force_update()
        finally:
            self._force_update_list = original_list

    def auto_update(self):
        """
        自动更新
        """
        logger.info("DC助手-自动更新-准备执行")
        if self._auto_update_cron:
            # 获取用户选择的容器 循环更新
            jwt = self.get_jwt()
            containers = self.get_docker_list()
            # 清理无标签 and 不在使用种的镜像
            if self._delete_images:
                images_list = self.get_images_list()
                for images in images_list:
                    if not images["inUsed"] and images["tag"]:
                        self.remove_image(images["id"])
            # 自动更新
            for name in self._auto_update_list:
                for container in containers:
                    if container["name"] == name and container["haveUpdate"]:
                        self._do_update(name, container, jwt, source="自动更新")

    def force_update(self, container_name: Optional[str] = None):
        """
        强制更新：跳过 haveUpdate 检查，对 forceupdatelist 中明确列出的容器立即执行一次更新任务。

        严格模式：仅当目标容器在 forceupdatelist 中时才执行；列表外或不存在的容器直接拒绝并通知。
        :param container_name: 指定容器名；为 None 时遍历 forceupdatelist
        """
        logger.info(f"DC助手-强制更新-开始 container_name={container_name}")
        if not self._host or not self._secretKey:
            logger.error("DC助手-强制更新-失败: host 或 secretKey 未配置")
            self.post_message(
                mtype=NotificationType.Plugin,
                title="【DC助手-强制更新】",
                text="host 或 secretKey 未配置，请先在插件设置中填写"
            )
            return
        force_list = list(self._force_update_list or [])
        if not force_list:
            self.post_message(
                mtype=NotificationType.Plugin,
                title="【DC助手-强制更新】",
                text="forceupdatelist 为空，未配置可强制更新的容器，跳过"
            )
            return
        # 决定要更新的目标列表
        if container_name:
            if container_name not in force_list:
                self.post_message(
                    mtype=NotificationType.Plugin,
                    title="【DC助手-强制更新】",
                    text=f"容器【{container_name}】不在 forceupdatelist 中，已拒绝执行强制更新"
                )
                return
            targets = [container_name]
        else:
            targets = list(force_list)
        jwt = self.get_jwt()
        containers = self.get_docker_list()
        if not containers:
            self.post_message(
                mtype=NotificationType.Plugin,
                title="【DC助手-强制更新】",
                text="获取容器列表失败，请检查 DockerCopilot 服务是否正常"
            )
            return
        # 强制更新前清理无用镜像（如果开启了）
        if self._delete_images:
            images_list = self.get_images_list()
            for images in images_list:
                if not images["inUsed"] and images["tag"]:
                    self.remove_image(images["id"])
        # 逐个强制更新
        for name in targets:
            target_container = None
            for c in containers:
                if c.get("name") == name:
                    target_container = c
                    break
            if not target_container:
                self.post_message(
                    mtype=NotificationType.Plugin,
                    title="【DC助手-强制更新】",
                    text=f"未找到容器【{name}】，跳过"
                )
                continue
            self._do_update(name, target_container, jwt, source="强制更新")

    def _do_update(self, name: str, container: Dict[str, Any], jwt: str, source: str = "自动更新"):
        """
        实际执行一次单容器更新 + 进度追踪
        :param name: 容器名
        :param container: 容器信息 dict
        :param jwt: 鉴权 token
        :param source: 触发来源，用于通知标题
        """
        old_image = container.get("usingImage", "")
        if not old_image or old_image.startswith("sha256:"):
            self.post_message(
                mtype=NotificationType.Plugin,
                title=f"【DC助手-{source}】",
                text=f"监测到您有容器TAG不正确\n【{container['name']}】\n当前镜像:{old_image}\n状态:{container['status']} "
                     f"{container['runningTime']}\n构建时间：{container['createTime']}\n"
                     f"该镜像无法通过DC自动更新,请修改TAG")
            return
        url = '%s/api/container/%s/update' % (self._host, container['id'])
        usingImage = {old_image}
        try:
            rescanres = (RequestUtils(headers={"Authorization": jwt})
                         .post_res(url, {"containerName": name, "imageNameAndTag": usingImage}))
            data = rescanres.json()
        except Exception as e:
            logger.error(f"DC助手-{source}-请求失败 {name}: {e}")
            self.post_message(
                mtype=NotificationType.Plugin,
                title=f"【DC助手-{source}】",
                text=f"【{name}】\n请求 DockerCopilot 失败：{e}"
            )
            return
        if data.get("code") == 200 and data.get("msg") == "success":
            self.post_message(
                mtype=NotificationType.Plugin,
                title=f"【DC助手-{source}】",
                text=f"【{name}】\n容器更新任务创建成功\n旧镜像：{old_image}")
            if self._schedule_report and data.get("data", {}).get("taskID"):
                iteration = 0
                limit = int(self._intervallimit)
                update_succeeded = False
                while iteration < limit:
                    iteration += 1
                    url = '%s/api/progress/%s' % (self._host, data["data"]["taskID"])
                    try:
                        rescanres = (RequestUtils(headers={"Authorization": jwt})
                                     .get_res(url))
                        report_json = rescanres.json()
                    except Exception as e:
                        logger.error(f"DC助手-{source}-进度查询失败 {name}: {e}")
                        break
                    if report_json.get("code") == 200:
                        self.post_message(
                            mtype=NotificationType.Plugin,
                            title="【DC助手-更新进度】",
                            text=f"【{name}】\n进度：{report_json.get('msg')}"
                        )
                        if report_json.get("msg") == "更新成功":
                            update_succeeded = True
                            break
                    if iteration >= limit:
                        logger.info(f'DC助手-更新进度追踪--{name}-超时')
                        break
                    time.sleep(int(self._interval))
                # 更新成功后再次查询容器列表，拿新镜像对比
                if update_succeeded:
                    new_image = self._fetch_container_image(jwt, name)
                    self._post_update_summary(name, source, old_image, new_image)
        else:
            self.post_message(
                mtype=NotificationType.Plugin,
                title=f"【DC助手-{source}】",
                text=f"【{name}】\n更新任务创建失败\n错误码：{data.get('code')}\n原因：{data.get('msg')}"
            )
            logger.error(f"DC助手-{source}-创建任务失败 {name}: code={data.get('code')}, msg={data.get('msg')}")

    def _fetch_container_image(self, jwt: str, container_name: str) -> str:
        """
        通过 /api/containers 重新查询指定容器的当前镜像。
        用于更新成功后对比新旧镜像版本。
        """
        try:
            containers = self.get_docker_list()
            for c in containers:
                if c.get("name") == container_name:
                    return c.get("usingImage", "") or ""
        except Exception as e:
            logger.error(f"DC助手-获取新镜像失败 {container_name}: {e}")
        return ""

    def _post_update_summary(self, name: str, source: str, old_image: str, new_image: str):
        """
        推送更新成功汇总通知：展示旧镜像 -> 新镜像 的对比。
        :param name: 容器名
        :param source: 触发来源
        :param old_image: 更新前 usingImage
        :param new_image: 更新后 usingImage（取不到时为空字符串）
        """
        if not new_image:
            text = (f"【{name}】\n更新成功\n"
                    f"旧镜像：{old_image}\n"
                    f"新镜像：未能获取，请到 DockerCopilot 查看")
        elif new_image == old_image:
            text = (f"【{name}】\n更新成功\n"
                    f"旧镜像：{old_image}\n"
                    f"新镜像：{new_image}\n"
                    f"⚠️ 镜像 tag 未变（可能使用 latest 等浮动 tag），建议到 DockerCopilot 或 registry 核对实际版本")
        else:
            text = (f"【{name}】\n更新成功\n"
                    f"旧镜像：{old_image}\n"
                    f"新镜像：{new_image}")
        self.post_message(
            mtype=NotificationType.Plugin,
            title=f"【DC助手-{source}】",
            text=text
        )

    def updatable(self):
        """
        更新通知
        """
        logger.info("DC助手-更新通知-准备执行")
        if self._update_cron:
            docker_list = self.get_docker_list()
            logger.debug(f"DC助手-更新通知-{self._updatable_list}")
            for docker in docker_list:
                if docker["haveUpdate"] and docker["name"] in self._updatable_list:
                    if docker["usingImage"] and not docker["usingImage"].startswith("sha256:"):
                        # 发送通知
                        self.post_message(
                            mtype=NotificationType.Plugin,
                            title="【DC助手-更新通知】",
                            text=f"您有容器可以更新啦！\n【{docker['name']}】\n当前镜像:{docker['usingImage']}\n状态:{docker['status']} {docker['runningTime']}\n构建时间：{docker['createTime']}")
                    else:
                        self.post_message(
                            mtype=NotificationType.Plugin,
                            title="【DC助手-更新通知】",
                            text=f"监测到您有容器TAG不正确\n【{docker['name']}】\n当前镜像:{docker['usingImage']}\n状态:{docker['status']} "
                                 f"{docker['runningTime']}\n构建时间：{docker['createTime']}\n"
                                 f"该镜像无法通过DC自动更新,请修改TAG")
    def backup(self):
        """
        备份
        """
        try:
            logger.info(f"DC-备份-准备执行")
            backup_url = '%s/api/container/backup' % (self._host)
            result = (RequestUtils(headers={"Authorization": self.get_jwt()})
                      .get_res(backup_url))
            data = result.json()
            if data["code"] == 200:
                if self._backups_notify:
                    self.post_message(
                        mtype=NotificationType.Plugin,
                        title="【DC助手-备份成功】",
                        text=f"镜像备份成功！")
                logger.info(f"DC-备份完成")
            else:
                if self._backups_notify:
                    self.post_message(
                        mtype=NotificationType.Plugin,
                        title="【DC助手-备份失败】",
                        text=f"镜像备份失败拉~！\n【失败原因】:{data['msg']}")
                logger.error(f"DC-备份失败 Error code: {data['code']}, message: {data['msg']}")
        except Exception as e:
            logger.error(f"DC-备份失败,网络异常,请检查DockerCopilot服务是否正常: {str(e)}")
            return []

    @eventmanager.register(EventType.PluginAction)
    def remote_sync(self, event: Event):
        pass

    @eventmanager.register(EventType.PluginAction)
    def force_update_action(self, event: Event):
        """
        处理 /dcfupdate 远程命令
        """
        if not event:
            return
        event_data = event.event_data or {}
        if event_data.get("action") != "force_update":
            return
        arg = (event_data.get("arg") or "").strip()
        self.force_update(container_name=arg or None)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return [
            {
                "cmd": "/dcfupdate",
                "event": EventType.PluginAction,
                "desc": "强制更新 forceupdatelist 中的容器（可指定名称，如 /dcfupdate cloud-media-sync）",
                "category": "DC助手",
                "data": {"action": "force_update"},
            },
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/force_update",
                "endpoint": self.api_force_update,
                "methods": ["POST"],
                "summary": "DC助手强制更新",
                "description": "立即强制更新 forceupdatelist 中的容器，跳过 haveUpdate 检查。body 可选 {\"container_name\": \"xxx\"}；仅当目标在 forceupdatelist 中时执行",
            },
        ]

    def api_force_update(self, container_name: Optional[str] = None) -> Dict[str, Any]:
        """
        强制更新 API endpoint
        """
        self.force_update(container_name=container_name or None)
        return {"success": True, "message": f"已触发强制更新: {container_name or 'forceupdatelist 全部'}"}

    def get_jwt(self) -> str:
        # 减少接口请求直接使用jwt
        payload = {
            "exp": int(time.time()) + 28 * 24 * 60 * 60,
            "iat": int(time.time())
        }
        encoded_jwt = jwt.encode(payload, self._secretKey, algorithm="HS256")
        logger.debug(f"DC helper get jwt---》{encoded_jwt}")
        return "Bearer "+encoded_jwt

    # def get_auth(self) -> str:
    #     """
    #     获取授权
    #     """
    #     auth_url = "%s/api/auth" % (self._host)
    #     rescanres = (RequestUtils()
    #                  .post_res(auth_url, {"secretKey": self._secretKey}))
    #     data = rescanres.json()
    #     if data["code"] == 201:
    #         jwt = data["data"]["jwt"]
    #         return jwt
    #     else:
    #         logger.error(f"DC-获取凭证异常 Error code: {data['code']}, message: {data['msg']}")
    #         return ""

    def get_docker_list(self) -> List[Dict[str, Any]]:
        """
        容器列表
        """
        try:
            docker_url = "%s/api/containers" % (self._host)
            result = (RequestUtils(headers={"Authorization":self.get_jwt() })
                      .get_res(docker_url))
            data = result.json()
            if data["code"] == 0:
                return data["data"]
            else:
                logger.error(f"DC-获取容器列表异常 Error code: {data['code']}, message: {data['msg']}")
                return []
        except Exception as e:
            logger.error(f"DC-请求容器列表时发生网络异常,请检查DockerCopilot服务是否正常: {str(e)}")
            return []

    def get_images_list(self) -> List[Dict[str, Any]]:
        """
        镜像列表
        """
        try:
            images_url = "%s/api/images" % (self._host)
            result = (RequestUtils(headers={"Authorization": self.get_jwt()})
                      .get_res(images_url))
            data = result.json()
            if data["code"] == 200:
                return data["data"]
            else:
                logger.error(f"DC-获取镜像列表异常 Error code: {data['code']}, message: {data['msg']}")
                return []
        except Exception as e:
            logger.error(f"DC-请求镜像列表时发生网络异常,请检查DockerCopilot服务是否正常: {str(e)}")
            return []

    def remove_image(self, sha) -> bool:
        """
        清理镜像
        """
        try:
            images_url = "%s/api/image/%s?force=false" % (self._host, sha)
            result = self.delete_res(images_url,{"Authorization": self.get_jwt()})
            logger.debug(f'result---{result}')
            data = result.json()
            if data["code"] == 200:
                logger.info(f"DC-清理镜像成功: {sha}")
                return True
            else:
                logger.error(f"DC-清理镜像异常 Error code: {data['code']}, message: {data['msg']}")
                return False
        except Exception as e:
            logger.error(f"DC-请求清理镜像时发生网络异常,请检查DockerCopilot服务是否正常: {str(e)}")
            return False

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据： 1、页面配置；2、数据结构
        """
        updatable_list = []
        auto_update_list = []
        force_update_list = []
        if self._secretKey and self._host:
            data = self.get_docker_list()
            # 移除不存在的选项
            names = [item['name'] for item in data]
            if self._updatable_list:
                self._updatable_list = [item for item in self._updatable_list if item in names]
            if self._auto_update_list:
                self._auto_update_list = [item for item in self._auto_update_list if item in names]
            if self._force_update_list:
                self._force_update_list = [item for item in self._force_update_list if item in names]
            if self._auto_update_list or self._updatable_list or self._force_update_list:
                self.__update_config()
            for item in data:
                updatable_list.append({"title": item["name"], "value": item["name"]})
                auto_update_list.append({"title": item["name"], "value": item["name"]})
                force_update_list.append({"title": item["name"], "value": item["name"]})
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '立即运行一次',
                                        }
                                    }
                                ]
                            }
                        ]
                    }, {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'host',
                                            'label': '服务器地址',
                                            'hint': 'dockerCopilot服务地址 http(s)://ip:端口'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'secretKey',
                                            'label': 'secretKey',
                                            'hint': 'dockerCopilot秘钥 环境变量查看'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [{
                            'component': 'VCol',
                            'props': {
                                'cols': 12
                            },
                            'content': [{
                                'component': 'VTabs',
                                'props': {
                                    'model': '_tabs',
                                    'height': 40,
                                    'style': {
                                        'margin-top-': '20px',
                                        'margin-bottom-': '60px',
                                        'margin-right': '30px'
                                    }
                                },
                                'content': [{
                                    'component': 'VTab',
                                    'props': {'value': 'C1'},
                                    'text': '更新通知'
                                },
                                    {
                                        'component': 'VTab',
                                        'props': {'value': 'C2'},
                                        'text': '自动更新'
                                    },
                                    {
                                        'component': 'VTab',
                                        'props': {'value': 'C3'},
                                        'text': '自动备份'
                                    },
                                    {
                                        'component': 'VTab',
                                        'props': {'value': 'C4'},
                                        'text': '强制更新'
                                    }
                                ]
                            },
                                {
                                    'component': 'VWindow',
                                    'props': {
                                        'model': '_tabs'
                                    },
                                    'content': [{
                                        'component': 'VWindowItem',
                                        'props': {
                                            'value': 'C1', 'style': {'margin-top': '30px'}
                                        },
                                        'content': [{
                                            'component': 'VRow',
                                            'content': [
                                                {
                                                    'component': 'VCol',
                                                    'props': {
                                                        'cols': 12,
                                                        'md': 6
                                                    },
                                                    'content': [
                                                        {
                                                            'component': 'VTextField',
                                                            'props': {
                                                                'model': 'updatecron',
                                                                'label': '更新通知周期',
                                                                'placeholder': '15 8-23/2 * * *'
                                                            }
                                                        }
                                                    ]
                                                }
                                            ]
                                        },
                                            {
                                                "component": "VRow",
                                                "content": [
                                                    {
                                                        'component': 'VCol',
                                                        'props': {
                                                            'cols': 12
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'VSelect',
                                                                'props': {
                                                                    'multiple': True,
                                                                    'chips': True,
                                                                    'clearable': True,
                                                                    'model': 'updatablelist',
                                                                    'label': '更新通知容器',
                                                                    'items': updatable_list,
                                                                    'hint': '勾选容器，检测到新版本时发送通知'
                                                                }
                                                            }
                                                        ]
                                                    }
                                                ],
                                            }, ]
                                    }]
                                },
                                {
                                    'component': 'VWindow',
                                    'props': {
                                        'model': '_tabs'
                                    },
                                    'content': [{
                                        'component': 'VWindowItem',
                                        'props': {'value': 'C2', 'style': {'margin-top': '30px'}},
                                        'content': [
                                            {
                                                'component': 'VRow',
                                                'content': [
                                                    {
                                                        'component': 'VCol',
                                                        'props': {
                                                            'cols': 12,
                                                            'md': 6
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'VTextField',
                                                                'props': {
                                                                    'model': 'autoupdatecron',
                                                                    'label': '自动更新周期',
                                                                    'placeholder': '15 2 * * *'
                                                                }
                                                            }
                                                        ]
                                                    },
                                                    {
                                                        'component': 'VCol',
                                                        'props': {
                                                            'cols': 12,
                                                            'md': 3
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'VTextField',
                                                                'props': {
                                                                    'model': 'interval',
                                                                    'label': '跟踪间隔(秒)',
                                                                    'placeholder': '10',
                                                                    'hint': '开启进度汇报时,每多少秒检查一次进度状态，默认10秒'
                                                                }
                                                            }
                                                        ]
                                                    },
                                                    {
                                                        'component': 'VCol',
                                                        'props': {
                                                            'cols': 12,
                                                            'md': 3
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'VTextField',
                                                                'props': {
                                                                    'model': 'intervallimit',
                                                                    'label': '检查次数',
                                                                    'placeholder': '6',
                                                                    'hint': '开启进度汇报，当达限制检查次数后放弃追踪,默认6次'
                                                                }
                                                            }
                                                        ]
                                                    }
                                                ]},
                                            {
                                                'component': 'VRow',
                                                'content': [
                                                    {
                                                        'component': 'VCol',
                                                        'props': {
                                                            'cols': 12,
                                                            'md': 4
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'VSwitch',
                                                                'props': {
                                                                    'model': 'autoupdatenotify',
                                                                    'label': '自动更新通知',
                                                                    'hint': '更新任务创建成功发送通知'
                                                                }
                                                            }
                                                        ]
                                                    },
                                                    {
                                                        'component': 'VCol',
                                                        'props': {
                                                            'cols': 12,
                                                            'md': 4
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'VSwitch',
                                                                'props': {
                                                                    'model': 'schedulereport',
                                                                    'label': '进度汇报',
                                                                    'hint': '追踪更新任务进度并发送通知'
                                                                }
                                                            }
                                                        ]
                                                    },
                                                    {
                                                        'component': 'VCol',
                                                        'props': {
                                                            'cols': 12,
                                                            'md': 4
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'VSwitch',
                                                                'props': {
                                                                    'model': 'deleteimages',
                                                                    'label': '清理镜像',
                                                                    'hint': '在下次执行时清理无tag且不在使用中的全部镜像'
                                                                }
                                                            }
                                                        ]
                                                    },
                                                ]},
                                            {
                                                "component": "VRow",
                                                "content": [
                                                    {
                                                        'component': 'VCol',
                                                        'props': {
                                                            'cols': 12
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'VSelect',
                                                                'props': {
                                                                    'multiple': True,
                                                                    'chips': False,
                                                                    'clearable': True,
                                                                    'model': 'autoupdatelist',
                                                                    'label': '自动更新容器',
                                                                    'items': auto_update_list,
                                                                    'hint': '勾选容器，检测到新版本时自动重建'
                                                                }
                                                            }
                                                        ]
                                                    }
                                                ],
                                            }, ]
                                    }]
                                }]
                        }]
                    },
                    {
                        'component': 'VWindow',
                        'props': {
                            'model': '_tabs'
                        },
                        'content': [{
                            'component': 'VWindowItem',
                            'props': {
                                'value': 'C3',
                                'style': {'margin-top': '30px'}
                            },
                            'content': [{
                                "component": "VRow",
                                "content": [
                                    {
                                        'component': 'VCol',
                                        'props': {
                                            'cols': 12,
                                            'md': 6
                                        },
                                        'content': [
                                            {
                                                'component': 'VTextField',
                                                'props': {
                                                    'model': 'backupcron',
                                                    'label': '自动备份',
                                                    'placeholder': '0 7 * * *'
                                                }
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VCol',
                                        'props': {
                                            'cols': 12,
                                            'md': 6
                                        },
                                        'content': [
                                            {
                                                'component': 'VSwitch',
                                                'props': {
                                                    'model': 'backupsnotify',
                                                    'label': '备份通知',
                                                    'hint': '备份成功发送通知'
                                                }
                                            }
                                        ]
                                    }
                                ]}]
                        }]
                    },
                    {
                        'component': 'VWindow',
                        'props': {
                            'model': '_tabs'
                        },
                        'content': [{
                            'component': 'VWindowItem',
                            'props': {
                                'value': 'C4',
                                'style': {'margin-top': '30px'}
                            },
                            'content': [{
                                "component": "VRow",
                                "content": [
                                    {
                                        'component': 'VCol',
                                        'props': {
                                            'cols': 12
                                        },
                                        'content': [
                                            {
                                                'component': 'VSelect',
                                                'props': {
                                                    'multiple': True,
                                                    'chips': False,
                                                    'clearable': True,
                                                    'model': 'forceupdatelist',
                                                    'label': '强制更新容器',
                                                    'items': force_update_list,
                                                    'hint': '勾选后点击保存，会立即按选中的容器依次重新拉取最新镜像并重建，无论是否检测到新版本；保存后选项会自动清空，下次再想重建请重新勾选'
                                                }
                                            }
                                        ]
                                    }
                                ]
                            }]
                        }]
                    }],
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "updatablenotify": False,
            "autoupdatenotify": False,
            "schedulereport": False,
            "deleteimages": False,
            "backupsnotify": False,
            "interval": 10,
            "intervallimit": 6

        }

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        """
        退出插件
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error("退出插件失败：%s" % str(e))

    def delete_res(self, url: str,
                   headers:dict = None,
                   params: dict = None,
                   data: Any = None,
                   json: dict = None,
                   allow_redirects: bool = True,
                   raise_exception: bool = False
                   ) -> Optional[Response]:
        try:
            return requests.delete(url,
                                   params=params,
                                   data=data,
                                   json=json,
                                   verify=False,
                                   headers=headers,
                                   timeout=20,
                                   allow_redirects=allow_redirects,
                                   stream=False)
        except requests.exceptions.RequestException:
            if raise_exception:
                raise requests.exceptions.RequestException
            return None