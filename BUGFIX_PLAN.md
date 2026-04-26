# BUGFIX_PLAN.md — NovelPipeline

> Phạm vi: review toàn bộ working tree (đã modify nhưng chưa commit) tính tới
> 2026-04-26. Tập trung 3 lớp: core pipeline, context, UI/runner.
> Audit dựa trên CLAUDE.md (4 pitfalls + 7 conventions) + Phase 2/3 schema.

Ưu tiên: **P0** = chặn hoặc vi phạm hard rule trong CLAUDE.md · **P1** = sai
hành vi runtime · **P2** = code-smell / dead code / doc lệch.

---

## Tóm tắt

| ID | File | Severity | Loại |
|----|------|----------|------|
| BUG-01 | core/pipeline.py:388–449 | P0 | Indentation broken + orphan scratch comments + lỗi log message |
| BUG-02 | ui/runner.py:66–139 | P0 | `run_background` thread thiếu `add_script_run_ctx` (vi phạm pitfall #1) |
| BUG-03 | ui/bible_ui.py:564–604 | P0 | `_launch_crossref` thread thiếu `add_script_run_ctx` |
| BUG-04 | ui/bible_ui.py:533–621 | P1 | `_render_consistency` tự poll + sleep+rerun, dùng legacy `bible_crossref_*` keys |
| BUG-05 | context/characters.py:495–514 (`delete_character`) | P1 | Không invalidate `_char_active_cache` / `_char_archive_cache` → stale reads |
| BUG-06 | ui/runner.py:114–120 | P1 | `clean_chars` mode docstring nói "fail fast" nhưng vẫn fallback `merge` |
| BUG-07 | core/pipeline.py:444 (else branch) | P2 | Log message sai khi `trans_retry_on_quality=False` |
| BUG-08 | config/settings.py:152–153 | P2 | Orphan scratch comments + line 153 misindented |
| BUG-09 | config/settings.py:272 | P2 | Stray `@` ký tự trong comment (`# flat mode: default@`) |
| BUG-10 | config/settings.py:1–9 (header) | P2 | Header nói `_bible_dir_raw` nhưng field thật là `_bible_dir_env` |
| BUG-11 | context/name_lock.py:31–32 | P2 | Orphan scratch comments giữa file |
| BUG-12 | ui/ui_utils.py:95 (`_poll`) | P2 | Dead function — không nơi nào import |
| BUG-13 | README.md:607–608 | P2 | Reference đã xoá: `pipeline_page.py`, `scraper_page.py` |
| BUG-14 | ui/pages/bible_page.py:16–19 | P2 | Re-export private name `_render_export` (underscore prefix) |
| BUG-15 | core/pipeline.py:674 banner | P2 | Banner ghi v5.4, header CLAUDE.md/app.py ghi v5.7 |

---

## Plan chi tiết

### P0 — Phải fix trước khi merge

#### BUG-01 — Pipeline post-call retry block: indent + scratch comments + log
**File:** [src/littrans/core/pipeline.py:388-449](src/littrans/core/pipeline.py#L388-L449)

Triệu chứng:
- Lines 389–391 lẫn comment scratch leak từ instructions edit:
  ```
  # src/littrans/core/pipeline.py
  # Tìm và thay thế đoạn sau trong _translate_three_call():
  # (phần if/else cuối của post-call loop)
  ```
- Body của `if (settings.trans_retry_on_quality ...)` ở 24 spaces thay vì 16 → parse được nhưng fragile. `else:` body cũng 24 spaces.
- BUG-07 đi kèm: log "Vẫn còn lỗi dịch thuật sau {N} lần retry" in cả khi `trans_retry_on_quality=False` (chưa retry lần nào).

Fix:
1. Xóa 3 dòng comment scratch (389–391).
2. Re-indent block 393–449 về 16 spaces (1 level inside `for`).
3. Tách 2 trường hợp trong `else`:
   ```python
   else:
       if not settings.trans_retry_on_quality:
           print("  ⚠️  trans_retry_on_quality=False → ghi file để review")
       else:
           print(f"  ⚠️  Vẫn còn lỗi sau {settings.post_call_max_retries} lần retry → ghi file để review")
       final_translation = post_result.final_translation
       break
   ```
4. Thêm syntax test: `python -c "import ast; ast.parse(open('src/littrans/core/pipeline.py', encoding='utf-8').read())"`

#### BUG-02 — `run_background` thread thiếu `add_script_run_ctx`
**File:** [src/littrans/ui/runner.py:66-139](src/littrans/ui/runner.py#L66-L139)

CLAUDE.md pitfall #1: Streamlit thread touch `st.session_state` mà không có ctx → fail silently. `run_background` dùng cho **4 prefix**: `tx`, `rt`, `cg`, `cc`. Hiện chỉ start `Thread(...).start()` không gắn ctx.

Triệu chứng có thể: nhật ký "Đang dịch…" treo, log không hiện, queue write OK nhưng `S.{prefix}_logs` không update.

Fix (gói lại như `ScrapeRunner`):
```python
thread = threading.Thread(target=_worker, daemon=True)
try:
    from streamlit.runtime.scriptrunner import add_script_run_ctx
    add_script_run_ctx(thread)
except ImportError:
    pass
thread.start()
return thread
```

#### BUG-03 — `_launch_crossref` thread thiếu ctx
**File:** [src/littrans/ui/bible_ui.py:564-604](src/littrans/ui/bible_ui.py#L564-L604)

Cùng pattern như BUG-02 — `threading.Thread(target=_worker, daemon=True).start()` ở dòng 604 không gắn ctx. `_launch_bible_scan` (dòng 248) đã có ctx, nhưng crossref bỏ quên.

Fix: copy block `add_script_run_ctx` từ `_launch_bible_scan`.

---

### P1 — Hành vi runtime sai

#### BUG-04 — Consistency tab tự poll, dùng legacy keys
**File:** [src/littrans/ui/bible_ui.py:533-621](src/littrans/ui/bible_ui.py#L533-L621)

Vi phạm Phase 2 rule trong CLAUDE.md: "chỉ `app.py` gọi `poll_all(S)`. Pages KHÔNG được tự gọi `poll_queue` hoặc `time.sleep + st.rerun`". `_handle_crossref_log` làm đúng cả hai (line 611 + line 620–621).

Fix lựa chọn:
- **Option A (gọn nhất):** thêm prefix mới ví dụ `cr` (cross-reference) vào `JOB_KEYS` trong [ui/core/state.py](src/littrans/ui/core/state.py), migrate `_render_consistency` dùng `S.cr_*` y hệt mọi page khác. Bỏ `_handle_crossref_log` polling, để `app.py poll_all` lo.
- **Option B:** tận dụng prefix `bi` đang có nếu chấp nhận crossref và scan dùng chung 1 job lane (không chạy song song được).

Khuyến nghị Option A — phù hợp với schema hiện có.

#### BUG-05 — `delete_character` không invalidate cache
**File:** [src/littrans/context/characters.py:495-514](src/littrans/context/characters.py#L495-L514)

Module có cache `_char_active_cache` + `_char_archive_cache` (dòng 56–94). `delete_character` save_json xong nhưng không reset cache → call kế tiếp `_cached_load_active()` vẫn thấy nhân vật đã xóa cho tới khi mtime/size thay đổi đủ.

Note: cache key dùng `(size, mtime_ns)` nên thực tế save_json sẽ thay đổi cả hai và cache miss tự nhiên. Nhưng atomic-write có thể giữ size không đổi nếu json layout y hệt cũ — hiếm nhưng có thể xảy ra. Fix triệt để:

```python
def delete_character(name: str) -> bool:
    ...
    finally:
        global _char_active_cache, _char_archive_cache
        with _char_cache_lock:
            _char_active_cache = None
            _char_archive_cache = None
    return removed
```

#### BUG-06 — `clean_chars` default action contradicts docstring
**File:** [src/littrans/ui/runner.py:114-120](src/littrans/ui/runner.py#L114-L120)

```python
elif mode == "clean_chars":
    # [FIX] Fail fast nếu action không được chỉ định
    action = char_action or "merge"
    if not char_action:
        print("⚠️  char_action không được truyền vào → dùng default 'merge'.")
```

Docstring (line 75–82) tuyên bố "rỗng thay vì 'merge' để tránh default âm thầm" và "bắt buộc khi mode='clean_chars'". Nhưng code vẫn fallback `merge`.

Fix — chọn 1:
- **Strict (đúng spec):** `if not char_action: raise ValueError("clean_chars: char_action required")`
- **Lenient (đúng code):** xóa docstring fail-fast, giữ fallback.

Khuyến nghị strict — UI hiện chỉ gọi `clean_glossary`, không có chỗ gọi `clean_chars` qua `run_background` nên rủi ro thấp.

---

### P2 — Code-smell, dead code, doc lệch

#### BUG-07 — Đã gộp vào BUG-01

#### BUG-08 — Scratch comments trong settings.py
**File:** [src/littrans/config/settings.py:152-153](src/littrans/config/settings.py#L152-L153)

```python
    # src/littrans/config/settings.py
# Chỉ thay đổi trong __post_init__ và thêm 1 method mới
```

Xóa 2 dòng.

#### BUG-09 — Stray `@` trong comment
**File:** [src/littrans/config/settings.py:272](src/littrans/config/settings.py#L272)

`return self.data_dir / "bible"               # flat mode: default@`

Sửa: bỏ `@`.

#### BUG-10 — Header docstring lệch tên field
**File:** [src/littrans/config/settings.py:1-9](src/littrans/config/settings.py#L1-L9)

Header nói `_bible_dir_raw`. Field thật: `_bible_dir_env` (line 122).
Sửa header để khớp.

#### BUG-11 — Scratch comments trong name_lock.py
**File:** [src/littrans/context/name_lock.py:31-32](src/littrans/context/name_lock.py#L31-L32)

```python
# src/littrans/context/name_lock.py
# Thay thế toàn bộ hàm build_name_lock_table() và thêm _extract_from_bible()
```

Xóa.

#### BUG-12 — `_poll` dead code
**File:** [src/littrans/ui/ui_utils.py:95-107](src/littrans/ui/ui_utils.py#L95-L107)

Định nghĩa nhưng không file nào import. Xóa hàm.

#### BUG-13 — README references file đã xóa
**File:** [README.md:607-608](README.md#L607-L608)

```
│       ├── pipeline_page.py ← Pipeline 1-click
│       ├── scraper_page.py  ← Scraper UI
```

Cập nhật cây thư mục theo trạng thái Phase 3 hiện tại (đã có trong CLAUDE.md).

#### BUG-14 — Re-export private name
**File:** [src/littrans/ui/pages/bible_page.py:16-19](src/littrans/ui/pages/bible_page.py#L16-L19)

```python
from littrans.ui.bible_ui import (
    render_bible_tab as render_bible,
    _render_export   as render_bible_export,
)
```

Fix: đổi tên `_render_export` → `render_bible_export` trong [ui/bible_ui.py:628](src/littrans/ui/bible_ui.py#L628), bỏ `_` prefix, update import.

#### BUG-15 — Banner version stale
**File:** [src/littrans/core/pipeline.py:674](src/littrans/core/pipeline.py#L674)

`Pipeline Dịch Truyện v5.4` nhưng app.py + CLAUDE.md đã ở v5.7. Đồng bộ hoặc bỏ version trong banner để khỏi phải maintain.

---

## Order of operations

1. **Wave A (critical, ~30 phút):** BUG-01 → BUG-02 → BUG-03. Sau Wave A test smoke: chạy 1 chương dịch + 1 lần Scrape, đảm bảo log hiện đầy đủ.
2. **Wave B (runtime, ~45 phút):** BUG-04 (Option A — thêm prefix `cr`) → BUG-05 → BUG-06.
3. **Wave C (polish, ~15 phút):** BUG-08 → BUG-09 → BUG-10 → BUG-11 → BUG-12 → BUG-13 → BUG-14 → BUG-15.

## Verification checklist (sau khi fix)

- [ ] `python -c "import ast; [ast.parse(open(f,encoding='utf-8').read()) for f in ['src/littrans/core/pipeline.py','src/littrans/config/settings.py','src/littrans/ui/runner.py','src/littrans/ui/bible_ui.py','src/littrans/context/characters.py','src/littrans/context/name_lock.py']]"` → không lỗi.
- [ ] `grep -n "src/littrans/" src/littrans/**/*.py` không trả về scratch path comments.
- [ ] Smoke: `python scripts/run_ui.py` → tab Translate, click "Dịch", log hiện trong < 5s (BUG-02).
- [ ] Smoke: tab Bible → Consistency → Validate, log hiện không cần manual rerun (BUG-03+04).
- [ ] Settings → expander "Quản lý nhân vật" → xóa 1 nhân vật → list refresh ngay (BUG-05).

## Out of scope (ghi nhận, không fix lần này)

- Scraper `_call` retry path khi tất cả retry đều TimeoutError ở last attempt: rơi vào fallback model — đúng spec, không sửa.
- `glossary._all_data_cache` không invalidate explicit sau write (chỉ dựa vào content hash) — đã verified an toàn vì atomic_write thay đổi mtime_ns.
- Settings dùng `object.__setattr__` cho `novel_name` — dataclass không frozen nhưng giữ pattern explicit, không cần fix.
