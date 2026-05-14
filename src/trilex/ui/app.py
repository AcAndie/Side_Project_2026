"""TriLex Streamlit entrypoint.

Run with:
    streamlit run src/trilex/ui/app.py

Multi-page layout: Streamlit auto-discovers `pages/*.py` next to this file.
"""

from __future__ import annotations

import streamlit as st

from trilex.ui._helpers import db_ready, sidebar_project_selector

st.set_page_config(
    page_title="TriLex",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    sidebar_project_selector()

    st.title("🌳 TriLex")
    st.caption(
        "QuickTranslator-style ZH→VN/EN engine with AI polish layer + Obsidian vault output."
    )

    if not db_ready():
        st.warning(
            "Cơ sở dữ liệu chưa khởi tạo. Mở terminal và chạy:\n\n"
            "```bash\n"
            "trilex db init\n"
            "```\n\n"
            "Sau đó reload trang."
        )
        return

    st.markdown("""
### Hướng dẫn nhanh

1. **Library** — tạo project mới (tên, slug, source/target lang, genre).
2. **Translate** — paste 1 chương ZH/EN, chọn mode, click *Translate Now*.
3. **Jobs** — theo dõi tiến độ các tác vụ dài.
4. **Dictionary** — quản lý các file QT (`VietPhrase.txt`, `Names.txt`, ...).
5. **Glossary** — chỉnh sửa thuật ngữ khoá per-novel.
6. **Settings** — kiểm tra config & API key đã load.
        """)

    st.divider()
    st.subheader("Trạng thái nhanh")
    cols = st.columns(3)
    cols[0].metric("DB", "ready", delta=None)
    try:
        from trilex.config import get_settings, mask_key

        s = get_settings()
        masked = mask_key(s.gemini_api_key.get_secret_value())
        cols[1].metric("Gemini key", masked)
        cols[2].metric("Model", s.gemini_model)
    except Exception as e:  # noqa: BLE001
        cols[1].metric("Gemini key", "—")
        cols[2].metric("Model", "—")
        st.warning(f"Settings: {e}")


if __name__ == "__main__":
    main()
