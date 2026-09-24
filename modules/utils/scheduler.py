from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from modules.utils.database import Database


class PersistentScheduler:
    def __init__(self, db: Database, timezone: str) -> None:
        self.db = db
        self.timezone = ZoneInfo(timezone)
        self.scheduler = AsyncIOScheduler(timezone=self.timezone)
        self.logger = logging.getLogger("selfbot.scheduler")
        self._handlers: dict[str, Callable[..., Awaitable[Any]]] = {}

    def register_handler(
        self, task_type: str, handler: Callable[..., Awaitable[Any]]
    ) -> None:
        self._handlers[task_type] = handler

    async def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()
        await self.restore()

    async def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def restore(self) -> None:
        tasks = await self.db.fetchall(
            "SELECT * FROM scheduled_tasks WHERE is_active = 1 ORDER BY id"
        )
        for task in tasks:
            handler = self._handlers.get(task["task_type"])
            if not handler:
                continue
            try:
                payload = json.loads(task["payload_json"])
                if task["trigger"] == "interval" and task["interval_seconds"]:
                    self.scheduler.add_job(
                        handler,
                        "interval",
                        seconds=float(task["interval_seconds"]),
                        kwargs=payload,
                        id=f"db:{task['id']}",
                        replace_existing=True,
                        coalesce=True,
                        max_instances=1,
                    )
                elif task["trigger"] == "cron" and task["cron_json"]:
                    cron = json.loads(task["cron_json"])
                    self.scheduler.add_job(
                        handler,
                        "cron",
                        **cron,
                        kwargs=payload,
                        id=f"db:{task['id']}",
                        replace_existing=True,
                        coalesce=True,
                        max_instances=1,
                    )
            except Exception:
                self.logger.exception("Failed to restore scheduled task %s", task["id"])

    async def add_interval(
        self,
        task_type: str,
        seconds: float,
        payload: dict[str, Any],
    ) -> int:
        row_id = await self.db.execute(
            """
            INSERT INTO scheduled_tasks(task_type, payload_json, trigger, interval_seconds)
            VALUES(?, ?, 'interval', ?)
            """,
            (task_type, json.dumps(payload, ensure_ascii=False), seconds),
        )
        handler = self._handlers.get(task_type)
        if handler:
            self.scheduler.add_job(
                handler,
                "interval",
                seconds=seconds,
                kwargs=payload,
                id=f"db:{row_id}",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )
        return row_id

    async def add_cron(
        self,
        task_type: str,
        cron: dict[str, Any],
        payload: dict[str, Any],
    ) -> int:
        row_id = await self.db.execute(
            """
            INSERT INTO scheduled_tasks(task_type, payload_json, trigger, cron_json)
            VALUES(?, ?, 'cron', ?)
            """,
            (
                task_type,
                json.dumps(payload, ensure_ascii=False),
                json.dumps(cron, ensure_ascii=False),
            ),
        )
        handler = self._handlers.get(task_type)
        if handler:
            self.scheduler.add_job(
                handler,
                "cron",
                **cron,
                kwargs=payload,
                id=f"db:{row_id}",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
            )
        return row_id

    async def remove(self, task_id: int) -> None:
        with_job_id = f"db:{task_id}"
        if self.scheduler.get_job(with_job_id):
            self.scheduler.remove_job(with_job_id)
        await self.db.execute(
            "UPDATE scheduled_tasks SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (task_id,),
        )

    async def list_tasks(self) -> list[dict[str, Any]]:
        return await self.db.fetchall(
            "SELECT * FROM scheduled_tasks WHERE is_active = 1 ORDER BY id"
        )

    def pending_count(self) -> int:
        return len(self.scheduler.get_jobs())
