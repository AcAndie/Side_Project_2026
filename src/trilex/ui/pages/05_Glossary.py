"""Glossary page — per-novel terms editor + pending review (scout proposals)."""

from __future__ import annotations

import streamlit as st

from trilex.persistence.repos import TermRepo
from trilex.ui._helpers import (
    db_ready,
    get_session_maker,
    run_async,
    sidebar_project_selector,
)

st.set_page_config(page_title="Glossary — TriLex", page_icon="🔖", layout="wide")

sidebar_project_selector()

st.title("🔖 Glossary")

if not db_ready():
    st.error("DB chưa init. Chạy `trilex db init`.")
    st.stop()

active = st.session_state.get("active_project_id")
if active is None:
    st.warning("Chọn project ở sidebar.")
    st.stop()

CATEGORIES = ("character", "skill", "realm", "place", "item", "org", "system_msg", "phrase")


async def _list_accepted():
    async with get_session_maker()() as s:
        return await TermRepo(s).list_for_project(active, status="accepted")


async def _list_pending():
    async with get_session_maker()() as s:
        return await TermRepo(s).list_pending(active)


pending = run_async(_list_pending())
accepted = run_async(_list_accepted())

# --------------------------------------------------------------------------- #
# Pending Review                                                              #
# --------------------------------------------------------------------------- #

if pending:
    st.subheader(f"🟡 Pending Review ({len(pending)})")
    st.caption("Scout đã đề xuất các term sau. Accept/Reject để lock hoặc bỏ.")
    for t in pending:
        with st.container(border=True):
            cols = st.columns([3, 2, 2, 1, 1, 1])
            cols[0].markdown(f"**{t.locked_zh}** → **{t.locked_vn or '—'}**")
            cols[1].caption(f"category: `{t.category}` · confidence: {t.confidence:.2f}")
            cols[2].caption(t.notes or "")
            if cols[3].button("✅", key=f"accept_{t.id}", help="Accept (lock)"):

                async def _accept(tid=t.id):
                    async with get_session_maker()() as s:
                        await TermRepo(s).accept_pending(tid)
                        await s.commit()

                run_async(_accept())
                st.rerun()
            if cols[4].button("❌", key=f"reject_{t.id}", help="Reject (delete)"):

                async def _reject(tid=t.id):
                    async with get_session_maker()() as s:
                        await TermRepo(s).reject_pending(tid)
                        await s.commit()

                run_async(_reject())
                st.rerun()
            with cols[5].popover("✏️"):
                new_vn = st.text_input("Sửa target", value=t.locked_vn or "", key=f"edit_vn_{t.id}")
                if st.button("Save & Accept", key=f"save_accept_{t.id}"):

                    async def _edit(tid=t.id, vn=new_vn):
                        async with get_session_maker()() as s:
                            repo = TermRepo(s)
                            term = await repo.get(tid)
                            if term is not None:
                                term.locked_vn = vn.strip() or term.locked_vn
                                term.status = "accepted"
                            await s.commit()

                    run_async(_edit())
                    st.rerun()
    st.divider()

# --------------------------------------------------------------------------- #
# Accepted terms                                                              #
# --------------------------------------------------------------------------- #

st.subheader(f"🔒 Locked terms ({len(accepted)})")

cat_filter = st.multiselect("Lọc theo category", list(CATEGORIES))
visible = [t for t in accepted if t.category in cat_filter] if cat_filter else list(accepted)
if visible:
    rows = [
        {
            "id": t.id[:8],
            "category": t.category,
            "zh": t.locked_zh or "",
            "vn": t.locked_vn or "",
            "en": t.locked_en or "",
            "confidence": round(t.confidence, 2),
            "source": t.source,
        }
        for t in visible
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    st.info("Chưa có term locked. Thêm thủ công bên dưới hoặc chạy scout.")

# --------------------------------------------------------------------------- #
# Conflicts                                                                   #
# --------------------------------------------------------------------------- #


async def _conflicts():
    async with get_session_maker()() as s:
        return await TermRepo(s).find_conflicts(project_id=active)


conflicts = run_async(_conflicts())
if conflicts:
    st.warning(f"⚠️ {len(conflicts)} conflict — cùng ZH source, target khác nhau")
    for zh, group in conflicts:
        st.write(f"- `{zh}` → " + " | ".join(f"`{t.locked_vn}`" for t in group))

st.divider()

# --------------------------------------------------------------------------- #
# Add new (manual)                                                            #
# --------------------------------------------------------------------------- #

st.subheader("➕ Thêm term thủ công")
with st.form("new_term"):
    cols = st.columns(3)
    locked_zh = cols[0].text_input("ZH source", placeholder="李青")
    locked_vn = cols[1].text_input("VN target", placeholder="Lý Thanh")
    locked_en = cols[2].text_input("EN target (optional)")
    cols2 = st.columns(2)
    category = cols2[0].selectbox("Category", list(CATEGORIES), index=0)
    confidence = cols2[1].slider("Confidence", 0.0, 1.0, 1.0, 0.05)
    notes = st.text_input("Notes (optional)")
    add = st.form_submit_button("Thêm", type="primary")

if add:
    if not locked_zh.strip() and not locked_vn.strip():
        st.error("Cần ít nhất 1 trong 2 trường zh/vn")
    else:

        async def _create():
            async with get_session_maker()() as s:
                repo = TermRepo(s)
                t = await repo.create(
                    project_id=active,
                    category=category,
                    locked_zh=locked_zh.strip() or None,
                    locked_vn=locked_vn.strip() or None,
                    locked_en=locked_en.strip() or None,
                    confidence=confidence,
                    notes=notes.strip(),
                    source="manual",
                )
                # Manual entries skip review.
                t.status = "accepted"
                await s.commit()
                return t

        try:
            run_async(_create())
        except Exception as e:  # noqa: BLE001
            st.error(f"Thêm thất bại: {e}")
        else:
            st.success("Đã thêm")
            st.rerun()

st.divider()

# --------------------------------------------------------------------------- #
# Scout — extract new terms from translated chapters                          #
# --------------------------------------------------------------------------- #

st.subheader("🔍 Scout — quét term mới từ chương đã dịch")
st.caption(
    "Gửi 1 LLM call để extract proper nouns / skill / sect khỏi chương gần nhất "
    "chưa scout. Sau khi xong, các term sẽ hiện ở **Pending Review** ở trên."
)
cols = st.columns([2, 2, 1])
last_n = cols[0].slider("Quét N chương gần nhất", min_value=1, max_value=20, value=5, key="scout_n")
auto_accept = cols[1].checkbox(
    "Auto-accept (bỏ qua pending review)",
    value=True,
    key="scout_auto_accept",
    help="ON: term mới khóa luôn vào glossary. OFF: chờ review.",
)
if cols[2].button("🚀 Run scout", type="primary", key="run_scout"):
    from sqlalchemy import desc, select

    from trilex.memory import scout_terms
    from trilex.persistence.models import Chapter
    from trilex.ui._helpers import gemini_provider_or_warn

    provider = gemini_provider_or_warn()
    if provider is None:
        st.stop()

    async def _do_scout():
        async with get_session_maker()() as s:
            result = await s.execute(
                select(Chapter)
                .where(
                    Chapter.project_id == active,
                    Chapter.polished_text.isnot(None),
                )
                .order_by(desc(Chapter.index))
                .limit(last_n)
            )
            chapters = list(result.scalars())
            repo = TermRepo(s)
            glossary_rows = await repo.list_for_project(active, status="accepted")
            # Convert SQLAlchemy Term rows into core Term DTOs.
            from trilex.core.models.term import Term as TermDTO

            glossary = [
                TermDTO(
                    source=r.locked_zh or r.locked_vn or "",
                    target=r.locked_vn or r.locked_en or r.locked_zh or "",
                    category=(r.category if r.category != "system_msg" else "phrase"),
                )
                for r in glossary_rows
                if (r.locked_zh or "")
            ]
            total_proposed = 0
            for ch in chapters:
                proposals = await scout_terms(
                    original=ch.source_text,
                    translation=ch.polished_text or "",
                    provider=provider,
                    glossary=glossary,
                )
                if not proposals:
                    continue
                inserted = await repo.insert_pending(
                    [
                        (
                            p.zh,
                            p.vn,
                            p.category if p.category != "sect" else "org",
                            p.confidence,
                            p.notes,
                        )
                        for p in proposals
                    ],
                    project_id=active,
                    status="accepted" if auto_accept else "pending",
                )
                total_proposed += inserted
            await s.commit()
            return len(chapters), total_proposed

    with st.spinner(f"Scout {last_n} chương..."):
        try:
            n_scanned, n_new = run_async(_do_scout())
        except Exception as e:  # noqa: BLE001
            st.error(f"Scout thất bại: {type(e).__name__}: {e}")
        else:
            label = "locked" if auto_accept else "pending"
            st.success(f"Scout xong: {n_scanned} chương → {n_new} term mới ({label}).")
            st.rerun()
