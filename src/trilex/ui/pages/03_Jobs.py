"""Jobs page — live monitor (auto-refresh every 2s) with detail + cancel."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from trilex.persistence.repos import JobRepo
from trilex.ui._helpers import (
    db_ready,
    get_session_maker,
    run_async,
    sidebar_project_selector,
)
from trilex.ui.runners import cancel_job

st.set_page_config(page_title="Jobs — TriLex", page_icon="⚙️", layout="wide")

sidebar_project_selector()

st.title("⚙️ Jobs")

if not db_ready():
    st.error("DB chưa init. Chạy `trilex db init`.")
    st.stop()

active = st.session_state.get("active_project_id")
if active is None:
    st.warning("Chọn project ở sidebar.")
    st.stop()


def _eta(job) -> str:
    if job.started_at is None or job.progress <= 0:
        return "—"
    elapsed = (datetime.now(UTC) - job.started_at).total_seconds()
    if job.progress >= 1.0:
        return "done"
    remaining = elapsed * (1 - job.progress) / job.progress
    return f"~{int(remaining)}s"


def _format_row(job) -> dict:
    return {
        "id": job.id[:8],
        "type": job.type,
        "status": job.status,
        "progress": f"{int(job.progress * 100)}%",
        "eta": _eta(job),
        "started": job.started_at.strftime("%H:%M:%S") if job.started_at else "—",
        "error": (job.error or "")[:100],
    }


@st.fragment(run_every="2s")
def _jobs_panel() -> None:
    async def _fetch():
        async with get_session_maker()() as s:
            repo = JobRepo(s)
            pending = await repo.list_for_project(active, status="pending")
            running = await repo.list_for_project(active, status="running")
            completed = await repo.list_for_project(active, status="completed", limit=20)
            failed = await repo.list_for_project(active, status="failed", limit=20)
            cancelled = await repo.list_for_project(active, status="cancelled", limit=10)
            return pending, running, completed, failed, cancelled

    try:
        pending, running, completed, failed, cancelled = run_async(_fetch())
    except Exception as e:  # noqa: BLE001
        st.error(f"Lỗi đọc jobs: {e}")
        return

    cols = st.columns(5)
    cols[0].metric("Pending", len(pending))
    cols[1].metric("Running", len(running))
    cols[2].metric("Completed", len(completed))
    cols[3].metric("Failed", len(failed))
    cols[4].metric("Cancelled", len(cancelled))

    if running:
        st.subheader("🏃 Running")
        for j in running:
            with st.container(border=True):
                st.progress(
                    min(max(j.progress, 0.0), 1.0),
                    text=f"{j.type} · {int(j.progress * 100)}% · id `{j.id[:8]}…` · ETA {_eta(j)}",
                )
                ecols = st.columns([3, 1])
                with ecols[0].expander("Payload"):
                    st.json(j.payload or {})
                if ecols[1].button("⏹️ Cancel", key=f"cancel_{j.id}"):
                    if cancel_job(j.id):
                        st.success("Đã yêu cầu cancel. Worker dừng trước chương kế tiếp.")
                    else:
                        st.warning("Không thể cancel (job đã kết thúc).")
                    st.rerun()

    if pending:
        st.subheader("⏳ Pending")
        for j in pending:
            cols2 = st.columns([4, 1])
            cols2[0].write(
                f"`{j.id[:8]}…` · type **{j.type}** · "
                f"created {j.created_at.strftime('%H:%M:%S')}"
            )
            if cols2[1].button("Cancel", key=f"cancel_pending_{j.id}"):
                cancel_job(j.id)
                st.rerun()

    if completed:
        st.subheader("✅ Completed")
        st.dataframe(
            [_format_row(j) for j in completed],
            use_container_width=True,
            hide_index=True,
        )

    if failed:
        st.subheader("💥 Failed")
        st.dataframe(
            [_format_row(j) for j in failed],
            use_container_width=True,
            hide_index=True,
        )
        for j in failed:
            with st.expander(f"Detail · `{j.id[:8]}…`"):
                st.write("**Error**:", j.error or "(no message)")
                st.write("**Payload**:")
                st.json(j.payload or {})

    if cancelled:
        st.subheader("🚫 Cancelled")
        st.dataframe(
            [_format_row(j) for j in cancelled],
            use_container_width=True,
            hide_index=True,
        )


_jobs_panel()
