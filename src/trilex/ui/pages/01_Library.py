"""Library page — list / create projects + active-project switcher."""

from __future__ import annotations

import re

import streamlit as st

from trilex.persistence.repos import ProjectRepo
from trilex.ui._helpers import (
    db_ready,
    get_session_maker,
    list_projects,
    run_async,
    sidebar_project_selector,
)

st.set_page_config(page_title="Library — TriLex", page_icon="📚", layout="wide")

sidebar_project_selector()

st.title("📚 Library")

if not db_ready():
    st.error("DB chưa init. Chạy `trilex db init`.")
    st.stop()

projects = list_projects()
active_id = st.session_state.get("active_project_id")

# --------------------------------------------------------------------------- #
# Existing projects                                                           #
# --------------------------------------------------------------------------- #

if projects:
    st.subheader(f"{len(projects)} project")
    for p in projects:
        is_active = active_id == p.id
        with st.container(border=True):
            cols = st.columns([4, 1, 1, 1])
            label = f"**{p.name}**" + (" 🟢" if is_active else "")
            cols[0].markdown(
                f"{label}\n\n"
                f"`{p.slug}` · {p.source_lang}→{p.target_lang} · {p.genre}\n\n"
                f"Created: {p.created_at.strftime('%Y-%m-%d %H:%M')}"
            )
            if cols[1].button(
                "Open" if not is_active else "Active",
                key=f"switch_{p.id}",
                disabled=is_active,
                use_container_width=True,
            ):
                st.session_state["active_project_id"] = p.id
                st.rerun()
            if cols[2].button(
                "→ Translate",
                key=f"translate_{p.id}",
                use_container_width=True,
            ):
                st.session_state["active_project_id"] = p.id
                st.switch_page("pages/02_Translate.py")
            if cols[3].button(
                "🗑️",
                key=f"delete_{p.id}",
                use_container_width=True,
                help="Delete project + chapters + terms + jobs (cascade)",
            ):
                st.session_state[f"confirm_del_{p.id}"] = True

            if st.session_state.get(f"confirm_del_{p.id}"):
                st.warning(
                    f"⚠️ Xóa **{p.name}** và toàn bộ chapters/terms/jobs liên quan? "
                    "Không thể hoàn tác."
                )
                ccols = st.columns(2)
                if ccols[0].button("Xác nhận xóa", key=f"do_del_{p.id}", type="primary"):

                    async def _do_delete(pid=p.id):
                        async with get_session_maker()() as s:
                            await ProjectRepo(s).delete(pid)
                            await s.commit()

                    run_async(_do_delete())
                    if active_id == p.id:
                        st.session_state.pop("active_project_id", None)
                    st.session_state.pop(f"confirm_del_{p.id}", None)
                    st.rerun()
                if ccols[1].button("Hủy", key=f"cancel_del_{p.id}"):
                    st.session_state.pop(f"confirm_del_{p.id}", None)
                    st.rerun()
else:
    st.info("Chưa có project. Tạo mới bên dưới.")

st.divider()

# --------------------------------------------------------------------------- #
# Create new                                                                  #
# --------------------------------------------------------------------------- #

st.subheader("➕ Tạo project mới")

with st.form("new_project"):
    name = st.text_input("Tên project", placeholder="VD: Đại Đạo Tu Tiên")
    slug_default = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-") if name else ""
    slug = st.text_input("Slug (URL-safe)", value=slug_default, placeholder="dai-dao-tu-tien")
    cols = st.columns(3)
    source_lang = cols[0].selectbox("Source lang", ["zh", "en", "vn"], index=0)
    target_lang = cols[1].selectbox("Target lang", ["vn", "en"], index=0)
    genre = cols[2].selectbox("Genre", ["tu_tien", "litrpg", "vu_su", "hien_dai", "other"], index=0)
    vault_path = st.text_input(
        "Vault path (optional, default: `data/vault`)",
        placeholder="data/vault",
    )
    submit = st.form_submit_button("Tạo project", type="primary")

if submit:
    errors = []
    if not name.strip():
        errors.append("Thiếu tên")
    if not slug.strip():
        errors.append("Thiếu slug")
    if not re.fullmatch(r"[a-z0-9-]+", slug or ""):
        errors.append("Slug chỉ được chứa [a-z 0-9 -]")
    if source_lang == target_lang:
        errors.append("source_lang phải khác target_lang")
    if errors:
        for e in errors:
            st.error(e)
    else:

        async def _create():
            async with get_session_maker()() as s:
                repo = ProjectRepo(s)
                p = await repo.create(
                    name=name.strip(),
                    slug=slug.strip(),
                    source_lang=source_lang,
                    target_lang=target_lang,
                    genre=genre,
                    vault_path=vault_path.strip() or None,
                )
                await s.commit()
                return p

        try:
            created = run_async(_create())
        except Exception as e:  # noqa: BLE001
            st.error(f"Tạo thất bại: {e}")
        else:
            st.session_state["active_project_id"] = created.id
            st.success(f"Đã tạo {created.name}")
            st.rerun()
