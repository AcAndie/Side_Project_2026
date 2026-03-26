"""
src/littrans/ui/app.py — LiTTrans Web UI (Streamlit)

[v5.5] UX overhaul:
  - Welcome/onboarding screen for first-time users
  - Quick Setup in Settings (API key only, no tech jargon)
  - Fixed cache keys: load_stats/load_characters/load_glossary_data
    now include novel_name to prevent stale data on novel switch
  - Better empty states with step-by-step guidance
  - Contextual help throughout
  - Cleaner navigation labels

[Bug fixes]
  - load_stats/load_characters/load_glossary_data: add novel_name cache key
  - Regex mismatch in _record_violations fixed in pipeline.py (separate patch)
"""
from __future__ import annotations

import html
import queue
import re
import sys
import time
from pathlib import Path
from typing import Any

# ── Project root → sys.path ───────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[3]
for _p in [str(_ROOT), str(_ROOT / "src")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st
from littrans.ui.bible_ui import render_bible_tab as render_bible
from littrans.ui.epub_ui import render_epub_tab as render_epub
import streamlit.components.v1 as components

st.set_page_config(
    page_title="LiTTrans — Dịch Truyện Tự Động",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state ─────────────────────────────────────────────────
_DEFAULTS: dict[str, Any] = {
    "page"          : "translate",
    "running"       : False,
    "run_thread"    : None,
    "log_q"         : None,
    "logs"          : [],
    "rt_running"    : False,
    "rt_thread"     : None,
    "rt_q"          : None,
    "rt_logs"       : [],
    "sel_ch"        : 0,
    "show_rt"       : False,
    "clean_running" : False,
    "clean_q"       : None,
    "clean_logs"    : [],
    "settings_saved": False,
    "current_novel" : "",
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
    # UX state
    "show_advanced_settings": False,
    "onboarding_done"       : False,
    "last_export_file"      : None,   # for persistent download button
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

S = st.session_state

# ── CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Badges */
.badge { display:inline-block;font-size:11px;font-weight:600;padding:2px 8px;border-radius:99px;margin:1px; }
.badge-ok   { background:#EAF3DE;color:#3B6D11; }
.badge-warn { background:#FAEEDA;color:#633806; }
.badge-err  { background:#FCEBEB;color:#791F1F; }
.badge-info { background:#E6F1FB;color:#0C447C; }
.badge-dim  { background:#F1EFE8;color:#444441; }
.novel-pill { display:inline-block;background:#EEEDFE;color:#3C3489;font-size:12px;font-weight:600;padding:3px 10px;border-radius:99px; }
.strong-lock { color:#3B6D11;font-size:11px; }
.weak-lock   { color:#BA7517;font-size:11px; }

/* Welcome card */
.welcome-card {
    background: linear-gradient(135deg, #EEEDFE 0%, #E6F1FB 100%);
    border-radius: 16px;
    padding: 32px;
    margin-bottom: 24px;
    border: 1px solid #d0cef8;
}

/* Step card */
.step-card {
    background: white;
    border-radius: 12px;
    padding: 20px;
    border: 1px solid #e8e8e8;
    height: 100%;
}
.step-num {
    width: 32px; height: 32px;
    border-radius: 50%;
    background: #3C3489;
    color: white;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 14px;
    margin-bottom: 8px;
}

/* Progress step */
.progress-step-done   { color: #3B6D11; font-weight: 600; }
.progress-step-active { color: #3C3489; font-weight: 600; }
.progress-step-todo   { color: #aaa; }

/* Quick setup highlight */
.quick-setup-box {
    background: #FFF9F0;
    border: 2px solid #EF9F27;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)

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
    env = _load_env()
    return bool(env.get("GEMINI_API_KEY", "").strip())


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
    load_chapters.clear()
    load_stats.clear()
    load_characters.clear()
    load_glossary_data.clear()


# ── Cached data loaders (BUG FIX: novel_name as cache key for all) ─

@st.cache_data(ttl=10)
def load_chapters(novel_name: str = "") -> list[dict]:
    try:
        from littrans.config.settings import settings
        input_dir  = settings.active_input_dir
        output_dir = settings.active_output_dir
    except Exception:
        input_dir  = _ROOT / "inputs" / novel_name if novel_name else _ROOT / "inputs"
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
        base    = fp.stem
        vn_path = output_dir / f"{base}_VN.txt"
        result.append({
            "idx"    : i,
            "name"   : fp.name,
            "path"   : fp,
            "size"   : f"{fp.stat().st_size // 1024} KB",
            "vn_path": vn_path,
            "done"   : vn_path.exists(),
        })
    return result


@st.cache_data(ttl=30)
def load_chapter_content(path_str: str, vn_path_str: str, done: bool) -> dict[str, str]:
    raw = ""
    vn  = ""
    try:
        raw = Path(path_str).read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if done:
        try:
            vn = Path(vn_path_str).read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
    return {"raw": raw, "vn": vn}


@st.cache_data(ttl=4)
def load_characters(novel_name: str = "") -> dict[str, dict]:  # FIX: added novel_name
    try:
        from littrans.context.characters import load_active, load_archive
        return {
            "active" : load_active().get("characters", {}),
            "archive": load_archive().get("characters", {}),
        }
    except Exception:
        return {"active": {}, "archive": {}}


@st.cache_data(ttl=4)
def load_glossary_data(novel_name: str = "") -> dict[str, list[tuple[str, str]]]:  # FIX: added novel_name
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
def load_stats(novel_name: str = "") -> dict:  # FIX: added novel_name
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


# ── HTML viewer components ────────────────────────────────────────

def _paras_to_html(text: str) -> str:
    paras = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    if not paras:
        return "<p style='color:#999;font-style:italic'>Không có nội dung.</p>"
    return "".join(
        f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>"
        for p in paras
    )


def split_view(raw: str, vn: str, height: int = 520) -> None:
    raw_html = _paras_to_html(raw)
    vn_html  = _paras_to_html(vn)
    widget   = f"""<!DOCTYPE html><html><head><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px;background:transparent}}
.wrap{{display:flex;height:{height}px;border:0.5px solid #e0e0e0;border-radius:8px;overflow:hidden}}
.pane{{flex:1;overflow-y:auto;padding:14px 18px;line-height:1.85;color:#1a1a1a}}
.pane+.pane{{border-left:0.5px solid #e0e0e0}}
.lbl{{font-size:10px;font-weight:600;letter-spacing:.08em;color:#aaa;margin-bottom:12px;text-transform:uppercase}}
p{{margin-bottom:10px}}p:last-child{{margin:0}}
@media(prefers-color-scheme:dark){{body{{background:transparent}}.pane{{color:#ddd;background:#0e1117}}.wrap,.pane+.pane{{border-color:#2a2a2a}}}}
</style></head><body>
<div class="wrap">
  <div class="pane" id="L"><div class="lbl">Bản gốc (EN)</div>{raw_html}</div>
  <div class="pane" id="R"><div class="lbl">Bản dịch (VN)</div>{vn_html}</div>
</div>
<script>
var L=document.getElementById('L'),R=document.getElementById('R'),busy=false;
L.addEventListener('scroll',function(){{if(busy)return;busy=true;var r=L.scrollTop/Math.max(1,L.scrollHeight-L.clientHeight);R.scrollTop=r*(R.scrollHeight-R.clientHeight);setTimeout(function(){{busy=false;}},60);}});
R.addEventListener('scroll',function(){{if(busy)return;busy=true;var r=R.scrollTop/Math.max(1,R.scrollHeight-R.clientHeight);L.scrollTop=r*(L.scrollHeight-L.clientHeight);setTimeout(function(){{busy=false;}},60);}});
</script></body></html>"""
    components.html(widget, height=height + 6, scrolling=False)


def diff_view(raw: str, vn: str, height: int = 520) -> None:
    import difflib
    raw_p = [p.strip() for p in raw.replace("\r\n", "\n").split("\n\n") if p.strip()]
    vn_p  = [p.strip() for p in vn.replace("\r\n",  "\n").split("\n\n") if p.strip()]
    ops   = difflib.SequenceMatcher(None, raw_p, vn_p, autojunk=False).get_opcodes()
    tag_a: dict[int, str] = {}
    tag_b: dict[int, str] = {}
    for tag, i1, i2, j1, j2 in ops:
        if tag == "replace":
            for i in range(i1, i2): tag_a[i] = "chg"
            for j in range(j1, j2): tag_b[j] = "chg"
        elif tag == "delete":
            for i in range(i1, i2): tag_a[i] = "del"
        elif tag == "insert":
            for j in range(j1, j2): tag_b[j] = "add"
    def render(paras, tags):
        out = []
        for i, p in enumerate(paras):
            t = tags.get(i, "")
            esc = html.escape(p).replace(chr(10), "<br>")
            cls = f' class="{t}"' if t else ""
            out.append(f"<p{cls}>{esc}</p>")
        return "".join(out) or "<p style='color:#999'>—</p>"
    raw_html = render(raw_p, tag_a)
    vn_html  = render(vn_p,  tag_b)
    widget = f"""<!DOCTYPE html><html><head><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px}}
.wrap{{display:flex;height:{height}px;border:0.5px solid #e0e0e0;border-radius:8px;overflow:hidden}}
.pane{{flex:1;overflow-y:auto;padding:14px 18px;line-height:1.85;color:#1a1a1a}}
.pane+.pane{{border-left:0.5px solid #e0e0e0}}
.lbl{{font-size:10px;font-weight:600;letter-spacing:.08em;color:#aaa;margin-bottom:12px;text-transform:uppercase}}
p{{margin-bottom:10px}}p:last-child{{margin:0}}
.add{{background:rgba(99,153,34,.13);border-left:2px solid #639922;padding-left:8px;margin-left:-10px;border-radius:0 3px 3px 0}}
.del{{background:rgba(163,45,45,.08);border-left:2px solid #A32D2D;padding-left:8px;margin-left:-10px;opacity:.5;text-decoration:line-through}}
.chg{{background:rgba(133,79,11,.1);border-left:2px solid #EF9F27;padding-left:8px;margin-left:-10px;border-radius:0 3px 3px 0}}
@media(prefers-color-scheme:dark){{.pane{{color:#ddd;background:#0e1117}}.wrap,.pane+.pane{{border-color:#2a2a2a}}}}
</style></head><body>
<div class="wrap">
  <div class="pane"><div class="lbl">Bản gốc (EN)</div>{raw_html}</div>
  <div class="pane"><div class="lbl">Bản dịch (VN)</div>{vn_html}</div>
</div></body></html>"""
    components.html(widget, height=height + 6, scrolling=False)


# ── Queue polling + log display ───────────────────────────────────

def _poll(q_key: str, logs_key: str, thread_key: str | None = None) -> bool:
    q: queue.Queue | None = S.get(q_key)
    if q is None: return False
    done = False
    while True:
        try:
            msg = q.get_nowait()
            if msg == "__DONE__": done = True
            else: S[logs_key].append(msg)
        except queue.Empty:
            break
    if not done and thread_key:
        thread = S.get(thread_key)
        if thread is not None and not thread.is_alive():
            S[logs_key].append("⚠️  Background thread đã dừng bất ngờ.")
            done = True
    return done


def _show_log(logs: list[str], height: int = 200) -> None:
    st.code("\n".join(logs[-300:]) if logs else "(chờ log...)", language=None)


# ══════════════════════════════════════════════════════════════════
# WELCOME SCREEN — hiện khi chưa có API key
# ══════════════════════════════════════════════════════════════════

def render_welcome() -> None:
    """Hướng dẫn cài đặt lần đầu — chỉ hiện khi chưa có API key."""
    st.markdown("""
    <div class="welcome-card">
        <h2 style="margin:0 0 8px 0">👋 Chào mừng đến với LiTTrans!</h2>
        <p style="color:#555;margin:0;font-size:15px">
            Dịch truyện LitRPG / Tu Tiên tự động từ tiếng Anh sang tiếng Việt.<br>
            Nhất quán tên nhân vật, xưng hô và kỹ năng từ đầu đến cuối.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Bắt đầu trong 3 bước đơn giản")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("""
        <div class="step-card">
            <div class="step-num">1</div>
            <h4>🔑 Lấy API Key</h4>
            <p style="color:#555;font-size:13px">
                Truy cập <b>aistudio.google.com</b>, đăng nhập bằng tài khoản Google
                rồi nhấn <b>Get API key → Create API key</b>.
                <br><br>
                Miễn phí, không cần thẻ tín dụng.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div class="step-card">
            <div class="step-num">2</div>
            <h4>⚙️ Nhập API Key</h4>
            <p style="color:#555;font-size:13px">
                Dán API Key vào ô bên dưới và nhấn <b>Lưu</b>.
                <br><br>
                API Key có dạng <code>AIzaSy...</code>
            </p>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown("""
        <div class="step-card">
            <div class="step-num">3</div>
            <h4>📄 Upload chương và dịch</h4>
            <p style="color:#555;font-size:13px">
                Vào tab <b>📄 Dịch</b>, upload file <code>.txt</code> hoặc <code>.md</code>
                của các chương, rồi nhấn <b>▶ Chạy pipeline</b>.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Quick API key setup
    st.markdown("### Nhập API Key của bạn")
    st.markdown(
        "Chưa có API key? [Lấy miễn phí tại đây →](https://aistudio.google.com) "
        "(cần tài khoản Google)",
        unsafe_allow_html=False,
    )

    col_key, col_btn = st.columns([4, 1])
    api_key = col_key.text_input(
        "Gemini API Key",
        type="password",
        placeholder="AIzaSy...",
        label_visibility="collapsed",
        help="API key từ Google AI Studio. Bắt đầu bằng AIzaSy...",
    )
    if col_btn.button("💾 Lưu & bắt đầu", type="primary", use_container_width=True):
        if not api_key.strip():
            st.error("Vui lòng nhập API Key trước.")
        elif not api_key.strip().startswith("AIza"):
            st.warning("⚠️  API Key thường bắt đầu bằng 'AIza...'. Kiểm tra lại.")
        else:
            try:
                _save_env({"GEMINI_API_KEY": api_key.strip()})
                st.success("✅ Đã lưu! Đang khởi động lại...")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Không thể lưu: {e}")

    with st.expander("💡 Câu hỏi thường gặp"):
        st.markdown("""
**Miễn phí không?**
Gói miễn phí của Gemini API đủ để dịch 30–50 chương mỗi ngày. Không cần thẻ tín dụng.

**Dữ liệu có an toàn không?**
API Key được lưu trong file `.env` trên máy tính của bạn, không chia sẻ với bên thứ ba nào.

**Tôi cần biết lập trình không?**
Hoàn toàn không. LiTTrans có giao diện web đơn giản để thao tác bằng nút bấm.

**Hỗ trợ loại file nào?**
`.txt` và `.md`. Nếu có file `.epub`, dùng tab **📚 EPUB** để chuyển đổi trước.
        """)


# ══════════════════════════════════════════════════════════════════
# PAGE: DỊCH
# ══════════════════════════════════════════════════════════════════

def render_translate() -> None:
    chapters = load_chapters(S.current_novel)
    done  = sum(1 for c in chapters if c["done"])
    total = len(chapters)

    st.subheader("📄 Dịch chương")

    # ── Upload ─────────────────────────────────────────────────────
    with st.expander("📁 Upload file chương (.txt / .md)", expanded=not chapters):
        st.markdown(
            "Đặt tên file theo thứ tự để pipeline dịch đúng thứ tự: "
            "`chapter_001.txt`, `chapter_002.txt`, ...",
            help="File .txt hoặc .md chứa nội dung chương tiếng Anh cần dịch.",
        )
        uploaded = st.file_uploader(
            "Chọn file",
            type=["txt", "md"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
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
            st.success(f"✅ Đã lưu {len(uploaded)} file → `{inp}`")
            load_chapters.clear()
            st.rerun()

    # ── Empty state ────────────────────────────────────────────────
    if not chapters:
        st.markdown("---")
        st.info(
            "**Chưa có chương nào.** Upload file `.txt` hoặc `.md` vào ô trên để bắt đầu.\n\n"
            "Nếu có file `.epub`, hãy chuyển đổi trước bằng tab **📚 EPUB** ở menu bên trái."
        )
        return

    # ── Chapter list ───────────────────────────────────────────────
    if total:
        pct = done / total
        st.progress(pct, text=f"Tiến độ: {done}/{total} chương đã dịch ({int(pct*100)}%)")

    # Status filter
    col_f1, col_f2, _ = st.columns([1, 1, 3])
    show_filter = col_f1.selectbox(
        "Hiển thị",
        ["Tất cả", "Chưa dịch", "Đã dịch"],
        label_visibility="collapsed",
    )
    if col_f2.button("↺ Làm mới danh sách"):
        load_chapters.clear()
        st.rerun()

    filtered_chapters = chapters
    if show_filter == "Chưa dịch":
        filtered_chapters = [c for c in chapters if not c["done"]]
    elif show_filter == "Đã dịch":
        filtered_chapters = [c for c in chapters if c["done"]]

    if filtered_chapters:
        h0, h1, h2, h3 = st.columns([0.4, 3, 0.8, 1.5])
        h0.caption("STT"); h1.caption("File")
        h2.caption("Kích thước"); h3.caption("Trạng thái")
        for ch in filtered_chapters:
            c0, c1, c2, c3 = st.columns([0.4, 3, 0.8, 1.5])
            c0.write(f"`{ch['idx']+1:03d}`")
            c1.write(ch["name"])
            c2.write(ch["size"])
            if ch["done"]:
                c3.markdown('<span class="badge badge-ok">✅ Đã dịch</span>', unsafe_allow_html=True)
            else:
                c3.markdown('<span class="badge badge-warn">⬜ Chưa dịch</span>', unsafe_allow_html=True)
    elif show_filter != "Tất cả":
        st.info(f"Không có chương nào ở trạng thái '{show_filter}'.")

    st.divider()

    # ── Run pipeline ───────────────────────────────────────────────
    pending_count = total - done
    col_btn, col_info = st.columns([1, 4])

    if not S.running:
        btn_disabled = not chapters or pending_count == 0
        btn_help = (
            "Tất cả chương đã được dịch." if done == total and total > 0
            else "Nhấn để bắt đầu dịch tất cả chương chưa có bản dịch."
        )
        if col_btn.button(
            f"▶ Dịch {pending_count} chương" if pending_count > 0 else "▶ Dịch",
            type="primary",
            disabled=btn_disabled,
            help=btn_help,
        ):
            S.logs  = []
            S.log_q = queue.Queue()
            from littrans.ui.runner import run_background
            S.run_thread = run_background(S.log_q, mode="run", novel_name=S.current_novel)
            S.running = True
            st.rerun()
        if total and done == total:
            col_info.success("🎉 Tất cả chương đã được dịch xong!")
        elif total and pending_count > 0:
            col_info.info(f"💡 Còn {pending_count} chương chưa dịch. Nhấn nút để bắt đầu.")
    else:
        col_btn.button("⏹ Đang chạy…", disabled=True)
        col_info.warning("🔄 Pipeline đang chạy — đừng đóng cửa sổ. Có thể mất vài phút mỗi chương.")

    if S.running or S.logs:
        if S.running:
            done_flag = _poll("log_q", "logs", "run_thread")
            if done_flag:
                S.running = False
                S.logs.append("─" * 56)
                S.logs.append("✅ Pipeline hoàn tất.")
                load_chapters.clear()
                load_stats.clear()
        with st.expander("📋 Nhật ký xử lý", expanded=S.running):
            _show_log(S.logs)
        if S.running:
            time.sleep(0.9)
            st.rerun()


# ══════════════════════════════════════════════════════════════════
# PAGE: XEM CHƯƠNG
# ══════════════════════════════════════════════════════════════════

def render_chapters() -> None:
    chapters = load_chapters(S.current_novel)
    if not chapters:
        st.info(
            "**Chưa có chương nào.** Vào tab **📄 Dịch** để upload file và bắt đầu dịch."
        )
        return

    col_list, col_view = st.columns([1, 3.2])

    with col_list:
        search = st.text_input("🔍", placeholder="Tìm chương…",
                               label_visibility="collapsed", key="ch_s")
        filtered = [c for c in chapters
                    if not search or search.lower() in c["name"].lower()]
        st.caption(f"{len(filtered)} / {len(chapters)} chương")
        for ch in filtered:
            icon = "✅" if ch["done"] else "⬜"
            is_sel = (ch["idx"] == S.sel_ch)
            if st.button(f"{icon} {ch['name']}", key=f"chbtn_{ch['idx']}",
                         use_container_width=True,
                         type="primary" if is_sel else "secondary"):
                S.sel_ch  = ch["idx"]
                S.show_rt = False
                S.rt_logs = []
                st.rerun()

    with col_view:
        idx = S.sel_ch if S.sel_ch < len(chapters) else 0
        _render_chapter_detail(chapters[idx])


def _render_chapter_detail(ch: dict) -> None:
    content = load_chapter_content(str(ch["path"]), str(ch["vn_path"]), ch["done"])
    raw = content["raw"]
    vn  = content["vn"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("File", ch["name"])
    m2.metric("Kích thước", ch["size"])
    m3.metric("Bản dịch", "✅ Có" if ch["done"] else "❌ Chưa")
    nl_count = 0
    if ch["done"] and vn:
        try:
            from littrans.context.name_lock import build_name_lock_table, validate_translation
            nl_count = len(validate_translation(vn, build_name_lock_table()))
        except Exception:
            pass
    nl_label = f"⚠️ {nl_count} vi phạm" if nl_count else "✅ 0 vi phạm"
    m4.metric("Name Lock", nl_label, help="Số lần tên nhân vật bị dịch không đúng theo bảng đã chốt")

    tabs = st.tabs(["🔀 Song song", "📄 Bản gốc", "🇻🇳 Bản dịch", "⚡ So sánh"])

    with tabs[0]:
        if not ch["done"]:
            st.info("Chương này chưa có bản dịch. Vào tab **📄 Dịch** để dịch.")
            if raw:
                st.text_area("Bản gốc", raw, height=420, disabled=True, label_visibility="collapsed")
        elif not raw:
            st.warning("Không đọc được file gốc.")
        else:
            split_view(raw, vn)

    with tabs[1]:
        if raw:
            st.text_area("", raw, height=500, disabled=True, label_visibility="collapsed")
        else:
            st.info("Không đọc được file gốc.")

    with tabs[2]:
        if ch["done"] and vn:
            st.text_area("", vn, height=500, disabled=True, label_visibility="collapsed")
            c1, c2 = st.columns([1, 5])
            c2.download_button(
                "⬇ Tải xuống bản dịch",
                data=vn.encode("utf-8"),
                file_name=f"{ch['path'].stem}_VN.txt",
                mime="text/plain",
                key="dl_vn",
            )
        elif not ch["done"]:
            st.info("Chương chưa được dịch. Vào tab **📄 Dịch** để dịch.")
        else:
            st.warning("Không đọc được file dịch.")

    with tabs[3]:
        if not ch["done"]:
            st.info("Cần có bản dịch để xem so sánh.")
        elif not raw or not vn:
            st.warning("Thiếu nội dung để so sánh.")
        else:
            st.caption("🟢 Đoạn thêm vào  🟡 Đoạn thay đổi  🔴 Đoạn bị xóa")
            diff_view(raw, vn)

    # ── Retranslate panel ──────────────────────────────────────────
    st.divider()
    rt_col, _ = st.columns([1, 5])
    btn_label = "✕ Đóng" if S.show_rt else "↺ Dịch lại chương này"
    if rt_col.button(btn_label, key="rt_toggle", type="secondary"):
        S.show_rt = not S.show_rt
        S.rt_logs = []
        st.rerun()

    if S.show_rt:
        with st.container(border=True):
            st.markdown(f"**↺ Dịch lại — `{ch['name']}`**")
            if ch["done"]:
                st.warning("⚠️  Bản dịch hiện tại sẽ bị **ghi đè** sau khi dịch lại.")

            with st.expander("⚙️ Tùy chọn nâng cao", expanded=False):
                c1, c2 = st.columns(2)
                update_data = c1.checkbox(
                    "Cập nhật dữ liệu nhân vật/từ điển",
                    value=False,
                    help="Sau khi dịch lại, tự động cập nhật thông tin nhân vật và thuật ngữ mới.",
                )
                force_scout = c2.checkbox(
                    "Chạy Scout AI trước",
                    value=False,
                    help="Scout AI sẽ đọc các chương gần đây để cập nhật ngữ cảnh trước khi dịch lại.",
                )

            if not S.rt_running:
                if st.button("⚡ Xác nhận dịch lại", type="primary", key="rt_confirm"):
                    S.rt_logs = []
                    S.rt_q    = queue.Queue()
                    all_files_list = [c["name"] for c in load_chapters(S.current_novel)]
                    from littrans.ui.runner import run_background
                    S.rt_thread = run_background(
                        S.rt_q,
                        mode          = "retranslate",
                        novel_name    = S.current_novel,
                        filename      = ch["name"],
                        update_data   = update_data,
                        force_scout   = force_scout,
                        all_files     = all_files_list,
                        chapter_index = ch["idx"],
                    )
                    S.rt_running = True
                    st.rerun()
            else:
                st.info("⏳ Đang dịch lại…")

            if S.rt_running or S.rt_logs:
                if S.rt_running:
                    rt_done = _poll("rt_q", "rt_logs", "rt_thread")
                    if rt_done:
                        S.rt_running = False
                        S.rt_logs.append("─" * 56)
                        S.rt_logs.append("✅ Dịch lại hoàn tất.")
                        load_chapters.clear()
                        load_stats.clear()
                with st.expander("📋 Nhật ký", expanded=S.rt_running):
                    _show_log(S.rt_logs)
                if S.rt_running:
                    time.sleep(0.9)
                    st.rerun()


# ══════════════════════════════════════════════════════════════════
# PAGE: NHÂN VẬT
# ══════════════════════════════════════════════════════════════════

def render_characters() -> None:
    chars_data = load_characters(S.current_novel)
    active  = chars_data["active"]
    archive = chars_data["archive"]

    if not active and not archive:
        st.info(
            "**Chưa có nhân vật nào.** Dữ liệu nhân vật sẽ được tự động thu thập "
            "trong quá trình dịch. Hãy dịch ít nhất một chương trước."
        )
        return

    tab_a, tab_b = st.tabs([
        f"Đang theo dõi ({len(active)})",
        f"Lưu trữ ({len(archive)})",
    ])
    for tab, chars, label in [(tab_a, active, "active"), (tab_b, archive, "archive")]:
        with tab:
            if not chars:
                st.info(f"Không có nhân vật nào trong {label}.")
                continue
            search = st.text_input(
                "🔍", placeholder="Tìm tên nhân vật...",
                label_visibility="collapsed", key=f"cs_{label}",
            )
            filtered = {k: v for k, v in chars.items()
                        if not search or search.lower() in k.lower()}
            st.caption(f"{len(filtered)} nhân vật")
            cols = st.columns(3)
            for i, (name, profile) in enumerate(filtered.items()):
                with cols[i % 3]:
                    _char_card(name, profile)


def _char_card(name: str, p: dict) -> None:
    speech = p.get("speech", {})
    power  = p.get("power", {})
    ident  = p.get("identity", {})
    arc    = p.get("arc_status", {})
    em     = p.get("emotional_state", {})
    rels   = p.get("relationships", {})

    palettes = [
        ("#E1F5EE", "#085041"), ("#EEEDFE", "#3C3489"),
        ("#E6F1FB", "#0C447C"), ("#FAEEDA", "#633806"),
        ("#FCEBEB", "#791F1F"), ("#EAF3DE", "#3B6D11"),
    ]
    bg, fg   = palettes[sum(ord(c) for c in name) % len(palettes)]
    initials = "".join(w[0].upper() for w in name.split()[:2]) or name[:2].upper()

    state = em.get("current", "normal")
    em_map = {
        "angry"  : '<span class="badge badge-err">TỨC GIẬN</span>',
        "hurt"   : '<span class="badge badge-warn">TỔN THƯƠNG</span>',
        "changed": '<span class="badge badge-info">ĐÃ THAY ĐỔI</span>',
    }
    em_html = em_map.get(state, "")

    pronoun_self = speech.get("pronoun_self", "—")
    level        = power.get("current_level", "—")
    faction      = ident.get("faction", p.get("faction", ""))
    goal_raw     = arc.get("current_goal", "") if arc else ""
    goal         = goal_raw[:70] + "…" if len(goal_raw) > 70 else goal_raw
    history      = p.get("_history", [])

    with st.container(border=True):
        avatar_col, info_col = st.columns([1, 4])
        with avatar_col:
            st.markdown(
                f'<div style="width:38px;height:38px;border-radius:50%;'
                f'background:{bg};color:{fg};display:flex;align-items:center;'
                f'justify-content:center;font-size:13px;font-weight:600">'
                f'{initials}</div>', unsafe_allow_html=True,
            )
        with info_col:
            st.markdown(f"**{name}**")
            st.caption(p.get("role", "?"))
            if em_html:
                st.markdown(em_html, unsafe_allow_html=True)

        tab_profile, tab_history = st.tabs(["Thông tin", f"Lịch sử ({len(history)})"])

        with tab_profile:
            st.caption(f"Tự xưng: **{pronoun_self}** · Cấp: **{level}**")
            if faction: st.caption(f"Phe: {faction}")
            if goal:    st.caption(f"Mục tiêu: {goal}")
            for other, rel in list(rels.items())[:2]:
                dyn    = rel.get("dynamic", "")
                status = rel.get("pronoun_status", "weak")
                if not dyn: continue
                icon = "✓" if status == "strong" else "🔸"
                css  = "strong-lock" if status == "strong" else "weak-lock"
                st.markdown(
                    f'<span class="{css}">{icon} {name} ↔ {other}: <b>{dyn}</b></span>',
                    unsafe_allow_html=True,
                )

        with tab_history:
            _render_char_history(name, p)


def _render_char_history(name: str, p: dict) -> None:
    try:
        from littrans.context.char_history import get_log, get_log_rel, get_log_all_rels
    except ImportError:
        st.caption("Chưa có dữ liệu lịch sử.")
        return

    history = get_log(p, limit=30)
    if not history:
        st.caption("Chưa có lịch sử thay đổi nào.")
        return

    rel_options = ["Tất cả"] + list(p.get("relationships", {}).keys())
    sel_rel = st.selectbox(
        "Lọc theo quan hệ",
        rel_options,
        key=f"hist_rel_{name}",
        label_visibility="collapsed",
    )

    if sel_rel != "Tất cả":
        history = get_log_rel(p, sel_rel, limit=20)
        st.caption(f"{len(history)} thay đổi liên quan đến {sel_rel}")
    else:
        st.caption(f"{len(p.get('_history', []))} thay đổi · hiển thị {len(history)} gần nhất")

    trigger_badge_map = {
        "post_call"          : ("badge-info", "dịch"),
        "scout"              : ("badge-ok",   "scout"),
        "relationship_update": ("badge-warn", "quan hệ"),
        "manual"             : ("badge-dim",  "thủ công"),
    }

    for commit in history:
        cid     = commit["commit"]
        trigger = commit.get("trigger", "")
        ts      = commit.get("timestamp", "")
        changes = commit.get("changes", {})
        badge_cls, badge_label = trigger_badge_map.get(trigger, ("badge-dim", trigger))

        with st.expander(f"{cid}  ·  {ts}", expanded=False):
            st.markdown(f'<span class="badge {badge_cls}">{badge_label}</span>',
                        unsafe_allow_html=True)
            if "__created__" in changes:
                st.caption("_(nhân vật được tạo lần đầu)_")
                continue
            for field, diff in changes.items():
                if not isinstance(diff, dict): continue
                if "added" in diff:
                    st.markdown(f"`{field}`")
                    for item in diff.get("added", []):
                        st.markdown(f'<span style="color:green">+ {item}</span>',
                                    unsafe_allow_html=True)
                    for item in diff.get("removed", []):
                        st.markdown(f'<span style="color:red;text-decoration:line-through">- {item}</span>',
                                    unsafe_allow_html=True)
                elif "old" in diff:
                    old_v = str(diff["old"]) if diff["old"] else "_(trống)_"
                    new_v = str(diff["new"]) if diff["new"] else "_(trống)_"
                    st.markdown(f"`{field}`")
                    col1, col2 = st.columns(2)
                    col1.markdown(f'<span style="color:red">- {old_v}</span>',
                                  unsafe_allow_html=True)
                    col2.markdown(f'<span style="color:green">+ {new_v}</span>',
                                  unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# PAGE: TỪ ĐIỂN
# ══════════════════════════════════════════════════════════════════

def render_glossary() -> None:
    import pandas as pd
    glos = load_glossary_data(S.current_novel)
    if not glos:
        st.info(
            "**Từ điển trống.** Thuật ngữ sẽ được tự động thu thập trong quá trình dịch. "
            "Sau khi dịch vài chương, chạy **🔄 Phân loại thuật ngữ** để sắp xếp vào đúng danh mục."
        )
        return

    staging_count = len(glos.get("staging", []))
    if staging_count:
        st.info(
            f"📖 **{staging_count} thuật ngữ mới** đang chờ phân loại. "
            "Nhấn **🔄 Phân loại thuật ngữ** để AI tự động sắp xếp vào đúng danh mục."
        )

    c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
    sel_cat = c1.selectbox(
        "Danh mục",
        ["Tất cả"] + list(glos.keys()),
        label_visibility="collapsed",
        key="glos_cat",
        help="Lọc thuật ngữ theo danh mục",
    )
    search = c2.text_input(
        "🔍",
        placeholder="Tìm thuật ngữ...",
        label_visibility="collapsed",
        key="glos_q",
    )
    with c3:
        if not S.clean_running:
            if st.button("🔄 Phân loại thuật ngữ", help="AI tự động phân loại thuật ngữ trong Staging vào đúng danh mục"):
                S.clean_logs = []
                S.clean_q    = queue.Queue()
                from littrans.ui.runner import run_background
                run_background(S.clean_q, mode="clean_glossary", novel_name=S.current_novel)
                S.clean_running = True
                st.rerun()
        else:
            st.button("⏳ Đang phân loại…", disabled=True)
    with c4:
        if st.button("↺ Làm mới"):
            load_glossary_data.clear()
            st.rerun()

    _cat_label = {
        "pathways": "Tu luyện", "organizations": "Tổ chức", "items": "Vật phẩm",
        "locations": "Địa danh", "general": "Chung", "staging": "⏳ Chưa phân loại",
    }
    rows = []
    for cat, entries in glos.items():
        if sel_cat != "Tất cả" and cat != sel_cat: continue
        for eng, vn in entries:
            if search and search.lower() not in eng.lower() and search.lower() not in vn.lower():
                continue
            rows.append({"Tiếng Anh": eng, "Tiếng Việt": vn, "Danh mục": _cat_label.get(cat, cat)})

    if rows:
        st.caption(f"{len(rows)} thuật ngữ")
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True,
                     column_config={"Danh mục": st.column_config.TextColumn(width="small")})
    else:
        st.info("Không tìm thấy thuật ngữ nào.")

    if S.clean_running or S.clean_logs:
        if S.clean_running:
            done_flag = _poll("clean_q", "clean_logs")
            if done_flag:
                S.clean_running = False
                S.clean_logs.append("✅ Phân loại hoàn tất.")
                load_glossary_data.clear()
                load_stats.clear()
        if S.clean_logs:
            with st.expander("📋 Nhật ký", expanded=S.clean_running):
                _show_log(S.clean_logs)
        if S.clean_running:
            time.sleep(0.9)
            st.rerun()


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

    # Main metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Chương đã dịch",
        f"{done} / {total}",
        delta=f"{int(done/total*100)}%" if total else None,
        help="Số chương đã có bản dịch / tổng số chương",
    )
    m2.metric("Nhân vật đang theo dõi", s["chars"].get("active", 0),
              help="Nhân vật xuất hiện gần đây")
    m3.metric("Nhân vật lưu trữ", s["chars"].get("archive", 0),
              help="Nhân vật lâu không xuất hiện")
    em_count = s["chars"].get("emotional", 0)
    m4.metric(
        "Đang có trạng thái đặc biệt",
        em_count,
        delta="cần chú ý" if em_count else None,
        delta_color="inverse",
        help="Nhân vật đang tức giận / tổn thương / vừa thay đổi",
    )

    st.divider()

    # Glossary & tools
    glos        = s.get("glos", {})
    total_terms = sum(v for k, v in glos.items() if k != "staging")
    staging_terms = glos.get("staging", 0)
    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Thuật ngữ trong từ điển", total_terms)
    m6.metric(
        "Chờ phân loại",
        staging_terms,
        delta="cần phân loại" if staging_terms else None,
        delta_color="inverse",
        help="Vào tab Từ điển → Phân loại thuật ngữ để xử lý",
    )
    m7.metric("Kỹ năng đã biết", s["skills"].get("total", 0))
    m8.metric("Tên đã chốt", s["lock"].get("total_locked", 0),
              help="Số tên nhân vật/địa danh đã có bản dịch cố định")

    # Chart
    chart_data = {k: v for k, v in glos.items() if v and k != "staging"}
    if chart_data:
        st.divider()
        st.markdown("**Phân bổ từ điển theo danh mục**")
        cat_vn = {
            "pathways": "Tu luyện", "organizations": "Tổ chức",
            "items": "Vật phẩm", "locations": "Địa danh", "general": "Chung",
        }
        df = pd.DataFrame.from_dict(
            {cat_vn.get(k, k): v for k, v in chart_data.items()},
            orient="index",
            columns=["Thuật ngữ"],
        )
        st.bar_chart(df, color="#3B6D11")

    if total:
        st.divider()
        pct = done / total
        st.progress(pct, text=f"Tiến độ dịch: {done}/{total} chương · {int(pct*100)}%")

        rows = [{"Chương": c["name"], "Trạng thái": "✅ Đã dịch" if c["done"] else "⬜ Chưa",
                 "Kích thước": c["size"]} for c in chapters]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════
# PAGE: CÀI ĐẶT
# ══════════════════════════════════════════════════════════════════

def render_settings() -> None:
    env = _load_env()

    def e(key, default=""): return env.get(key, default)
    def ei(key, default):
        try: return int(env.get(key, str(default)))
        except: return default
    def ef(key, default):
        try: return float(env.get(key, str(default)))
        except: return default
    def eb(key, default):
        v = env.get(key, "").strip().lower()
        return v in ("true", "1", "yes", "on") if v else default

    hcol1, hcol2, hcol3 = st.columns([4, 1, 1])
    hcol1.subheader("⚙️ Cài đặt")
    save_clicked  = hcol2.button("💾 Lưu", type="primary", use_container_width=True)
    reset_clicked = hcol3.button("↺ Reset", use_container_width=True)

    if S.settings_saved:
        st.success("✅ Đã lưu! Khởi động lại pipeline để áp dụng thay đổi.")
        S.settings_saved = False

    if not _ENV_PATH.exists():
        st.warning("⚠️  Chưa có file `.env`. Điền API Key và nhấn **Lưu** để tạo.")

    updates: dict[str, str] = {}

    # ── Quick Setup (tab đầu tiên, nổi bật) ──────────────────────
    tabs = st.tabs([
        "🚀 Cài đặt cơ bản",
        "⚙️ Pipeline",
        "🔭 Scout AI",
        "📖 Từ điển tự động",
        "👤 Nhân vật",
        "💰 Giới hạn token",
        "🔀 Merge & Retry",
        "📁 Đường dẫn",
    ])

    with tabs[0]:
        st.markdown("#### 🔑 API Key (bắt buộc)")
        st.markdown(
            "API Key Gemini **miễn phí** từ [aistudio.google.com](https://aistudio.google.com). "
            "Đăng nhập bằng tài khoản Google → **Get API key → Create API key**."
        )

        k_primary = st.text_input(
            "Gemini API Key *",
            value=e("GEMINI_API_KEY"),
            type="password",
            placeholder="AIzaSy...",
            help="Bắt buộc. Lấy miễn phí tại aistudio.google.com",
        )
        updates["GEMINI_API_KEY"] = k_primary

        st.markdown("**Key dự phòng** (khuyến nghị — dùng khi key chính bị rate limit)")
        c1, c2 = st.columns(2)
        k_fb1 = c1.text_input("Key dự phòng 1", value=e("FALLBACK_KEY_1"), type="password",
                               help="API key từ tài khoản Google khác")
        k_fb2 = c2.text_input("Key dự phòng 2", value=e("FALLBACK_KEY_2"), type="password")
        updates.update({"FALLBACK_KEY_1": k_fb1, "FALLBACK_KEY_2": k_fb2})

        st.divider()
        st.markdown("#### 🤖 Engine dịch")
        provider_opts = ["gemini", "anthropic"]
        cur_provider  = e("TRANSLATION_PROVIDER", "gemini")
        provider_idx  = provider_opts.index(cur_provider) if cur_provider in provider_opts else 0

        provider_labels = {
            "gemini"    : "Gemini (Google) — miễn phí, khuyến nghị cho người mới",
            "anthropic" : "Claude (Anthropic) — chất lượng cao hơn, có phí",
        }
        provider_sel = st.radio(
            "Provider",
            provider_opts,
            index=provider_idx,
            format_func=lambda x: provider_labels[x],
            horizontal=False,
            help="Gemini miễn phí và đủ chất lượng cho hầu hết người dùng.",
        )
        updates["TRANSLATION_PROVIDER"] = provider_sel

        if provider_sel == "gemini":
            _models = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash-exp", "gemini-1.5-pro"]
            model_labels = {
                "gemini-2.5-flash"    : "Gemini 2.5 Flash (nhanh, miễn phí) ✓",
                "gemini-2.5-pro"      : "Gemini 2.5 Pro (tốt hơn, giới hạn thấp hơn)",
                "gemini-2.0-flash-exp": "Gemini 2.0 Flash Exp (cũ hơn)",
                "gemini-1.5-pro"      : "Gemini 1.5 Pro (cũ)",
            }
            cur_model = e("GEMINI_MODEL", "gemini-2.5-flash")
            model_idx = _models.index(cur_model) if cur_model in _models else 0
            model = st.selectbox(
                "Model",
                _models,
                index=model_idx,
                format_func=lambda x: model_labels.get(x, x),
            )
            updates["GEMINI_MODEL"] = model
            updates["TRANSLATION_MODEL"] = ""
        else:
            anthropic_key = st.text_input(
                "Anthropic API Key *",
                value=e("ANTHROPIC_API_KEY"),
                type="password",
                placeholder="sk-ant-...",
                help="Lấy tại console.anthropic.com",
            )
            updates["ANTHROPIC_API_KEY"] = anthropic_key
            trans_model = st.text_input(
                "Claude model",
                value=e("TRANSLATION_MODEL", "claude-sonnet-4-6"),
                help="Ví dụ: claude-sonnet-4-6, claude-opus-4-6",
            )
            updates["TRANSLATION_MODEL"] = trans_model

        st.divider()
        st.markdown("#### ⏱️ Tốc độ dịch")
        st.caption(
            "Pipeline nghỉ giữa các chương để tránh bị Google giới hạn. "
            "Nếu bị lỗi 429 nhiều, hãy tăng thời gian nghỉ lên."
        )
        c1, c2 = st.columns(2)
        succ_s = c1.slider(
            "Nghỉ sau mỗi chương thành công (giây)",
            0, 120, ei("SUCCESS_SLEEP", 30), step=5,
            help="Thời gian chờ giữa các chương. Giảm = nhanh hơn nhưng dễ bị rate limit hơn.",
        )
        rl_s = c2.slider(
            "Nghỉ khi bị rate limit (giây)",
            10, 300, ei("RATE_LIMIT_SLEEP", 60), step=10,
            help="Khi Google báo lỗi 429 (quá nhiều request), pipeline chờ bao lâu trước khi thử lại.",
        )
        updates.update({"SUCCESS_SLEEP": str(succ_s), "RATE_LIMIT_SLEEP": str(rl_s)})

    with tabs[1]:
        st.info("Pipeline luôn dùng **3 bước**: Phân tích → Dịch → Kiểm tra.", icon="ℹ️")
        c1, c2, c3 = st.columns(3)
        pre_s  = c1.slider("Nghỉ trước khi dịch (s)",  0, 30, ei("PRE_CALL_SLEEP", 5))
        post_s = c2.slider("Nghỉ sau khi dịch (s)", 0, 30, ei("POST_CALL_SLEEP", 5))
        post_r = c3.number_input("Số lần kiểm tra lại", 0, 5, ei("POST_CALL_MAX_RETRIES", 2))
        retry_q = st.toggle(
            "Dịch lại khi phát hiện lỗi",
            value=eb("TRANS_RETRY_ON_QUALITY", True),
            help="Nếu bước kiểm tra phát hiện lỗi dịch thuật, tự động dịch lại.",
        )
        updates.update({
            "PRE_CALL_SLEEP": str(pre_s), "POST_CALL_SLEEP": str(post_s),
            "POST_CALL_MAX_RETRIES": str(post_r),
            "TRANS_RETRY_ON_QUALITY": "true" if retry_q else "false",
        })
        st.divider()
        max_ret   = st.number_input("Số lần thử lại tối đa khi lỗi", 1, 20, ei("MAX_RETRIES", 5))
        min_chars = st.number_input(
            "Độ dài tối thiểu mỗi chương (ký tự)",
            0, 5000, ei("MIN_CHARS_PER_CHAPTER", 500), step=100,
            help="Chương ngắn hơn mức này sẽ bị cảnh báo.",
        )
        updates.update({"MAX_RETRIES": str(max_ret), "MIN_CHARS_PER_CHAPTER": str(min_chars)})

    with tabs[2]:
        st.markdown(
            "Scout AI **đọc trước** nhiều chương để hiểu ngữ cảnh, "
            "giúp bản dịch nhất quán hơn về xưng hô và mạch truyện."
        )
        c1, c2, c3 = st.columns(3)
        scout_ev = c1.slider("Chạy Scout mỗi N chương", 1, 20, ei("SCOUT_REFRESH_EVERY", 5),
                             help="Scout chạy sau mỗi bao nhiêu chương.")
        scout_lb = c2.slider("Đọc lại N chương gần nhất", 2, 30, ei("SCOUT_LOOKBACK", 10),
                             help="Scout đọc bao nhiêu chương để lấy ngữ cảnh.")
        arc_win  = c3.slider("Giữ bộ nhớ N arc", 1, 10, ei("ARC_MEMORY_WINDOW", 3),
                             help="Số arc memory entries đưa vào mỗi prompt dịch.")
        updates.update({
            "SCOUT_REFRESH_EVERY": str(scout_ev),
            "SCOUT_LOOKBACK": str(scout_lb),
            "ARC_MEMORY_WINDOW": str(arc_win),
        })

    with tabs[3]:
        suggest_on = st.toggle(
            "Tự động phát hiện thuật ngữ mới",
            value=eb("SCOUT_SUGGEST_GLOSSARY", True),
            help="Scout AI sẽ tự động đề xuất thuật ngữ mới vào Staging để phân loại.",
        )
        updates["SCOUT_SUGGEST_GLOSSARY"] = "true" if suggest_on else "false"
        c1, c2 = st.columns(2)
        min_conf = c1.slider(
            "Độ tin cậy tối thiểu",
            0.0, 1.0, ef("SCOUT_SUGGEST_MIN_CONFIDENCE", 0.7), step=0.05,
            disabled=not suggest_on,
            help="0.7 = Scout cần khá chắc chắn mới đề xuất. Tăng lên để ít đề xuất nhầm hơn.",
        )
        max_terms = c2.number_input(
            "Tối đa N thuật ngữ mỗi lần Scout",
            1, 50, ei("SCOUT_SUGGEST_MAX_TERMS", 20),
            disabled=not suggest_on,
        )
        updates["SCOUT_SUGGEST_MIN_CONFIDENCE"] = str(round(min_conf, 2))
        updates["SCOUT_SUGGEST_MAX_TERMS"]      = str(max_terms)

    with tabs[4]:
        st.markdown(
            "LiTTrans tự động lưu trữ nhân vật lâu không xuất hiện để tiết kiệm token."
        )
        c1, c2 = st.columns(2)
        arch_a = c1.slider(
            "Lưu trữ sau N chương vắng mặt",
            10, 200, ei("ARCHIVE_AFTER_CHAPTERS", 60), step=10,
            help="Nhân vật không xuất hiện sau N chương sẽ chuyển sang lưu trữ.",
        )
        emo_r  = c2.slider(
            "Reset trạng thái cảm xúc sau N chương",
            1, 20, ei("EMOTION_RESET_CHAPTERS", 5),
        )
        updates.update({"ARCHIVE_AFTER_CHAPTERS": str(arch_a), "EMOTION_RESET_CHAPTERS": str(emo_r)})

    with tabs[5]:
        st.markdown(
            "Giới hạn số token gửi cho AI mỗi lần. Tăng nếu bị cắt nội dung, "
            "giảm nếu bị lỗi token limit."
        )
        budget = st.number_input(
            "Giới hạn token (0 = tắt)",
            min_value=0, step=10000,
            value=ei("BUDGET_LIMIT", 150000),
            help="Thường để 150000. Giảm nếu model báo token quá dài.",
        )
        updates["BUDGET_LIMIT"] = str(budget)

    with tabs[6]:
        c1, c2, c3 = st.columns(3)
        imm = c1.toggle(
            "Merge ngay sau mỗi chương",
            value=eb("IMMEDIATE_MERGE", True),
            help="Cập nhật nhân vật và từ điển ngay sau mỗi chương. Khuyến nghị bật.",
        )
        ag  = c2.toggle("Tự động phân loại thuật ngữ cuối pipeline", value=eb("AUTO_MERGE_GLOSSARY", False))
        ac  = c3.toggle("Tự động merge nhân vật cuối pipeline", value=eb("AUTO_MERGE_CHARACTERS", False))
        updates.update({
            "IMMEDIATE_MERGE": "true" if imm else "false",
            "AUTO_MERGE_GLOSSARY": "true" if ag else "false",
            "AUTO_MERGE_CHARACTERS": "true" if ac else "false",
        })
        rfp = st.number_input(
            "Thử lại chương lỗi N lần cuối pipeline",
            0, 10, ei("RETRY_FAILED_PASSES", 3),
        )
        updates["RETRY_FAILED_PASSES"] = str(rfp)

    with tabs[7]:
        st.markdown("#### Thư mục làm việc")
        st.info(
            "📚 Data của mỗi truyện được tự động lưu trong `outputs/<TenTruyen>/data/`. "
            "Chỉ cần đặt file chương vào `inputs/<TenTruyen>/`.",
            icon="ℹ️",
        )
        _path_defs = [
            ("INPUT_DIR",   "inputs",  "Thư mục chứa file chương gốc tiếng Anh"),
            ("OUTPUT_DIR",  "outputs", "Thư mục lưu bản dịch + data nhân vật/từ điển"),
            ("PROMPTS_DIR", "prompts", "Thư mục chứa các file hướng dẫn cho AI"),
        ]
        for key, default, desc in _path_defs:
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


# ══════════════════════════════════════════════════════════════════
# SIDEBAR + MAIN
# ══════════════════════════════════════════════════════════════════

def _render_novel_selector() -> None:
    novels = _get_available_novels()

    if not novels:
        st.sidebar.caption(
            "📁 **Một truyện** (flat mode)\n\n"
            "_Tạo subfolder trong `inputs/` để quản lý nhiều truyện._"
        )
        if S.current_novel:
            S.current_novel = ""
            _apply_novel("")
        return

    current = S.current_novel if S.current_novel in novels else novels[0]
    selected = st.sidebar.selectbox(
        "📚 Truyện đang chọn",
        novels,
        index=novels.index(current) if current in novels else 0,
        key="novel_selector_sb",
        help="Chọn truyện để dịch. Mỗi truyện có data riêng biệt.",
    )

    if selected != S.current_novel:
        S.current_novel = selected
        _apply_novel(selected)
        S.sel_ch  = 0
        S.logs    = []
        S.rt_logs = []
        st.rerun()
    elif not S.current_novel:
        S.current_novel = selected
        _apply_novel(selected)


def main() -> None:
    # ── Nếu chưa có API key → hiện welcome screen ────────────────
    if not _has_api_key():
        with st.sidebar:
            st.markdown("## 📖 LiTTrans")
            st.caption("v5.5 — Thiết lập ban đầu")
        render_welcome()
        return

    with st.sidebar:
        st.markdown("## 📖 LiTTrans")
        st.caption("v5.5 — LitRPG / Tu Tiên Pipeline")
        st.divider()

        # Novel selector
        _render_novel_selector()
        st.divider()

        # Navigation
        _pages = {
            "translate" : "📄 Dịch",
            "chapters"  : "🔍 Xem chương",
            "characters": "👤 Nhân vật",
            "glossary"  : "📚 Từ điển",
            "stats"     : "📊 Thống kê",
            "settings"  : "⚙️ Cài đặt",
            "bible"     : "📖 Bible System",
            "epub"      : "📚 EPUB Processor",
        }
        for key, label in _pages.items():
            t = "primary" if S.page == key else "secondary"
            if st.button(label, key=f"nav_{key}", use_container_width=True, type=t):
                S.page    = key
                S.show_rt = False
                st.rerun()

        st.divider()

        # Progress & status badges
        try:
            chs  = load_chapters(S.current_novel)
            done = sum(1 for c in chs if c["done"])
            total = len(chs)
            if total:
                st.progress(done / total)
                st.caption(f"{done}/{total} chương")
            elif S.current_novel:
                st.caption(f"📁 {S.current_novel}\nChưa có chương nào")

            try:
                from littrans.context.glossary import glossary_stats
                glos_s    = glossary_stats()
                staging_n = glos_s.get("staging", 0)
                if staging_n:
                    st.markdown(
                        f'<span class="badge badge-warn">📖 {staging_n} thuật ngữ chờ phân loại</span>',
                        unsafe_allow_html=True,
                    )
            except Exception:
                pass
        except Exception:
            pass

        if S.running:
            st.warning("🔄 Đang dịch… đừng đóng cửa sổ.")
        if S.rt_running:
            st.info("↺ Đang dịch lại...")
        if S.clean_running:
            st.info("🔄 Đang phân loại...")

        st.divider()
        env_ok = _ENV_PATH.exists() and _has_api_key()
        if env_ok:
            st.caption("✅ API key đã cài đặt")
        else:
            st.caption("⚠️ Chưa có API key")
            if st.button("🔑 Cài đặt API Key", key="sidebar_setup"):
                S.page = "settings"
                st.rerun()

    # Đảm bảo settings đồng bộ với current_novel
    if S.current_novel:
        try:
            from littrans.config.settings import settings, set_novel
            if settings.novel_name != S.current_novel:
                set_novel(S.current_novel)
        except Exception:
            pass

    _route = {
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