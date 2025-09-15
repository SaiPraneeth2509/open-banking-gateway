from __future__ import annotations
import asyncio
import logging
from anyio import to_thread

from app.db.session import SessionLocal
from app.repositories.consents import expire_due

class ExpirySweeper:
    def __init__(self, interval_seconds: int = 60) -> None:
        self.interval = interval_seconds
        self._task: asyncio.Task | None = None
        self._stopping = False

    async def start(self) -> None:
        if self._task:
            return
        self._stopping = False
        self._task = asyncio.create_task(self._run(), name="expiry-sweeper")

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None

    async def _run(self) -> None:
        log = logging.getLogger("expiry")
        while not self._stopping:
            try:
                count = await to_thread.run_sync(self._expire_once)
                if count:
                    log.info("expired_consents count=%d", count)
            except Exception:
                log.exception("expiry_sweep_error")
            await asyncio.sleep(self.interval)

    def _expire_once(self) -> int:
        db = SessionLocal()
        try:
            return expire_due(db)
        finally:
            db.close()
