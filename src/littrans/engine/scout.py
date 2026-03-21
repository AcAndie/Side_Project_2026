"""
src/littrans/engine/scout.py — Scout AI.

Mỗi SCOUT_REFRESH_EVERY chương:
  1. Xóa Context_Notes cũ → sinh mới (4 mục)
  2. Append Arc_Memory (tóm tắt window)
  3. [v4]   Cập nhật emotional_state nhân vật
  4. [v4.4] Đề xuất thuật ngữ mới → Staging_Terms.md
  5. [v5.0] Cập nhật EPS (Emotional Proximity Signal) giữa các cặp nhân vật

Không raise — pipeline tiếp tục nếu Scout thất bại.

[v4.2] Validate emotional_states là list + giá trị hợp lệ trước khi ghi DB.
[v4.3 FIX] Xoá dead import `from google.genai import types`.
[v4.4] Thêm _suggest_new_terms() — Scout Glossary Suggest.
[v5.0] Thêm _update_eps() — EPS update cho các cặp quan hệ thay đổi trong window.
"""
from __future__ import annotations

import os
import re
import logging

from littrans.config.settings import settings
from littrans.utils.io_utils import load_text, atomic_write, load_json, save_json

_SCOUT_SYSTEM = """Bạn là Scout AI — đọc trước các chương truyện để sinh ghi chú hỗ trợ AI dịch.

Đọc các chương tiếng Anh, trả về ghi chú ngắn gọn bằng tiếng Việt
theo ĐÚNG 4 mục dưới đây. KHÔNG thêm lời mở đầu hay kết luận.

## 1. MẠCH TRUYỆN ĐẶC BIỆT
Có flashback / hồi ký / giấc mơ / thư từ / cảnh quá khứ không?
Nếu không → "Không có."

## 2. KHOÁ XƯNG HÔ ĐANG ACTIVE
Từng cặp nhân vật + xưng hô hiện tại. Ghi rõ nếu khác theo ngữ cảnh.
VD:
- Arthur ↔ Lyra: hiện tại = Anh–Em | trong hồi ký = Tao–Mày
- System ↔ MC: luôn = Hệ thống–Ký chủ

## 3. DIỄN BIẾN GẦN NHẤT
3–5 sự kiện / thay đổi trạng thái quan trọng nhất.

## 4. CẢNH BÁO CHO AI DỊCH
Những điểm CỤ THỂ dễ sai nếu không có ngữ cảnh.
Nếu không có → "Không có cảnh báo đặc biệt."
VD:
- ⚠️ Chương tiếp theo có thể tiếp tục hồi ký → GIỮ xưng hô Tao–Mày."""

_EMOTION_SYSTEM = """Bạn là AI phân tích cảm xúc nhân vật trong truyện.

Đọc các chương, xác định trạng thái cảm xúc CUỐI CÙNG của từng nhân vật CHÍNH.
Trả về JSON. KHÔNG thêm gì ngoài JSON:
{
  "emotional_states": [
    {
      "character": "Tên nhân vật",
      "state": "normal|angry|hurt|changed",
      "reason": "Lý do ngắn gọn (1 câu)",
      "intensity": "low|medium|high"
    }
  ]
}

Quy tắc:
- "normal"  : bình thường
- "angry"   : tức giận, bực bội — ảnh hưởng lời thoại
- "hurt"    : tổn thương, buồn — ảnh hưởng lời thoại
- "changed" : vừa trải qua sự kiện lớn thay đổi nhận thức/mục tiêu
- Chỉ nhân vật có tên rõ ràng và xuất hiện đáng kể. Tối đa 8 nhân vật."""

_EPS_SYSTEM = """Bạn là AI phân tích mức độ thân mật (Emotional Proximity Signal) giữa các nhân vật.

Đọc các chương, xác định các cặp nhân vật có thay đổi mức độ thân mật đáng kể.

Thang EPS (1–5):
  1 = FORMAL       : lạnh lùng, trang trọng — dùng kính ngữ, câu đầy đủ
  2 = NEUTRAL      : mặc định, không đặc biệt
  3 = FRIENDLY     : thân thiện, thoải mái — bỏ kính ngữ, câu ngắn hơn
  4 = CLOSE        : rất thân — nickname, chia sẻ cảm xúc cá nhân
  5 = INTIMATE     : yêu / gia đình gần gũi — ngôn ngữ riêng tư đặc biệt

Chỉ báo cáo cặp nhân vật:
  - Có tương tác trực tiếp trong window này VÀ
  - Mức độ thân mật thay đổi RÕ RÀNG (không phải suy đoán)

Trả về JSON. KHÔNG thêm bất cứ thứ gì ngoài JSON:
{
  "eps_updates": [
    {
      "character_a": "tên nhân vật A",
      "character_b": "tên nhân vật B",
      "new_intimacy_level": 3,
      "signals": [
        "A gọi B bằng nickname lần đầu ở chương X",
        "B chia sẻ bí mật cá nhân với A",
        "Họ bắt đầu dùng xưng hô thân mật hơn"
      ],
      "reason": "Sau sự kiện cùng thoát hiểm, A và B trở nên thân thiết hơn",
      "chapter_reference": "chapter_005.txt"
    }
  ]
}

Nếu không có thay đổi đáng kể → trả về: {"eps_updates": []}"""

_GLOSSARY_SUGGEST_SYSTEM = """Bạn là chuyên gia thuật ngữ cho truyện LitRPG / Tu Tiên.

Đọc đoạn truyện tiếng Anh và tìm thuật ngữ CHUYÊN BIỆT chưa có trong danh sách đã biết.

CẦN BÁO CÁO (ưu tiên theo thứ tự):
  1. Tên kỹ năng, chiêu thức, phép thuật, kỹ thuật chiến đấu
  2. Danh hiệu, cấp bậc tu luyện, cảnh giới, tước vị
  3. Tên tổ chức, hội phái, môn phái, lực lượng
  4. Địa danh, vùng đất, cõi giới, dungeon
  5. Vật phẩm đặc biệt, đan dược, vũ khí có tên riêng
  6. Thuật ngữ hệ thống: pathway, sequence, ability class...

KHÔNG BÁO CÁO:
  - Tên nhân vật (đã có hệ thống riêng)
  - Từ tiếng Anh thông thường không cần dịch
  - Thuật ngữ đã có trong danh sách "ĐÃ BIẾT" dưới đây
  - Bất cứ thứ gì chưa đủ ngữ cảnh để dịch chính xác

Quy tắc dịch đề xuất:
  - Tên kỹ năng / danh hiệu / cảnh giới → Hán Việt, đặt trong [ngoặc vuông] nếu là kỹ năng
  - Địa danh Hán → Hán Việt
  - Tên phương Tây, LitRPG sequence → giữ nguyên tiếng Anh

Trả về JSON. KHÔNG thêm bất cứ thứ gì ngoài JSON:
{
  "suggested_terms": [
    {
      "english": "tên thuật ngữ tiếng Anh gốc",
      "vietnamese": "bản dịch đề xuất",
      "category": "pathways|organizations|items|locations|general",
      "confidence": 0.85,
      "context": "mô tả ngắn: xuất hiện ở đâu, nghĩa là gì"
    }
  ]
}"""

_VALID_STATES      = {"normal", "angry", "hurt", "changed"}
_VALID_INTENSITIES = {"low", "medium", "high"}


# ── Public API ────────────────────────────────────────────────────

def run(all_files: list[str], current_index: int) -> None:
    """Chạy toàn bộ Scout: notes + arc memory + emotion + eps + glossary suggest. Không raise."""
    _refresh_context_notes(all_files, current_index)

    start  = max(0, current_index - settings.scout_lookback)
    window = all_files[start:current_index]
    if window:
        range_label = f"{window[0]} → {window[-1]}"
        try:
            from littrans.managers.memory import append_arc_summary
            append_arc_summary(all_files, current_index, range_label)
        except Exception as e:
            logging.error(f"Arc Memory: {e}")
            print(f"  ⚠️  Arc Memory lỗi: {e}")

    try:
        _update_emotional_states(all_files, current_index)
    except Exception as e:
        logging.error(f"Emotion Tracker: {e}")
        print(f"  ⚠️  Emotion Tracker lỗi: {e}")

    try:
        _update_eps(all_files, current_index)
    except Exception as e:
        logging.error(f"EPS Update: {e}")
        print(f"  ⚠️  EPS Update lỗi: {e}")

    try:
        _suggest_new_terms(all_files, current_index)
    except Exception as e:
        logging.error(f"GlossarySuggest: {e}")
        print(f"  ⚠️  Glossary Suggest lỗi: {e}")


def should_refresh(chapters_done: int) -> bool:
    return chapters_done % settings.scout_refresh_every == 0


def load_context_notes() -> str:
    return load_text(settings.context_notes_file)


# ── Context Notes ─────────────────────────────────────────────────

def _refresh_context_notes(all_files: list[str], current_index: int) -> None:
    if os.path.exists(str(settings.context_notes_file)):
        print("  🗑️  Context_Notes.md cũ đã xóa.")

    start  = max(0, current_index - settings.scout_lookback)
    window = all_files[start:current_index]
    if not window:
        _write_empty_note("Chưa có chương nào để phân tích.")
        return

    texts = [
        (fn, load_text(str(settings.input_dir / fn))[:6000])
        for fn in window
        if load_text(str(settings.input_dir / fn)).strip()
    ]
    if not texts:
        _write_empty_note("Không đọc được nội dung chương.")
        return

    range_label = f"{window[0]} → {window[-1]}"
    print(f"  🔭 Scout đọc {len(texts)} chương ({range_label})...")
    user_msg = "\n\n---\n\n".join(f"### {fn}\n\n{text}" for fn, text in texts)

    try:
        from littrans.llm.client import call_gemini_text
        body = call_gemini_text(_SCOUT_SYSTEM, user_msg)
    except Exception as e:
        logging.error(f"Scout AI: {e}")
        body = f"⚠️ Scout AI lỗi: {e}"

    note = (
        f"# Context Notes\n"
        f"_Sinh bởi Scout AI · {range_label}_\n\n"
        f"{body.strip()}\n"
    )
    atomic_write(settings.context_notes_file, note)
    print(f"  ✅ Context_Notes.md ({len(note)} ký tự).")


def _write_empty_note(reason: str) -> None:
    note = (
        f"# Context Notes\n_Không có dữ liệu: {reason}_\n\n"
        "## 1. MẠCH TRUYỆN ĐẶC BIỆT\nKhông có.\n\n"
        "## 2. KHOÁ XƯNG HÔ ĐANG ACTIVE\nChưa xác định.\n\n"
        "## 3. DIỄN BIẾN GẦN NHẤT\nKhông có.\n\n"
        "## 4. CẢNH BÁO CHO AI DỊCH\nKhông có cảnh báo đặc biệt.\n"
    )
    atomic_write(settings.context_notes_file, note)


# ── Emotion Tracker ───────────────────────────────────────────────

def _update_emotional_states(all_files: list[str], current_index: int) -> None:
    start  = max(0, current_index - settings.scout_lookback)
    window = all_files[start:current_index]
    if not window:
        return

    texts = []
    for fn in window[-5:]:
        base, _ = os.path.splitext(fn)
        vn_path = str(settings.output_dir / f"{base}_VN.txt")
        en_path = str(settings.input_dir  / fn)
        for path in [vn_path, en_path]:
            text = load_text(path)
            if text.strip():
                texts.append((fn, text[:3000]))
                break

    if not texts:
        return

    user_msg = "\n\n---\n\n".join(f"### {fn}\n\n{t}" for fn, t in texts)

    try:
        from littrans.llm.client import call_gemini_json
        data = call_gemini_json(_EMOTION_SYSTEM, user_msg)
    except Exception as e:
        logging.error(f"Emotion extract: {e}")
        return

    if not isinstance(data, dict):
        return

    states = data.get("emotional_states", [])
    if not isinstance(states, list) or not states:
        return

    char_data = load_json(settings.characters_active_file) or {}
    chars     = char_data.get("characters", {})
    updated   = 0

    for name, profile in chars.items():
        em      = profile.get("emotional_state", {})
        last_ch = em.get("last_chapter_index", 0)
        if (current_index - last_ch) >= settings.emotion_reset_chapters:
            if em.get("current", "normal") != "normal":
                profile.setdefault("emotional_state", {})["current"] = "normal"
                profile["emotional_state"]["reset_at"] = current_index
                updated += 1

    for entry in states:
        if not isinstance(entry, dict):
            continue
        char_name = entry.get("character", "")
        if not isinstance(char_name, str) or not char_name.strip():
            continue
        char_name = char_name.strip()
        state     = entry.get("state", "normal")
        intensity = entry.get("intensity", "medium")
        reason    = entry.get("reason", "")

        if state not in _VALID_STATES:
            state = "normal"
        if intensity not in _VALID_INTENSITIES:
            intensity = "medium"

        matched = next((n for n in chars if n.lower() == char_name.lower()), None)
        if not matched:
            continue

        chars[matched]["emotional_state"] = {
            "current"            : state,
            "intensity"          : intensity,
            "reason"             : reason if isinstance(reason, str) else "",
            "last_chapter_index" : current_index,
        }
        updated += 1

    if updated:
        save_json(settings.characters_active_file, char_data)
        non_normal = [
            f"{n}={p['emotional_state']['current']}"
            for n, p in chars.items()
            if p.get("emotional_state", {}).get("current", "normal") != "normal"
        ]
        print(f"  💭 Emotion Tracker: {updated} cập nhật"
              + (f" | Active: {', '.join(non_normal[:5])}" if non_normal else " | Tất cả normal"))


# ── EPS Update (v5.0) ─────────────────────────────────────────────

def _update_eps(all_files: list[str], current_index: int) -> None:
    """
    Phân tích thay đổi mức độ thân mật giữa các cặp nhân vật trong window.
    Cập nhật intimacy_level và eps_signals vào Characters_Active.json.
    """
    start  = max(0, current_index - settings.scout_lookback)
    window = all_files[start:current_index]
    if not window:
        return

    # Đọc text chương — ưu tiên bản dịch VN (ngắn hơn EN raw)
    texts = []
    for fn in window[-5:]:  # Chỉ 5 chương gần nhất để tiết kiệm token
        base, _ = os.path.splitext(fn)
        vn_path = str(settings.output_dir / f"{base}_VN.txt")
        en_path = str(settings.input_dir  / fn)
        for path in [vn_path, en_path]:
            text = load_text(path)
            if text.strip():
                texts.append((fn, text[:3000]))
                break

    if not texts:
        return

    # Load danh sách nhân vật để gửi kèm context
    char_data = load_json(settings.characters_active_file) or {}
    chars     = char_data.get("characters", {})
    if not chars:
        return

    # Tóm tắt quan hệ hiện tại để AI có context
    rel_summary_lines = []
    for name, profile in list(chars.items())[:10]:  # Giới hạn 10 nhân vật
        for other, r in profile.get("relationships", {}).items():
            intimacy = r.get("intimacy_level", 2)
            rel_summary_lines.append(
                f"  {name} ↔ {other}: EPS={intimacy} | dynamic={r.get('dynamic','?')}"
            )

    rel_context = ""
    if rel_summary_lines:
        rel_context = "## QUAN HỆ HIỆN TẠI\n" + "\n".join(rel_summary_lines[:20])

    user_msg = (
        rel_context + "\n\n---\n\n"
        + "\n\n---\n\n".join(f"### {fn}\n\n{t}" for fn, t in texts)
    )

    try:
        from littrans.llm.client import call_gemini_json
        data = call_gemini_json(_EPS_SYSTEM, user_msg)
    except Exception as e:
        logging.error(f"[EPS] call lỗi: {e}")
        return

    if not isinstance(data, dict):
        return

    eps_updates = data.get("eps_updates", [])
    if not isinstance(eps_updates, list) or not eps_updates:
        return

    updated_pairs = 0
    dirty = False

    for upd in eps_updates:
        if not isinstance(upd, dict):
            continue

        char_a = upd.get("character_a", "").strip()
        char_b = upd.get("character_b", "").strip()
        new_level = upd.get("new_intimacy_level")
        signals   = upd.get("signals", [])
        reason    = upd.get("reason", "")

        if not char_a or not char_b:
            continue
        if not isinstance(new_level, int) or not (1 <= new_level <= 5):
            continue

        # Tìm match case-insensitive
        matched_a = next((n for n in chars if n.lower() == char_a.lower()), None)
        matched_b = next((n for n in chars if n.lower() == char_b.lower()), None)

        if not matched_a:
            continue  # Bỏ qua nếu char_a không có trong DB

        # Cập nhật relationship của matched_a → matched_b
        rels_a = chars[matched_a].setdefault("relationships", {})
        target_key = matched_b if matched_b else char_b

        if target_key not in rels_a:
            rels_a[target_key] = {
                "type": "neutral", "feeling": "", "dynamic": "",
                "pronoun_status": "weak", "current_status": "",
                "tension_points": [], "history": [],
                "intimacy_level": 2, "eps_signals": [],
            }

        r = rels_a[target_key]
        old_level = r.get("intimacy_level", 2)

        if old_level == new_level and not signals:
            continue  # Không có gì thay đổi

        r["intimacy_level"] = new_level

        # Append signals mới (không trùng)
        existing_sigs = set(r.get("eps_signals", []))
        new_sigs = [s for s in signals if isinstance(s, str) and s and s not in existing_sigs]
        if new_sigs:
            r.setdefault("eps_signals", []).extend(new_sigs)
            r["eps_signals"] = r["eps_signals"][-10:]  # Giữ 10 gần nhất

        if reason:
            r.setdefault("history", []).append({
                "chapter": upd.get("chapter_reference", window[-1] if window else ""),
                "event"  : f"[EPS {old_level}→{new_level}] {reason}",
            })

        updated_pairs += 1
        dirty = True

        # Cũng cập nhật chiều ngược lại nếu matched_b có trong DB
        if matched_b and matched_b in chars:
            rels_b = chars[matched_b].setdefault("relationships", {})
            if matched_a not in rels_b:
                rels_b[matched_a] = {
                    "type": "neutral", "feeling": "", "dynamic": "",
                    "pronoun_status": "weak", "current_status": "",
                    "tension_points": [], "history": [],
                    "intimacy_level": 2, "eps_signals": [],
                }
            r_b = rels_b[matched_a]
            r_b["intimacy_level"] = new_level
            if new_sigs:
                r_b.setdefault("eps_signals", []).extend(new_sigs)
                r_b["eps_signals"] = r_b["eps_signals"][-10:]

    if dirty:
        save_json(settings.characters_active_file, char_data)
        # Log summary
        from littrans.llm.schemas import EPS_LABELS
        pair_summaries = []
        for upd in eps_updates[:3]:
            if isinstance(upd, dict):
                lvl = upd.get("new_intimacy_level", 0)
                label = EPS_LABELS.get(lvl, ("?", ""))[0] if lvl else "?"
                pair_summaries.append(
                    f"{upd.get('character_a','?')}↔{upd.get('character_b','?')}:{lvl}/{label}"
                )
        suffix = " | ".join(pair_summaries)
        print(f"  💞 EPS Update: {updated_pairs} cặp → {suffix}")


# ── Glossary Suggest ──────────────────────────────────────────────

def _suggest_new_terms(all_files: list[str], current_index: int) -> None:
    """
    Đề xuất thuật ngữ mới từ window hiện tại → ghi vào Staging_Terms.md.
    Chỉ chạy khi SCOUT_SUGGEST_GLOSSARY=true. Không raise.
    """
    if not settings.scout_suggest_glossary:
        return

    start  = max(0, current_index - settings.scout_lookback)
    window = all_files[start:current_index]
    if not window:
        return

    texts = []
    for fn in window[-5:]:
        text = load_text(str(settings.input_dir / fn))
        if text.strip():
            texts.append((fn, text[:5000]))

    if not texts:
        return

    from littrans.managers.glossary import existing_terms_set
    known = existing_terms_set()

    known_sample = sorted(known)[:200]
    known_block  = "\n".join(f"- {t}" for t in known_sample)
    if len(known) > 200:
        known_block += f"\n... (và {len(known) - 200} thuật ngữ khác)"

    user_msg = (
        f"## THUẬT NGỮ ĐÃ BIẾT — KHÔNG BÁO CÁO LẠI\n"
        f"{known_block}\n\n---\n\n"
        + "\n\n---\n\n".join(f"### {fn}\n\n{text}" for fn, text in texts)
    )

    try:
        from littrans.llm.client import call_gemini_json
        data = call_gemini_json(_GLOSSARY_SUGGEST_SYSTEM, user_msg)
    except Exception as e:
        logging.error(f"[GlossarySuggest] call lỗi: {e}")
        return

    if not isinstance(data, dict):
        return

    suggestions = data.get("suggested_terms", [])
    if not isinstance(suggestions, list) or not suggestions:
        return

    from littrans.llm.schemas import TermDetail
    filtered: list[TermDetail] = []
    seen_this_batch: set[str]  = set()

    for s in suggestions:
        if not isinstance(s, dict):
            continue
        eng  = s.get("english", "").strip()
        vn   = s.get("vietnamese", "").strip()
        cat  = s.get("category", "general")
        conf = 0.0
        try:
            conf = float(s.get("confidence", 0))
        except (ValueError, TypeError):
            pass

        if not eng or not vn:
            continue
        if conf < settings.scout_suggest_min_confidence:
            continue
        if eng.lower() in known or eng.lower() in seen_this_batch:
            continue
        if len(filtered) >= settings.scout_suggest_max_terms:
            break

        if cat not in ("pathways", "organizations", "items", "locations", "general"):
            cat = "general"

        try:
            filtered.append(TermDetail(english=eng, vietnamese=vn, category=cat))
            seen_this_batch.add(eng.lower())
        except Exception as e:
            logging.warning(f"[GlossarySuggest] TermDetail parse lỗi [{eng}]: {e}")

    if not filtered:
        return

    from littrans.managers.glossary import add_new_terms
    source_label = f"scout_suggest_{window[-1]}"
    n = add_new_terms(filtered, source_label)

    if n:
        cats: dict[str, int] = {}
        for t in filtered[:n]:
            cats[t.category] = cats.get(t.category, 0) + 1
        cat_str  = " · ".join(f"{k}:{v}" for k, v in sorted(cats.items()))
        dest_str = "Glossary" if settings.immediate_merge else "Staging"
        print(f"  📖 Glossary Suggest: +{n} thuật ngữ → {dest_str} ({cat_str})")