from datetime import datetime
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from config.settings import settings


class SchedulerService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    def schedule_task(
        self,
        task_id: str,
        func: Callable,
        run_date: datetime,
        args: tuple = (),
        kwargs: dict = None,
    ) -> str:
        job = self.scheduler.add_job(
            func,
            trigger=DateTrigger(run_date=run_date),
            args=args,
            kwargs=kwargs or {},
            id=task_id,
            replace_existing=True,
        )
        return job.id

    def schedule_recurring_task(
        self,
        task_id: str,
        func: Callable,
        cron_expression: str,
        args: tuple = (),
        kwargs: dict = None,
    ) -> str:
        # parse cron expression: "0 9 * * *" for 9am daily
        parts = cron_expression.split()

        job = self.scheduler.add_job(
            func,
            trigger=CronTrigger(
                minute=parts[0] if len(parts) > 0 else "*",
                hour=parts[1] if len(parts) > 1 else "*",
                day=parts[2] if len(parts) > 2 else "*",
                month=parts[3] if len(parts) > 3 else "*",
                day_of_week=parts[4] if len(parts) > 4 else "*",
            ),
            args=args,
            kwargs=kwargs or {},
            id=task_id,
            replace_existing=True,
        )
        return job.id

    def cancel_task(self, task_id: str) -> bool:
        try:
            self.scheduler.remove_job(task_id)
            return True
        except Exception:
            return False

    def get_scheduled_tasks(self) -> list:
        return [
            {
                "id": job.id,
                "next_run": job.next_run_time.isoformat()
                if job.next_run_time
                else None,
                "trigger": str(job.trigger),
            }
            for job in self.scheduler.get_jobs()
        ]


scheduler_service = SchedulerService()
