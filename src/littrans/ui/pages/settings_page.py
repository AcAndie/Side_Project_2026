"""src/littrans/ui/pages/settings_page.py — Cài đặt page."""
from __future__ import annotations

import streamlit as st

from littrans.ui.loaders import load_stats
from littrans.ui.env_utils import _load_env, _save_env, _ENV_PATH


def render_settings() -> None:
    S = st.session_state
    env = _load_env()
    def e(k, d=""):
        return env.get(k, d)
    def ei(k, d):
        try: return int(env.get(k, str(d)))
        except: return d
    def ef(k, d):
        try: return float(env.get(k, str(d)))
        except: return d
    def eb(k, d):
        v = env.get(k, "").strip().lower()
        return v in ("true","1","yes","on") if v else d

    hc1, hc2, hc3 = st.columns([4, 1, 1])
    hc1.subheader("⚙️ Cài đặt")
    save_clicked  = hc2.button("💾 Lưu", type="primary", use_container_width=True)
    reset_clicked = hc3.button("↺ Reset", use_container_width=True)

    if S.settings_saved:
        st.success("✅ Đã lưu! Khởi động lại pipeline để áp dụng.")
        S.settings_saved = False
    if not _ENV_PATH.exists():
        st.warning("⚠️  Chưa có file `.env`. Điền API Key và nhấn Lưu.")

    updates: dict[str, str] = {}

    tabs = st.tabs([
        "🚀 Cơ bản", "⚙️ Pipeline", "🔭 Scout AI",
        "📖 Từ điển auto", "👤 Nhân vật", "📖 Bible",
        "💰 Token", "🔀 Merge", "📁 Đường dẫn",
    ])

    with tabs[0]:
        st.markdown("#### 🔑 API Key (bắt buộc)")
        st.markdown("[Lấy miễn phí tại aistudio.google.com →](https://aistudio.google.com)")

        k_primary = st.text_input(
            "Gemini API Key *", value=e("GEMINI_API_KEY"),
            type="password", placeholder="AIzaSy...",
            help="Bắt buộc. Lấy miễn phí tại aistudio.google.com",
        )
        updates["GEMINI_API_KEY"] = k_primary

        c1, c2, c3 = st.columns(3)
        k_fb1 = c1.text_input("Key dự phòng 1", value=e("FALLBACK_KEY_1"), type="password",
                               help="Tài khoản Google khác — dùng khi key chính bị giới hạn")
        k_fb2 = c2.text_input("Key dự phòng 2", value=e("FALLBACK_KEY_2"), type="password")
        k_rot = c3.number_input("Rotate sau N lỗi", 1, 10, ei("KEY_ROTATE_THRESHOLD", 3),
                                 help="Chuyển sang key dự phòng sau bao nhiêu lỗi liên tiếp")
        updates.update({"FALLBACK_KEY_1": k_fb1, "FALLBACK_KEY_2": k_fb2,
                        "KEY_ROTATE_THRESHOLD": str(k_rot)})

        st.divider()
        st.markdown("#### 🤖 Engine dịch")
        provider_opts = ["gemini", "anthropic"]
        cur_prov  = e("TRANSLATION_PROVIDER", "gemini")
        prov_idx  = provider_opts.index(cur_prov) if cur_prov in provider_opts else 0
        prov_fmt  = {"gemini"    : "Gemini (Google) — miễn phí, khuyến nghị",
                     "anthropic" : "Claude (Anthropic) — chất lượng cao hơn, có phí"}
        prov_sel  = st.radio("Provider", provider_opts, index=prov_idx,
                             format_func=lambda x: prov_fmt[x], horizontal=False)
        updates["TRANSLATION_PROVIDER"] = prov_sel

        if prov_sel == "gemini":
            _models = ["gemini-2.5-flash","gemini-2.5-pro","gemini-2.0-flash-exp","gemini-1.5-pro"]
            _mlbl   = {"gemini-2.5-flash"    : "2.5 Flash — nhanh, miễn phí ✓",
                       "gemini-2.5-pro"      : "2.5 Pro — tốt hơn, hạn ngạch thấp hơn",
                       "gemini-2.0-flash-exp": "2.0 Flash Exp (cũ hơn)",
                       "gemini-1.5-pro"      : "1.5 Pro (cũ)"}
            cur_m = e("GEMINI_MODEL", "gemini-2.5-flash")
            m_idx = _models.index(cur_m) if cur_m in _models else 0
            model = st.selectbox("Model", _models, index=m_idx, format_func=lambda x: _mlbl.get(x, x))
            updates["GEMINI_MODEL"] = model; updates["TRANSLATION_MODEL"] = ""
        else:
            ant_key = st.text_input("Anthropic API Key *", value=e("ANTHROPIC_API_KEY"),
                                    type="password", placeholder="sk-ant-...",
                                    help="Lấy tại console.anthropic.com")
            trans_model = st.text_input("Claude model",
                                        value=e("TRANSLATION_MODEL","claude-sonnet-4-6"),
                                        help="Ví dụ: claude-sonnet-4-6, claude-opus-4-6")
            updates.update({"ANTHROPIC_API_KEY": ant_key, "TRANSLATION_MODEL": trans_model})

        st.divider()
        st.markdown("#### ⏱️ Tốc độ")
        c1, c2 = st.columns(2)
        succ_s = c1.slider("Nghỉ sau mỗi chương (giây)", 0, 120,
                           ei("SUCCESS_SLEEP", 30), step=5,
                           help="Giảm = nhanh hơn nhưng dễ bị rate limit 429")
        rl_s   = c2.slider("Nghỉ khi bị rate limit (giây)", 10, 300,
                           ei("RATE_LIMIT_SLEEP", 60), step=10,
                           help="Khi Google báo lỗi 429, chờ bao lâu trước khi thử lại")
        updates.update({"SUCCESS_SLEEP": str(succ_s), "RATE_LIMIT_SLEEP": str(rl_s)})

    with tabs[1]:
        st.info("Pipeline luôn dùng **3 bước**: Phân tích → Dịch → Kiểm tra.", icon="ℹ️")
        c1, c2, c3 = st.columns(3)
        pre_s  = c1.slider("Nghỉ trước khi dịch (s)",   0, 30, ei("PRE_CALL_SLEEP",  5))
        post_s = c2.slider("Nghỉ sau khi dịch (s)",     0, 30, ei("POST_CALL_SLEEP", 5))
        post_r = c3.number_input("Số lần kiểm tra lại", 0, 5,  ei("POST_CALL_MAX_RETRIES", 2))
        retry_q = st.toggle("Dịch lại khi phát hiện lỗi",
                            value=eb("TRANS_RETRY_ON_QUALITY", True),
                            help="Bước kiểm tra phát hiện lỗi dịch thuật → tự động dịch lại")
        max_ret   = st.number_input("Số lần thử lại tối đa", 1, 20, ei("MAX_RETRIES", 5))
        min_chars = st.number_input("Độ dài tối thiểu mỗi chương (ký tự)",
                                    0, 5000, ei("MIN_CHARS_PER_CHAPTER", 500), step=100)
        updates.update({
            "PRE_CALL_SLEEP": str(pre_s), "POST_CALL_SLEEP": str(post_s),
            "POST_CALL_MAX_RETRIES": str(post_r),
            "TRANS_RETRY_ON_QUALITY": "true" if retry_q else "false",
            "MAX_RETRIES": str(max_ret), "MIN_CHARS_PER_CHAPTER": str(min_chars),
        })

    with tabs[2]:
        st.markdown("Scout AI **đọc trước** các chương để hiểu ngữ cảnh — "
                    "giúp xưng hô và mạch truyện nhất quán hơn.")
        c1, c2, c3 = st.columns(3)
        scout_ev = c1.slider("Chạy Scout mỗi N chương",    1, 20, ei("SCOUT_REFRESH_EVERY", 5))
        scout_lb = c2.slider("Đọc lại N chương gần nhất",  2, 30, ei("SCOUT_LOOKBACK", 10))
        arc_win  = c3.slider("Giữ bộ nhớ N arc entry",     1, 10, ei("ARC_MEMORY_WINDOW", 3),
                             help="Số entry Arc Memory đưa vào prompt mỗi lần dịch")
        updates.update({"SCOUT_REFRESH_EVERY": str(scout_ev),
                        "SCOUT_LOOKBACK": str(scout_lb),
                        "ARC_MEMORY_WINDOW": str(arc_win)})

    with tabs[3]:
        suggest_on = st.toggle("Tự động phát hiện thuật ngữ mới",
                               value=eb("SCOUT_SUGGEST_GLOSSARY", True),
                               help="Scout đề xuất thuật ngữ mới vào Staging sau mỗi lần chạy")
        updates["SCOUT_SUGGEST_GLOSSARY"] = "true" if suggest_on else "false"
        c1, c2 = st.columns(2)
        min_conf  = c1.slider("Độ tin cậy tối thiểu", 0.0, 1.0,
                               ef("SCOUT_SUGGEST_MIN_CONFIDENCE", 0.7), step=0.05,
                               disabled=not suggest_on,
                               help="0.7 = cần khá chắc chắn. Tăng để ít đề xuất sai hơn.")
        max_terms = c2.number_input("Tối đa N thuật ngữ/lần", 1, 50,
                                    ei("SCOUT_SUGGEST_MAX_TERMS", 20),
                                    disabled=not suggest_on)
        updates.update({"SCOUT_SUGGEST_MIN_CONFIDENCE": str(round(min_conf, 2)),
                        "SCOUT_SUGGEST_MAX_TERMS": str(max_terms)})

    with tabs[4]:
        c1, c2 = st.columns(2)
        arch_a = c1.slider("Archive sau N chương vắng mặt", 10, 200,
                           ei("ARCHIVE_AFTER_CHAPTERS", 60), step=10,
                           help="Nhân vật không xuất hiện sau N chương → lưu trữ tự động")
        emo_r  = c2.slider("Reset cảm xúc sau N chương", 1, 20,
                           ei("EMOTION_RESET_CHAPTERS", 5),
                           help="Sau N chương, trạng thái tức giận/tổn thương tự reset về normal")
        updates.update({"ARCHIVE_AFTER_CHAPTERS": str(arch_a),
                        "EMOTION_RESET_CHAPTERS": str(emo_r)})

    with tabs[5]:
        st.markdown(
            "Bible System xây dựng **knowledge base toàn tác phẩm** (nhân vật, kỹ năng, "
            "địa danh, lore, plot threads) — giúp pipeline nhất quán khi dịch truyện dài."
        )
        st.info("Sau khi bật, chạy **Scan** trong tab 📖 Bible để xây dựng database.", icon="💡")

        bible_mode = st.toggle(
            "Bật Bible Mode",
            value=eb("BIBLE_MODE", False),
            help="Khi bật, pipeline dùng Bible data thay vì context file riêng lẻ",
        )
        updates["BIBLE_MODE"] = "true" if bible_mode else "false"

        st.divider()
        c1, c2, c3 = st.columns(3)
        depth_opts = ["quick","standard","deep"]
        cur_depth  = e("BIBLE_SCAN_DEPTH","standard")
        depth_idx  = depth_opts.index(cur_depth) if cur_depth in depth_opts else 1
        depth_sel  = c1.selectbox(
            "Độ sâu scan", depth_opts, index=depth_idx,
            format_func=lambda x: {"quick":"Quick — nhanh, chỉ entity",
                                   "standard":"Standard — đầy đủ ✓",
                                   "deep":"Deep — kỹ nhất, chậm nhất"}[x],
            disabled=not bible_mode,
        )
        scan_batch = c2.number_input(
            "Consolidate sau N chương", 1, 20, ei("BIBLE_SCAN_BATCH", 5),
            disabled=not bible_mode,
            help="Gộp kết quả scan vào database sau mỗi N chương",
        )
        scan_sleep = c3.number_input(
            "Nghỉ giữa chương scan (s)", 0, 60, ei("BIBLE_SCAN_SLEEP", 10),
            disabled=not bible_mode,
        )
        cross_ref = st.toggle(
            "Chạy cross-reference sau scan",
            value=eb("BIBLE_CROSS_REF", True),
            disabled=not bible_mode,
            help="Tự động kiểm tra mâu thuẫn cốt truyện sau khi scan xong",
        )
        updates.update({
            "BIBLE_SCAN_DEPTH": depth_sel,
            "BIBLE_SCAN_BATCH": str(scan_batch),
            "BIBLE_SCAN_SLEEP": str(scan_sleep),
            "BIBLE_CROSS_REF" : "true" if cross_ref else "false",
        })

    with tabs[6]:
        st.markdown("Giới hạn token gửi cho AI. Tăng nếu bị cắt nội dung, giảm nếu lỗi token limit.")
        budget = st.number_input(
            "Giới hạn token (0 = tắt)", min_value=0, step=10000,
            value=ei("BUDGET_LIMIT", 150000),
            help="Thường để 150000. Gemini 2.5 Pro hỗ trợ đến 1M token.",
        )
        updates["BUDGET_LIMIT"] = str(budget)

    with tabs[7]:
        c1, c2, c3 = st.columns(3)
        imm = c1.toggle("Merge ngay sau mỗi chương",       value=eb("IMMEDIATE_MERGE", True),
                        help="Cập nhật nhân vật/từ điển ngay sau mỗi chương. Khuyến nghị bật.")
        ag  = c2.toggle("Tự động phân loại thuật ngữ cuối", value=eb("AUTO_MERGE_GLOSSARY", False))
        ac  = c3.toggle("Tự động merge nhân vật cuối",      value=eb("AUTO_MERGE_CHARACTERS", False))
        rfp = st.number_input("Thử lại chương lỗi N lần cuối pipeline",
                              0, 10, ei("RETRY_FAILED_PASSES", 3))
        updates.update({
            "IMMEDIATE_MERGE"    : "true" if imm else "false",
            "AUTO_MERGE_GLOSSARY": "true" if ag  else "false",
            "AUTO_MERGE_CHARACTERS": "true" if ac else "false",
            "RETRY_FAILED_PASSES": str(rfp),
        })

    with tabs[8]:
        st.info("Data của mỗi truyện tự động lưu trong `outputs/<TênTruyện>/data/`. "
                "Chỉ cần đặt file chương vào `inputs/<TênTruyện>/`.", icon="ℹ️")
        for key, default, desc in [
            ("INPUT_DIR",   "inputs",  "Thư mục chứa file chương gốc tiếng Anh"),
            ("OUTPUT_DIR",  "outputs", "Thư mục lưu bản dịch + data nhân vật/từ điển"),
            ("PROMPTS_DIR", "prompts", "Thư mục các file hướng dẫn cho AI (system_agent.md, ...)"),
        ]:
            val = st.text_input(f"`{key}`", value=e(key, default), help=desc)
            updates[key] = val

    if save_clicked:
        try:
            _save_env({k: v for k, v in updates.items() if v is not None})
            load_stats.clear()
            S.settings_saved = True
        except Exception as exc:
            st.error(f"❌ Lỗi khi lưu: {exc}")
        else:
            st.rerun()

    if reset_clicked:
        st.rerun()
