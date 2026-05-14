"""Job repository — async queue helpers (pending → running → completed)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trilex.persistence.models import Job

VALID_STATUSES = ("pending", "running", "completed", "failed", "cancelled")


class JobRepo:
    """CRUD on `Job`. Models a simple FIFO queue per project."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        project_id: str,
        job_type: str,
        payload: dict[str, Any] | None = None,
    ) -> Job:
        job = Job(
            project_id=project_id,
            type=job_type,
            status="pending",
            progress=0.0,
            payload=payload or {},
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get(self, job_id: str) -> Job | None:
        return await self.session.get(Job, job_id)

    async def get_pending(
        self,
        project_id: str | None = None,
        *,
        job_type: str | None = None,
        limit: int | None = None,
    ) -> Sequence[Job]:
        stmt = select(Job).where(Job.status == "pending").order_by(Job.created_at.asc())
        if project_id is not None:
            stmt = stmt.where(Job.project_id == project_id)
        if job_type is not None:
            stmt = stmt.where(Job.type == job_type)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def mark_running(self, job_id: str) -> Job | None:
        job = await self.get(job_id)
        if job is None:
            return None
        if job.status != "pending":
            raise ValueError(f"Job {job_id} not pending (status={job.status!r})")
        job.status = "running"
        job.started_at = datetime.now(UTC)
        job.progress = 0.0
        await self.session.flush()
        return job

    async def update_progress(self, job_id: str, progress: float) -> Job | None:
        if not 0.0 <= progress <= 1.0:
            raise ValueError(f"progress must be in [0,1], got {progress}")
        job = await self.get(job_id)
        if job is None:
            return None
        job.progress = progress
        await self.session.flush()
        return job

    async def mark_complete(self, job_id: str) -> Job | None:
        job = await self.get(job_id)
        if job is None:
            return None
        job.status = "completed"
        job.progress = 1.0
        job.completed_at = datetime.now(UTC)
        job.error = None
        await self.session.flush()
        return job

    async def mark_failed(self, job_id: str, error: str) -> Job | None:
        job = await self.get(job_id)
        if job is None:
            return None
        job.status = "failed"
        job.completed_at = datetime.now(UTC)
        job.error = error
        await self.session.flush()
        return job

    async def cancel(self, job_id: str) -> Job | None:
        job = await self.get(job_id)
        if job is None:
            return None
        if job.status in ("completed", "failed", "cancelled"):
            return job
        job.status = "cancelled"
        job.completed_at = datetime.now(UTC)
        await self.session.flush()
        return job

    async def list_for_project(
        self,
        project_id: str,
        *,
        status: str | None = None,
        limit: int | None = None,
    ) -> Sequence[Job]:
        stmt = select(Job).where(Job.project_id == project_id).order_by(Job.created_at.desc())
        if status is not None:
            stmt = stmt.where(Job.status == status)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def delete(self, job_id: str) -> bool:
        job = await self.get(job_id)
        if job is None:
            return False
        await self.session.delete(job)
        await self.session.flush()
        return True
