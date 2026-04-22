"""src/littrans/ui/pages/characters_page.py — Nhân vật page."""
from __future__ import annotations

import queue
import time

import streamlit as st

from littrans.ui.loaders import load_characters, load_stats
from littrans.ui.ui_utils import _poll, _show_log


def render_characters() -> None:
    S = st.session_state
    chars_data = load_characters(S.current_novel)
    active  = chars_data["active"]
    archive = chars_data["archive"]

    staging_n = 0
    try:
        from littrans.context.characters import has_staging_chars
        staging_n = has_staging_chars()
    except Exception:
        pass

    col_t, col_m, col_v, col_e, col_r = st.columns([3, 1, 1, 1, 1])
    col_t.subheader("👤 Nhân vật")
    with col_r:
        if st.button("↺", help="Làm mới dữ liệu nhân vật", key="chars_refresh"):
            load_characters.clear(); st.rerun()

    if staging_n:
        st.info(f"📥 **{staging_n} nhân vật mới** trong Staging — nhấn **📥 Merge** để thêm vào danh sách theo dõi.")

    def _run_chars_action(action: str) -> None:
        S.chars_action_logs = []; S.chars_action_q = queue.Queue()
        from littrans.ui.runner import run_background
        run_background(S.chars_action_q, mode="clean_chars",
                       novel_name=S.current_novel, char_action=action)
        S.chars_action_running = True

    with col_m:
        if not S.chars_action_running:
            if st.button("📥 Merge", disabled=not staging_n,
                         help="Merge nhân vật từ Staging → Active", key="chars_merge"):
                _run_chars_action("merge"); st.rerun()
        else:
            st.button("⏳", disabled=True, key="chars_merge_busy")

    with col_v:
        if not S.chars_action_running:
            if st.button("✔ Validate", help="Kiểm tra schema profile nhân vật", key="chars_validate"):
                _run_chars_action("validate"); st.rerun()

    with col_e:
        if not S.chars_action_running:
            if st.button("📄 Export", help="Xuất báo cáo nhân vật ra Reports/", key="chars_export"):
                _run_chars_action("export"); st.rerun()

    if S.chars_action_running or S.chars_action_logs:
        if S.chars_action_running:
            if _poll("chars_action_q", "chars_action_logs"):
                S.chars_action_running = False
                S.chars_action_logs.append("✅ Hoàn tất.")
                load_characters.clear()
        with st.expander("📋 Nhật ký hành động nhân vật", expanded=S.chars_action_running):
            _show_log(S.chars_action_logs)
        if S.chars_action_running:
            time.sleep(0.9); st.rerun()

    st.divider()

    if not active and not archive:
        st.info("**Chưa có nhân vật nào.** Dữ liệu tự động thu thập khi dịch.")
        return

    tab_a, tab_b = st.tabs([f"Đang theo dõi ({len(active)})",
                             f"Lưu trữ ({len(archive)})"])

    for tab, chars, label in [(tab_a, active, "active"), (tab_b, archive, "archive")]:
        with tab:
            if not chars:
                st.info(f"Không có nhân vật nào trong {label}.")
                continue
            search = st.text_input("🔍", placeholder="Tìm tên...",
                                   label_visibility="collapsed", key=f"cs_{label}")
            filtered = {k: v for k, v in chars.items()
                        if not search or search.lower() in k.lower()}
            st.caption(f"{len(filtered)} nhân vật")
            cols_3 = st.columns(3)
            for i, (name, profile) in enumerate(filtered.items()):
                with cols_3[i % 3]:
                    _char_card(name, profile)


def _char_card(name: str, p: dict) -> None:
    speech = p.get("speech", {})
    power  = p.get("power", {})
    ident  = p.get("identity", {})
    arc    = p.get("arc_status", {})
    em     = p.get("emotional_state", {})
    rels   = p.get("relationships", {})

    palettes = [("#E1F5EE","#085041"),("#EEEDFE","#3C3489"),("#E6F1FB","#0C447C"),
                ("#FAEEDA","#633806"),("#FCEBEB","#791F1F"),("#EAF3DE","#3B6D11")]
    bg, fg   = palettes[sum(ord(c) for c in name) % len(palettes)]
    initials = "".join(w[0].upper() for w in name.split()[:2]) or name[:2].upper()

    state  = em.get("current", "normal")
    em_map = {"angry"  : '<span class="badge badge-err">TỨC GIẬN</span>',
              "hurt"   : '<span class="badge badge-warn">TỔN THƯƠNG</span>',
              "changed": '<span class="badge badge-info">ĐÃ THAY ĐỔI</span>'}
    em_html = em_map.get(state, "")

    pronoun_self = speech.get("pronoun_self", "—")
    level        = power.get("current_level", "—")
    faction      = ident.get("faction", p.get("faction", ""))
    goal_raw     = (arc or {}).get("current_goal", "")
    goal         = goal_raw[:70] + "…" if len(goal_raw) > 70 else goal_raw
    history      = p.get("_history", [])

    with st.container(border=True):
        av_col, info_col = st.columns([1, 4])
        with av_col:
            st.markdown(
                f'<div style="width:38px;height:38px;border-radius:50%;background:{bg};'
                f'color:{fg};display:flex;align-items:center;justify-content:center;'
                f'font-size:13px;font-weight:600">{initials}</div>',
                unsafe_allow_html=True,
            )
        with info_col:
            st.markdown(f"**{name}**")
            st.caption(p.get("role", "?"))
            if em_html: st.markdown(em_html, unsafe_allow_html=True)

        st.caption(f"Tự xưng: **{pronoun_self}** · Cấp: **{level}**")
        if faction: st.caption(f"Phe: {faction}")
        if goal:    st.caption(f"Mục tiêu: {goal}")

        for other, rel in list(rels.items())[:3]:
            dyn = rel.get("dynamic", "")
            if not dyn: continue
            status = rel.get("pronoun_status", "weak")
            icon = "✓" if status == "strong" else "🔸"
            css  = "strong-lock" if status == "strong" else "weak-lock"
            st.markdown(
                f'<span class="{css}">{icon} {name} ↔ {other}: <b>{dyn}</b></span>',
                unsafe_allow_html=True,
            )

        if history:
            with st.expander(f"📋 Lịch sử ({len(history)} thay đổi)", expanded=False):
                try:
                    from littrans.context.char_history import get_log
                    for commit in get_log(p, limit=5):
                        cid    = commit["commit"]
                        ts     = commit.get("timestamp", "")[:10]
                        fields = [f for f in commit.get("changes", {}) if f != "__created__"]
                        label  = ", ".join(fields[:3]) if fields else "tạo mới"
                        st.caption(f"• `{cid}` [{ts}] — {label}")
                except Exception:
                    st.caption("(không đọc được lịch sử)")
