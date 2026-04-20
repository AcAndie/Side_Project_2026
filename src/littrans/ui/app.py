"""
src/littrans/ui/app.py — LiTTrans Web UI (Streamlit) v5.6

Sửa lỗi so với v5.5:
  [BUG-1] st.markdown() không chấp nhận help= → xóa tham số này
  [BUG-2] pipeline.py: `from ... import build as build_prompt` → build() đã bị xóa ở v5.5
          → ghi chú trong patches_v2.py
  [BUG-3] st.tabs lồng nhau quá sâu trong _char_card → dùng expander thay thế

Chức năng thiếu so với CLI đã được bổ sung:
  [FEAT-1] Characters page: nút Merge Staging, Validate, Export báo cáo
  [FEAT-2] Settings: tab Bible System (BIBLE_MODE, depth, batch, sleep, crossref)
  [FEAT-3] Xem chương: hiển thị chi tiết vi phạm Name Lock
  [FEAT-4] Settings: KEY_ROTATE_THRESHOLD
  [FEAT-5] Sidebar: badge nhân vật chờ merge

Cache keys: load_stats/load_characters/load_glossary_data nhận novel_name
→ tránh data cũ khi đổi novel
"""
from __future__ import annotations

import html
import queue
import re
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
for _p in [str(_ROOT), str(_ROOT / "src")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st
from littrans.ui.bible_ui     import render_bible_tab   as render_bible
from littrans.ui.epub_ui      import render_epub_tab    as render_epub
from littrans.ui.scraper_page  import render_scraper
from littrans.ui.pipeline_page import render_pipeline
import streamlit.components.v1 as components

st.set_page_config(
    page_title="LiTTrans — Dịch Truyện Tự Động",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state ─────────────────────────────────────────────────
_DEFAULTS: dict[str, Any] = {
    "page"                  : "translate",
    "running"               : False,
    "run_thread"            : None,
    "log_q"                 : None,
    "logs"                  : [],
    "rt_running"            : False,
    "rt_thread"             : None,
    "rt_q"                  : None,
    "rt_logs"               : [],
    "sel_ch"                : 0,
    "show_rt"               : False,
    "clean_running"         : False,
    "clean_q"               : None,
    "clean_logs"            : [],
    # [FEAT-1] character actions
    "chars_action_running"  : False,
    "chars_action_q"        : None,
    "chars_action_logs"     : [],
    "settings_saved"        : False,
    "current_novel"         : "",
    "bible_scan_running"    : False,
    "bible_scan_q"          : None,
    "bible_scan_logs"       : [],
    "bible_crossref_running": False,
    "bible_crossref_q"      : None,
    "bible_crossref_logs"   : [],
    "bible_export_done"     : False,
    "epub_running"          : False,
    "epub_q"                : None,
    "epub_logs"             : [],
    "last_export_file"      : None,
    # EPUB Export
    "epub_export_bytes" : None,
    "epub_export_novel" : "",
    # Pipeline
    "pipeline_running"  : False,
    "pipeline_q"        : None,
    "pipeline_logs"     : [],
    "pipeline_stage"    : 0,
    "_pl_mode"          : "",
    "_pl_novel_name"    : "",
    "_pl_result_holder" : [],
    "_pl_epub_path"     : "",
    # Scraper
    "scraper_running"           : False,
    "scraper_q"                 : None,
    "scraper_logs"              : [],
    "scraper_result"            : None,
    "_scraper_result_holder"    : [],
    "_scraper_novel_name"       : "",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v
S = st.session_state

# ── CSS ───────────────────────────────────────────────────────────
st.markdown("""<style>
.badge{display:inline-block;font-size:11px;font-weight:600;padding:2px 8px;border-radius:99px;margin:1px}
.badge-ok  {background:#EAF3DE;color:#3B6D11}
.badge-warn{background:#FAEEDA;color:#633806}
.badge-err {background:#FCEBEB;color:#791F1F}
.badge-info{background:#E6F1FB;color:#0C447C}
.badge-dim {background:#F1EFE8;color:#444441}
.strong-lock{color:#3B6D11;font-size:11px}
.weak-lock  {color:#BA7517;font-size:11px}
.welcome-card{background:linear-gradient(135deg,#EEEDFE 0%,#E6F1FB 100%);
  border-radius:16px;padding:32px;margin-bottom:24px;border:1px solid #d0cef8}
.step-card{background:white;border-radius:12px;padding:20px;border:1px solid #e8e8e8;height:100%}
.step-num{width:32px;height:32px;border-radius:50%;background:#3C3489;color:white;
  display:inline-flex;align-items:center;justify-content:center;
  font-weight:700;font-size:14px;margin-bottom:8px}
</style>""", unsafe_allow_html=True)

# ── .env helpers ──────────────────────────────────────────────────
_ENV_PATH = _ROOT / ".env"

def _load_env() -> dict[str, str]:
    try:
        from dotenv import dotenv_values
        return {k: (v or "") for k, v in dotenv_values(str(_ENV_PATH)).items()}
    except Exception:
        return {}

def _save_env(updates: dict[str, str]) -> None:
    try:
        from dotenv import set_key
        if not _ENV_PATH.exists():
            _ENV_PATH.write_text("")
        for k, v in updates.items():
            set_key(str(_ENV_PATH), k, v)
    except Exception as exc:
        raise RuntimeError(f"Không thể lưu .env: {exc}") from exc

def _has_api_key() -> bool:
    return bool(_load_env().get("GEMINI_API_KEY", "").strip())


# ── Novel helpers ─────────────────────────────────────────────────

def _get_available_novels() -> list[str]:
    try:
        from littrans.config.settings import get_available_novels
        return get_available_novels()
    except Exception:
        inp = _ROOT / "inputs"
        if not inp.exists():
            return []
        return sorted([
            d.name for d in inp.iterdir()
            if d.is_dir() and not d.name.startswith(".")
            and any(f.suffix in (".txt", ".md") for f in d.iterdir())
        ])

def _apply_novel(name: str) -> None:
    from littrans.config.settings import set_novel
    set_novel(name)
    for fn in [load_chapters, load_stats, load_characters, load_glossary_data]:
        fn.clear()


# ── Cached loaders ────────────────────────────────────────────────

@st.cache_data(ttl=10)
def load_chapters(novel_name: str = "") -> list[dict]:
    try:
        from littrans.config.settings import settings
        input_dir  = settings.active_input_dir
        output_dir = settings.active_output_dir
    except Exception:
        input_dir  = _ROOT / "inputs"  / novel_name if novel_name else _ROOT / "inputs"
        output_dir = _ROOT / "outputs" / novel_name if novel_name else _ROOT / "outputs"
    if not input_dir.exists():
        return []
    files = sorted(
        [f for f in input_dir.iterdir() if f.suffix in (".txt", ".md")],
        key=lambda s: [int(t) if t.isdigit() else t.lower()
                       for t in re.split(r"(\d+)", s.name)],
    )
    result = []
    for i, fp in enumerate(files):
        vn_path = output_dir / f"{fp.stem}_VN.txt"
        result.append({
            "idx": i, "name": fp.name, "path": fp,
            "size": f"{fp.stat().st_size // 1024} KB",
            "vn_path": vn_path, "done": vn_path.exists(),
        })
    return result


@st.cache_data(ttl=30)
def load_chapter_content(path_str: str, vn_path_str: str, done: bool) -> dict[str, str]:
    raw = vn = ""
    try:    raw = Path(path_str).read_text(encoding="utf-8", errors="replace")
    except: pass
    if done:
        try:    vn = Path(vn_path_str).read_text(encoding="utf-8", errors="replace")
        except: pass
    return {"raw": raw, "vn": vn}


@st.cache_data(ttl=4)
def load_characters(novel_name: str = "") -> dict[str, dict]:
    try:
        from littrans.context.characters import load_active, load_archive
        return {
            "active" : load_active().get("characters", {}),
            "archive": load_archive().get("characters", {}),
        }
    except Exception:
        return {"active": {}, "archive": {}}


@st.cache_data(ttl=4)
def load_glossary_data(novel_name: str = "") -> dict[str, list[tuple[str, str]]]:
    try:
        from littrans.context.glossary import _load_all
        raw = _load_all()
    except Exception:
        return {}
    result: dict[str, list] = {}
    for cat, terms in raw.items():
        entries = []
        for _, line in terms.items():
            clean = re.sub(r"^[\*\-\+]\s*", "", line.strip())
            if ":" in clean and not clean.startswith("#"):
                eng, _, vn = clean.partition(":")
                if eng.strip():
                    entries.append((eng.strip(), vn.strip()))
        if entries:
            result[cat] = entries
    return result


@st.cache_data(ttl=5)
def load_stats(novel_name: str = "") -> dict:
    try:
        from littrans.context.characters import character_stats
        from littrans.context.glossary   import glossary_stats
        from littrans.context.skills     import skills_stats
        from littrans.context.name_lock  import lock_stats
        return {
            "chars" : character_stats(),
            "glos"  : glossary_stats(),
            "skills": skills_stats(),
            "lock"  : lock_stats(),
        }
    except Exception:
        return {"chars": {}, "glos": {}, "skills": {}, "lock": {}}


# ── HTML viewers ──────────────────────────────────────────────────

def _paras_to_html(text: str) -> str:
    paras = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    if not paras:
        return "<p style='color:#999;font-style:italic'>Không có nội dung.</p>"
    return "".join(
        f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in paras
    )


def split_view(raw: str, vn: str, height: int = 520) -> None:
    rh, vh = _paras_to_html(raw), _paras_to_html(vn)
    components.html(f"""<!DOCTYPE html><html><head><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px;background:transparent}}
.wrap{{display:flex;height:{height}px;border:0.5px solid #e0e0e0;border-radius:8px;overflow:hidden}}
.pane{{flex:1;overflow-y:auto;padding:14px 18px;line-height:1.85;color:#1a1a1a}}
.pane+.pane{{border-left:0.5px solid #e0e0e0}}
.lbl{{font-size:10px;font-weight:600;letter-spacing:.08em;color:#aaa;margin-bottom:12px;text-transform:uppercase}}
p{{margin-bottom:10px}}p:last-child{{margin:0}}
@media(prefers-color-scheme:dark){{.pane{{color:#ddd;background:#0e1117}}.wrap,.pane+.pane{{border-color:#2a2a2a}}}}
</style></head><body>
<div class="wrap">
  <div class="pane" id="L"><div class="lbl">Bản gốc (EN)</div>{rh}</div>
  <div class="pane" id="R"><div class="lbl">Bản dịch (VN)</div>{vh}</div>
</div>
<script>
var L=document.getElementById('L'),R=document.getElementById('R'),busy=false;
L.addEventListener('scroll',function(){{if(busy)return;busy=true;
  var r=L.scrollTop/Math.max(1,L.scrollHeight-L.clientHeight);
  R.scrollTop=r*(R.scrollHeight-R.clientHeight);
  setTimeout(function(){{busy=false;}},60);}});
R.addEventListener('scroll',function(){{if(busy)return;busy=true;
  var r=R.scrollTop/Math.max(1,R.scrollHeight-R.clientHeight);
  L.scrollTop=r*(L.scrollHeight-L.clientHeight);
  setTimeout(function(){{busy=false;}},60);}});
</script></body></html>""", height=height + 6, scrolling=False)


def diff_view(raw: str, vn: str, height: int = 520) -> None:
    import difflib
    raw_p = [p.strip() for p in raw.replace("\r\n","\n").split("\n\n") if p.strip()]
    vn_p  = [p.strip() for p in vn.replace("\r\n", "\n").split("\n\n") if p.strip()]
    ops   = difflib.SequenceMatcher(None, raw_p, vn_p, autojunk=False).get_opcodes()
    ta: dict[int,str] = {}; tb: dict[int,str] = {}
    for tag, i1, i2, j1, j2 in ops:
        if tag == "replace":
            for i in range(i1, i2): ta[i] = "chg"
            for j in range(j1, j2): tb[j] = "chg"
        elif tag == "delete":
            for i in range(i1, i2): ta[i] = "del"
        elif tag == "insert":
            for j in range(j1, j2): tb[j] = "add"

    def _r(paras: list, tags: dict) -> str:
        out = []
        for i, p in enumerate(paras):
            t = tags.get(i, "")
            esc = html.escape(p).replace(chr(10), "<br>")
            cls = f' class="{t}"' if t else ""
            out.append(f"<p{cls}>{esc}</p>")
        return "".join(out) or "<p style='color:#999'>—</p>"

    components.html(f"""<!DOCTYPE html><html><head><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px}}
.wrap{{display:flex;height:{height}px;border:0.5px solid #e0e0e0;border-radius:8px;overflow:hidden}}
.pane{{flex:1;overflow-y:auto;padding:14px 18px;line-height:1.85;color:#1a1a1a}}
.pane+.pane{{border-left:0.5px solid #e0e0e0}}
.lbl{{font-size:10px;font-weight:600;letter-spacing:.08em;color:#aaa;margin-bottom:12px;text-transform:uppercase}}
p{{margin-bottom:10px}}p:last-child{{margin:0}}
.add{{background:rgba(99,153,34,.13);border-left:2px solid #639922;padding-left:8px;margin-left:-10px}}
.del{{background:rgba(163,45,45,.08);border-left:2px solid #A32D2D;padding-left:8px;
  margin-left:-10px;opacity:.5;text-decoration:line-through}}
.chg{{background:rgba(133,79,11,.1);border-left:2px solid #EF9F27;padding-left:8px;margin-left:-10px}}
@media(prefers-color-scheme:dark){{.pane{{color:#ddd;background:#0e1117}}.wrap,.pane+.pane{{border-color:#2a2a2a}}}}
</style></head><body>
<div class="wrap">
  <div class="pane"><div class="lbl">Bản gốc (EN)</div>{_r(raw_p, ta)}</div>
  <div class="pane"><div class="lbl">Bản dịch (VN)</div>{_r(vn_p, tb)}</div>
</div></body></html>""", height=height + 6, scrolling=False)


# ── Queue polling ─────────────────────────────────────────────────

def _poll(q_key: str, logs_key: str, thread_key: str | None = None) -> bool:
    q: queue.Queue | None = S.get(q_key)
    if q is None:
        return False
    done = False
    while True:
        try:
            msg = q.get_nowait()
            if msg == "__DONE__":
                done = True
            else:
                S[logs_key].append(msg)
        except queue.Empty:
            break
    if not done and thread_key:
        t = S.get(thread_key)
        if t is not None and not t.is_alive():
            S[logs_key].append("⚠️  Thread dừng bất ngờ.")
            done = True
    return done


def _show_log(logs: list[str]) -> None:
    st.code("\n".join(logs[-300:]) if logs else "(chờ log...)", language=None)


# ══════════════════════════════════════════════════════════════════
# WELCOME SCREEN
# ══════════════════════════════════════════════════════════════════

def render_welcome() -> None:
    st.markdown("""
    <div class="welcome-card">
        <h2 style="margin:0 0 8px 0">👋 Chào mừng đến với LiTTrans!</h2>
        <p style="color:#555;margin:0;font-size:15px">
            Dịch truyện LitRPG / Tu Tiên tự động từ tiếng Anh sang tiếng Việt.<br>
            Nhất quán tên nhân vật, xưng hô và kỹ năng từ đầu đến cuối.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Bắt đầu trong 3 bước")
    c1, c2, c3 = st.columns(3)
    _steps = [
        (c1, "1", "🔑 Lấy API Key",
         "Truy cập <b>aistudio.google.com</b>, đăng nhập Google → "
         "<b>Get API key → Create API key</b>.<br><br>Miễn phí, không cần thẻ tín dụng."),
        (c2, "2", "⚙️ Nhập API Key bên dưới",
         "Dán key vào ô bên dưới và nhấn <b>Lưu & bắt đầu</b>.<br><br>"
         "Key có dạng <code>AIzaSy...</code>"),
        (c3, "3", "📄 Upload chương và dịch",
         "Vào tab <b>📄 Dịch</b>, upload file <code>.txt</code>/<code>.md</code>, "
         "nhấn <b>▶ Dịch</b>."),
    ]
    for col, num, title, body in _steps:
        with col:
            st.markdown(f"""<div class="step-card">
                <div class="step-num">{num}</div>
                <h4>{title}</h4>
                <p style="color:#555;font-size:13px">{body}</p>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Nhập Gemini API Key")
    st.markdown("[Lấy miễn phí tại aistudio.google.com →](https://aistudio.google.com)")

    col_key, col_btn = st.columns([4, 1])
    api_key = col_key.text_input("API Key", type="password",
                                  placeholder="AIzaSy...", label_visibility="collapsed")
    if col_btn.button("💾 Lưu & bắt đầu", type="primary", use_container_width=True):
        if not api_key.strip():
            st.error("Vui lòng nhập API Key.")
        elif not api_key.strip().startswith("AIza"):
            st.warning("⚠️  Key thường bắt đầu bằng 'AIza...' — kiểm tra lại.")
        else:
            try:
                _save_env({"GEMINI_API_KEY": api_key.strip()})
                st.success("✅ Đã lưu! Đang tải lại...")
                time.sleep(1); st.rerun()
            except Exception as e:
                st.error(f"Không thể lưu: {e}")

    with st.expander("💡 Câu hỏi thường gặp"):
        st.markdown("""
**Miễn phí không?** Gói miễn phí đủ dịch 30–50 chương/ngày. Không cần thẻ tín dụng.

**Dữ liệu an toàn không?** API Key lưu trong file `.env` trên máy bạn, không chia sẻ với ai.

**Cần biết lập trình không?** Không. Giao diện web, thao tác bằng nút bấm.

**Hỗ trợ file nào?** `.txt` và `.md`. File `.epub` → dùng tab **📚 EPUB** để chuyển trước.
        """)


# ══════════════════════════════════════════════════════════════════
# PAGE: DỊCH
# ══════════════════════════════════════════════════════════════════

def render_translate() -> None:
    chapters = load_chapters(S.current_novel)
    done  = sum(1 for c in chapters if c["done"])
    total = len(chapters)

    st.subheader("📄 Dịch chương")

    # BUG-1 FIX: st.markdown không có help=, dùng st.caption thay thế
    with st.expander("📁 Upload file chương (.txt / .md)", expanded=not chapters):
        st.caption("Đặt tên theo thứ tự: `chapter_001.txt`, `chapter_002.txt`, ...")
        uploaded = st.file_uploader("Chọn file", type=["txt", "md"],
                                    accept_multiple_files=True, label_visibility="collapsed")
        if uploaded:
            try:
                from littrans.config.settings import settings as cfg
                inp = cfg.active_input_dir
            except Exception:
                novel = S.current_novel
                inp = _ROOT / "inputs" / novel if novel else _ROOT / "inputs"
            inp.mkdir(parents=True, exist_ok=True)
            for f in uploaded:
                (inp / f.name).write_bytes(f.getvalue())
            st.success(f"✅ Đã lưu {len(uploaded)} file vào `{inp}`")
            load_chapters.clear(); st.rerun()

    if not chapters:
        st.info("**Chưa có chương nào.** Upload file ở trên, hoặc dùng tab **📚 EPUB** "
                "để chuyển file epub trước.")
        return

    st.progress(done / total,
                text=f"Tiến độ: {done}/{total} chương ({int(done/total*100)}%)")

    col_f1, col_f2, _ = st.columns([1, 1, 3])
    show_filter = col_f1.selectbox("Hiển thị", ["Tất cả", "Chưa dịch", "Đã dịch"],
                                   label_visibility="collapsed")
    if col_f2.button("↺ Làm mới danh sách"):
        load_chapters.clear(); st.rerun()

    filtered = chapters
    if show_filter == "Chưa dịch": filtered = [c for c in chapters if not c["done"]]
    elif show_filter == "Đã dịch":  filtered = [c for c in chapters if c["done"]]

    if filtered:
        h0, h1, h2, h3 = st.columns([0.4, 3, 0.8, 1.5])
        h0.caption("STT"); h1.caption("File")
        h2.caption("Kích thước"); h3.caption("Trạng thái")
        for ch in filtered:
            c0, c1, c2, c3 = st.columns([0.4, 3, 0.8, 1.5])
            c0.write(f"`{ch['idx']+1:03d}`")
            c1.write(ch["name"])
            c2.write(ch["size"])
            badge = "badge-ok" if ch["done"] else "badge-warn"
            label = "✅ Đã dịch" if ch["done"] else "⬜ Chưa dịch"
            c3.markdown(f'<span class="badge {badge}">{label}</span>', unsafe_allow_html=True)
    elif show_filter != "Tất cả":
        st.info(f"Không có chương nào ở trạng thái '{show_filter}'.")

    st.divider()

    pending = total - done
    col_btn, col_info = st.columns([1, 4])
    if not S.running:
        lbl = f"▶ Dịch {pending} chương" if pending > 0 else "▶ Dịch"
        if col_btn.button(lbl, type="primary", disabled=(not chapters or pending == 0)):
            S.logs = []; S.log_q = queue.Queue()
            from littrans.ui.runner import run_background
            S.run_thread = run_background(S.log_q, mode="run", novel_name=S.current_novel)
            S.running = True; st.rerun()
        if total and done == total:
            col_info.success("🎉 Tất cả chương đã được dịch xong!")
        elif total and pending > 0:
            col_info.info(f"💡 Còn {pending} chương chưa dịch. Nhấn nút để bắt đầu.")
    else:
        col_btn.button("⏹ Đang chạy…", disabled=True)
        col_info.warning("🔄 Pipeline đang chạy — đừng đóng cửa sổ.")

    if S.running or S.logs:
        if S.running:
            if _poll("log_q", "logs", "run_thread"):
                S.running = False
                S.logs.extend(["─" * 56, "✅ Pipeline hoàn tất."])
                load_chapters.clear(); load_stats.clear()
        with st.expander("📋 Nhật ký xử lý", expanded=S.running):
            _show_log(S.logs)
        if S.running:
            time.sleep(0.9); st.rerun()

    # ── EPUB Export ───────────────────────────────────────────────
    translated = [c for c in chapters if c["done"]]
    if translated and not S.running:
        st.divider()
        with st.expander("📖 Xuất EPUB", expanded=False):
            import io as _io
            st.caption(f"{len(translated)} chương đã dịch sẵn sàng xuất EPUB.")
            c1, c2 = st.columns(2)
            epub_title  = c1.text_input(
                "Tiêu đề", key="epub_exp_title",
                value=S.current_novel.replace("_", " ").title() if S.current_novel else "",
            )
            epub_author = c2.text_input("Tác giả", value="Unknown", key="epub_exp_author")

            if st.button("🔄 Tạo EPUB", key="epub_gen_btn"):
                try:
                    from littrans.tools.epub_exporter import (
                        export_to_epub, EpubExportMeta, get_translated_chapters,
                    )
                    chaps = get_translated_chapters(S.current_novel)
                    if not chaps:
                        st.error("Không tìm thấy file *_VN.txt trong outputs/")
                    else:
                        buf = _io.BytesIO()
                        export_to_epub(
                            chaps, buf,
                            EpubExportMeta(
                                title=epub_title or S.current_novel,
                                author=epub_author or "Unknown",
                            ),
                        )
                        S["epub_export_bytes"] = buf.getvalue()
                        S["epub_export_novel"] = S.current_novel
                        st.success(f"✅ EPUB từ {len(chaps)} chương. Nhấn Download bên dưới.")
                except Exception as _exc:
                    st.error(f"❌ Lỗi xuất EPUB: {_exc}")

            if S.get("epub_export_bytes") and S.get("epub_export_novel") == S.current_novel:
                fname = f"{S.current_novel or 'novel'}.epub"
                st.download_button(
                    "⬇️ Download EPUB",
                    data=S["epub_export_bytes"],
                    file_name=fname,
                    mime="application/epub+zip",
                    key="epub_dl_btn",
                )


# ══════════════════════════════════════════════════════════════════
# PAGE: XEM CHƯƠNG
# ══════════════════════════════════════════════════════════════════

def render_chapters() -> None:
    chapters = load_chapters(S.current_novel)
    if not chapters:
        st.info("**Chưa có chương nào.** Vào tab **📄 Dịch** để upload và dịch.")
        return

    col_list, col_view = st.columns([1, 3.2])
    with col_list:
        search = st.text_input("🔍", placeholder="Tìm chương…",
                               label_visibility="collapsed", key="ch_s")
        filtered = [c for c in chapters
                    if not search or search.lower() in c["name"].lower()]
        st.caption(f"{len(filtered)} / {len(chapters)} chương")
        for ch in filtered:
            icon   = "✅" if ch["done"] else "⬜"
            is_sel = ch["idx"] == S.sel_ch
            if st.button(f"{icon} {ch['name']}", key=f"chbtn_{ch['idx']}",
                         use_container_width=True,
                         type="primary" if is_sel else "secondary"):
                S.sel_ch = ch["idx"]; S.show_rt = False; S.rt_logs = []; st.rerun()

    with col_view:
        idx = min(S.sel_ch, len(chapters) - 1)
        _render_chapter_detail(chapters[idx])


def _render_chapter_detail(ch: dict) -> None:
    content = load_chapter_content(str(ch["path"]), str(ch["vn_path"]), ch["done"])
    raw, vn = content["raw"], content["vn"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("File", ch["name"])
    m2.metric("Kích thước", ch["size"])
    m3.metric("Bản dịch", "✅ Có" if ch["done"] else "❌ Chưa")

    # [FEAT-3] Name Lock check
    nl_violations: list[str] = []
    if ch["done"] and vn:
        try:
            from littrans.context.name_lock import build_name_lock_table, validate_translation
            nl_violations = validate_translation(vn, build_name_lock_table())
        except Exception:
            pass
    m4.metric("Name Lock", f"⚠️ {len(nl_violations)} vi phạm" if nl_violations else "✅ Ổn",
              help="Số lần tên nhân vật bị dịch không đúng theo bảng đã chốt")

    if nl_violations:
        with st.expander(f"🔒 {len(nl_violations)} vi phạm Name Lock", expanded=False):
            for w in nl_violations:
                st.markdown(f'<span class="badge badge-warn">{html.escape(w.strip())}</span>',
                            unsafe_allow_html=True)
            st.caption("Để sửa hàng loạt: `python scripts/main.py fix-names`")

    view_tabs = st.tabs(["🔀 Song song", "📄 Bản gốc", "🇻🇳 Bản dịch", "⚡ So sánh"])

    with view_tabs[0]:
        if not ch["done"]:
            st.info("Chưa có bản dịch.")
            if raw: st.text_area("", raw, height=420, disabled=True, label_visibility="collapsed")
        elif not raw: st.warning("Không đọc được file gốc.")
        else:         split_view(raw, vn)

    with view_tabs[1]:
        if raw: st.text_area("", raw, height=500, disabled=True, label_visibility="collapsed")
        else:   st.info("Không đọc được file gốc.")

    with view_tabs[2]:
        if ch["done"] and vn:
            st.text_area("", vn, height=500, disabled=True, label_visibility="collapsed")
            _, c2 = st.columns([1, 5])
            c2.download_button("⬇ Tải xuống bản dịch",
                               data=vn.encode("utf-8"),
                               file_name=f"{ch['path'].stem}_VN.txt",
                               mime="text/plain", key="dl_vn")
        elif not ch["done"]: st.info("Chưa có bản dịch.")
        else:                st.warning("Không đọc được file dịch.")

    with view_tabs[3]:
        if not ch["done"]:      st.info("Cần có bản dịch để so sánh.")
        elif not raw or not vn: st.warning("Thiếu nội dung.")
        else:
            st.caption("🟢 Đoạn thêm  🟡 Đoạn thay đổi  🔴 Đoạn bị xóa")
            diff_view(raw, vn)

    # Retranslate panel
    st.divider()
    rt_col, _ = st.columns([1, 5])
    if rt_col.button("✕ Đóng" if S.show_rt else "↺ Dịch lại chương này",
                     key="rt_toggle", type="secondary"):
        S.show_rt = not S.show_rt; S.rt_logs = []; st.rerun()

    if S.show_rt:
        with st.container(border=True):
            st.markdown(f"**↺ Dịch lại — `{ch['name']}`**")
            if ch["done"]:
                st.warning("⚠️  Bản dịch hiện tại sẽ bị **ghi đè**.")

            # defaults trước expander để luôn có giá trị
            update_data = False
            force_scout = False
            with st.expander("⚙️ Tùy chọn nâng cao", expanded=False):
                c1, c2 = st.columns(2)
                update_data = c1.checkbox("Cập nhật nhân vật/từ điển sau khi dịch",
                    help="Tự động cập nhật data nhân vật và thuật ngữ mới.")
                force_scout = c2.checkbox("Chạy Scout AI trước",
                    help="Scout đọc chương gần đây để cập nhật ngữ cảnh.")

            if not S.rt_running:
                if st.button("⚡ Xác nhận dịch lại", type="primary", key="rt_confirm"):
                    S.rt_logs = []; S.rt_q = queue.Queue()
                    from littrans.ui.runner import run_background
                    S.rt_thread = run_background(
                        S.rt_q, mode="retranslate", novel_name=S.current_novel,
                        filename=ch["name"], update_data=update_data,
                        force_scout=force_scout,
                        all_files=[c["name"] for c in load_chapters(S.current_novel)],
                        chapter_index=ch["idx"],
                    )
                    S.rt_running = True; st.rerun()
            else:
                st.info("⏳ Đang dịch lại…")

            if S.rt_running or S.rt_logs:
                if S.rt_running:
                    if _poll("rt_q", "rt_logs", "rt_thread"):
                        S.rt_running = False
                        S.rt_logs.extend(["─" * 56, "✅ Dịch lại hoàn tất."])
                        load_chapters.clear(); load_stats.clear()
                with st.expander("📋 Nhật ký", expanded=S.rt_running):
                    _show_log(S.rt_logs)
                if S.rt_running:
                    time.sleep(0.9); st.rerun()


# ══════════════════════════════════════════════════════════════════
# PAGE: NHÂN VẬT
# [FEAT-1] Action buttons: Merge, Validate, Export
# ══════════════════════════════════════════════════════════════════

def render_characters() -> None:
    chars_data = load_characters(S.current_novel)
    active  = chars_data["active"]
    archive = chars_data["archive"]

    # Staging count
    staging_n = 0
    try:
        from littrans.context.characters import has_staging_chars
        staging_n = has_staging_chars()
    except Exception:
        pass

    # Toolbar
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

        # BUG-3 FIX: dùng expander thay vì st.tabs lồng nhau
        st.caption(f"Tự xưng: **{pronoun_self}** · Cấp: **{level}**")
        if faction: st.caption(f"Phe: {faction}")
        if goal:    st.caption(f"Mục tiêu: {goal}")

        # Pronoun pairs (top 3)
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

        # Recent history (collapsed)
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


# ══════════════════════════════════════════════════════════════════
# PAGE: TỪ ĐIỂN
# ══════════════════════════════════════════════════════════════════

def render_glossary() -> None:
    import pandas as pd
    glos = load_glossary_data(S.current_novel)

    if not glos:
        st.info("**Từ điển trống.** Thuật ngữ tự thu thập khi dịch. "
                "Sau vài chương, nhấn **🔄 Phân loại** để sắp xếp vào đúng danh mục.")
        return

    staging_n = len(glos.get("staging", []))
    if staging_n:
        st.info(f"📖 **{staging_n} thuật ngữ mới** đang chờ phân loại. "
                "Nhấn **🔄 Phân loại** để AI sắp xếp vào đúng danh mục.")

    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
    sel_cat = c1.selectbox("Danh mục", ["Tất cả"] + list(glos.keys()),
                           label_visibility="collapsed", key="glos_cat")
    search  = c2.text_input("🔍", placeholder="Tìm thuật ngữ...",
                             label_visibility="collapsed", key="glos_q")
    with c3:
        if not S.clean_running:
            if st.button("🔄 Phân loại", disabled=not staging_n,
                         help="AI phân loại Staging vào đúng danh mục"):
                S.clean_logs = []; S.clean_q = queue.Queue()
                from littrans.ui.runner import run_background
                run_background(S.clean_q, mode="clean_glossary", novel_name=S.current_novel)
                S.clean_running = True; st.rerun()
        else:
            st.button("⏳ …", disabled=True, key="clean_busy")
    with c4:
        if st.button("↺ Làm mới", key="glos_refresh"):
            load_glossary_data.clear(); st.rerun()

    _cat_label = {"pathways":"Tu luyện","organizations":"Tổ chức","items":"Vật phẩm",
                  "locations":"Địa danh","general":"Chung","staging":"⏳ Chờ phân loại"}
    rows = []
    for cat, entries in glos.items():
        if sel_cat != "Tất cả" and cat != sel_cat: continue
        for eng, vn in entries:
            if search and search.lower() not in eng.lower() and search.lower() not in vn.lower():
                continue
            rows.append({"Tiếng Anh": eng, "Tiếng Việt": vn, "Danh mục": _cat_label.get(cat, cat)})

    if rows:
        st.caption(f"{len(rows)} thuật ngữ")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                     column_config={"Danh mục": st.column_config.TextColumn(width="small")})
    else:
        st.info("Không tìm thấy thuật ngữ nào.")

    if S.clean_running or S.clean_logs:
        if S.clean_running:
            if _poll("clean_q", "clean_logs"):
                S.clean_running = False
                S.clean_logs.append("✅ Phân loại hoàn tất.")
                load_glossary_data.clear(); load_stats.clear()
        with st.expander("📋 Nhật ký", expanded=S.clean_running):
            _show_log(S.clean_logs)
        if S.clean_running:
            time.sleep(0.9); st.rerun()


# ══════════════════════════════════════════════════════════════════
# PAGE: THỐNG KÊ
# ══════════════════════════════════════════════════════════════════

def render_stats() -> None:
    import pandas as pd
    s        = load_stats(S.current_novel)
    chapters = load_chapters(S.current_novel)
    done  = sum(1 for c in chapters if c["done"])
    total = len(chapters)

    st.subheader("📊 Tổng quan")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Chương đã dịch", f"{done} / {total}",
              delta=f"{int(done/total*100)}%" if total else None)
    m2.metric("Nhân vật theo dõi",  s["chars"].get("active",  0),
              help="Nhân vật xuất hiện gần đây")
    m3.metric("Nhân vật lưu trữ",   s["chars"].get("archive", 0),
              help="Tự động archive sau N chương vắng mặt")
    em = s["chars"].get("emotional", 0)
    m4.metric("Trạng thái đặc biệt", em,
              delta="cần chú ý" if em else None, delta_color="inverse",
              help="Tức giận / tổn thương / vừa thay đổi — ảnh hưởng lời thoại")

    st.divider()
    glos          = s.get("glos", {})
    total_terms   = sum(v for k, v in glos.items() if k != "staging")
    staging_terms = glos.get("staging", 0)
    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Thuật ngữ từ điển", total_terms)
    m6.metric("Chờ phân loại",     staging_terms,
              delta="→ Tab Từ điển" if staging_terms else None, delta_color="inverse")
    m7.metric("Kỹ năng đã biết",   s["skills"].get("total", 0))
    m8.metric("Tên đã chốt",        s["lock"].get("total_locked", 0),
              help="Name Lock — tên có bản dịch cố định, không thay đổi")

    chart_data = {k: v for k, v in glos.items() if v and k != "staging"}
    if chart_data:
        st.divider()
        st.markdown("**Phân bổ từ điển theo danh mục**")
        cat_vn = {"pathways":"Tu luyện","organizations":"Tổ chức",
                  "items":"Vật phẩm","locations":"Địa danh","general":"Chung"}
        df = pd.DataFrame.from_dict(
            {cat_vn.get(k, k): v for k, v in chart_data.items()},
            orient="index", columns=["Thuật ngữ"],
        )
        st.bar_chart(df, color="#3B6D11")

    if total:
        st.divider()
        st.progress(done / total, text=f"Tiến độ: {done}/{total} · {int(done/total*100)}%")
        rows = [{"Chương": c["name"],
                 "Trạng thái": "✅ Đã dịch" if c["done"] else "⬜ Chưa",
                 "Kích thước": c["size"]} for c in chapters]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════
# PAGE: CÀI ĐẶT
# [FEAT-2] Tab Bible System
# [FEAT-4] KEY_ROTATE_THRESHOLD
# ══════════════════════════════════════════════════════════════════

def render_settings() -> None:
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

    # ── Tab 0: Cơ bản ─────────────────────────────────────────────
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
        # [FEAT-4]
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

    # ── Tab 1: Pipeline ────────────────────────────────────────────
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

    # ── Tab 2: Scout AI ────────────────────────────────────────────
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

    # ── Tab 3: Từ điển auto ────────────────────────────────────────
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

    # ── Tab 4: Nhân vật ────────────────────────────────────────────
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

    # ── Tab 5: Bible System [FEAT-2] ──────────────────────────────
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

    # ── Tab 6: Token ───────────────────────────────────────────────
    with tabs[6]:
        st.markdown("Giới hạn token gửi cho AI. Tăng nếu bị cắt nội dung, giảm nếu lỗi token limit.")
        budget = st.number_input(
            "Giới hạn token (0 = tắt)", min_value=0, step=10000,
            value=ei("BUDGET_LIMIT", 150000),
            help="Thường để 150000. Gemini 2.5 Pro hỗ trợ đến 1M token.",
        )
        updates["BUDGET_LIMIT"] = str(budget)

    # ── Tab 7: Merge & Retry ───────────────────────────────────────
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

    # ── Tab 8: Đường dẫn ──────────────────────────────────────────
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

    # ── Save / Reset ───────────────────────────────────────────────
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


# ══════════════════════════════════════════════════════════════════
# SIDEBAR + MAIN
# ══════════════════════════════════════════════════════════════════

def _render_novel_selector() -> None:
    novels = _get_available_novels()
    if not novels:
        st.sidebar.caption("📁 **Một truyện** (flat mode)\n\n"
                           "_Tạo subfolder trong `inputs/` để quản lý nhiều truyện._")
        if S.current_novel:
            S.current_novel = ""; _apply_novel("")
        return

    current  = S.current_novel if S.current_novel in novels else novels[0]
    selected = st.sidebar.selectbox(
        "📚 Truyện đang chọn", novels,
        index=novels.index(current) if current in novels else 0,
        key="novel_selector_sb",
        help="Mỗi truyện có data riêng biệt (nhân vật, từ điển, bộ nhớ).",
    )
    if selected != S.current_novel:
        S.current_novel = selected; _apply_novel(selected)
        S.sel_ch = 0; S.logs = []; S.rt_logs = []; st.rerun()
    elif not S.current_novel:
        S.current_novel = selected; _apply_novel(selected)


def main() -> None:
    if not _has_api_key():
        with st.sidebar:
            st.markdown("## 📖 LiTTrans")
            st.caption("v5.6 — Thiết lập ban đầu")
        render_welcome()
        return

    with st.sidebar:
        st.markdown("## 📖 LiTTrans")
        st.caption("v5.6 — LitRPG / Tu Tiên Pipeline")
        st.divider()

        _render_novel_selector()
        st.divider()

        _pages = {
            "pipeline"  : "🚀 Pipeline",
            "scraper"   : "🌐 Cào Truyện",
            "translate" : "📄 Dịch",
            "chapters"  : "🔍 Xem chương",
            "characters": "👤 Nhân vật",
            "glossary"  : "📚 Từ điển",
            "stats"     : "📊 Thống kê",
            "settings"  : "⚙️ Cài đặt",
            "bible"     : "📖 Bible System",
            "epub"      : "📚 EPUB",
        }
        for key, label in _pages.items():
            if st.button(label, key=f"nav_{key}", use_container_width=True,
                         type="primary" if S.page == key else "secondary"):
                S.page = key; S.show_rt = False; st.rerun()

        st.divider()

        # Status strip
        try:
            chs   = load_chapters(S.current_novel)
            done  = sum(1 for c in chs if c["done"])
            total = len(chs)
            if total:
                st.progress(done / total)
                st.caption(f"{done}/{total} chương")
            elif S.current_novel:
                st.caption(f"📁 {S.current_novel} — chưa có chương")

            # Glossary staging badge
            try:
                from littrans.context.glossary import glossary_stats
                stg_n = glossary_stats().get("staging", 0)
                if stg_n:
                    st.markdown(
                        f'<span class="badge badge-warn">📖 {stg_n} thuật ngữ chờ phân loại</span>',
                        unsafe_allow_html=True,
                    )
            except Exception:
                pass

            # [FEAT-5] Character staging badge
            try:
                from littrans.context.characters import has_staging_chars
                sc = has_staging_chars()
                if sc:
                    st.markdown(
                        f'<span class="badge badge-info">👤 {sc} nhân vật chờ merge</span>',
                        unsafe_allow_html=True,
                    )
            except Exception:
                pass
        except Exception:
            pass

        # Running indicators
        for flag, msg in [
            (S.pipeline_running,     "🚀 Đang pipeline…"),
            (S.scraper_running,      "🌐 Đang cào…"),
            (S.running,              "🔄 Đang dịch…"),
            (S.rt_running,           "↺ Đang dịch lại…"),
            (S.clean_running,        "🔄 Đang phân loại…"),
            (S.chars_action_running, "👤 Đang xử lý nhân vật…"),
        ]:
            if flag:
                st.warning(msg)

        st.divider()
        if _has_api_key():
            st.caption("✅ API key đã cài đặt")
        else:
            st.caption("⚠️ Chưa có API key")
            if st.button("🔑 Cài đặt API Key", key="sidebar_setup"):
                S.page = "settings"; st.rerun()

    # Sync novel với settings singleton
    if S.current_novel:
        try:
            from littrans.config.settings import settings, set_novel
            if settings.novel_name != S.current_novel:
                set_novel(S.current_novel)
        except Exception:
            pass

    _route = {
        "pipeline"  : lambda: render_pipeline(S),
        "scraper"   : lambda: render_scraper(S),
        "translate" : render_translate,
        "chapters"  : render_chapters,
        "characters": render_characters,
        "glossary"  : render_glossary,
        "stats"     : render_stats,
        "settings"  : render_settings,
        "bible"     : lambda: render_bible(S),
        "epub"      : lambda: render_epub(S),
    }
    _route.get(S.page, render_translate)()


main()