"""
src/littrans/ui/ui_utils.py — Shared UI rendering utilities.
Extracted from app.py (Batch 7).
"""
from __future__ import annotations

import difflib
import html as _html

import streamlit as st
import streamlit.components.v1 as components


def _paras_to_html(text: str) -> str:
    paras = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    if not paras:
        return "<p style='color:#999;font-style:italic'>Không có nội dung.</p>"
    return "".join(
        f"<p>{_html.escape(p).replace(chr(10), '<br>')}</p>" for p in paras
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
    raw_p = [p.strip() for p in raw.replace("\r\n", "\n").split("\n\n") if p.strip()]
    vn_p  = [p.strip() for p in vn.replace("\r\n", "\n").split("\n\n") if p.strip()]
    ops   = difflib.SequenceMatcher(None, raw_p, vn_p, autojunk=False).get_opcodes()
    ta: dict[int, str] = {}; tb: dict[int, str] = {}
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
            esc = _html.escape(p).replace(chr(10), "<br>")
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


def _poll(q_key: str, logs_key: str, thread_key: str | None = None) -> bool:
    from littrans.ui.runner import poll_queue as _pq
    S = st.session_state
    q = S.get(q_key)
    if q is None:
        return False
    done, _ = _pq(q, S[logs_key])
    if not done and thread_key:
        t = S.get(thread_key)
        if t is not None and not t.is_alive():
            S[logs_key].append("⚠️  Thread dừng bất ngờ.")
            done = True
    return done


def _show_log(logs: list[str]) -> None:
    st.code("\n".join(logs[-300:]) if logs else "(chờ log...)", language=None)
