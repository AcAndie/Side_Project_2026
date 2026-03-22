"""
src/littrans/context/bible_prompt_builder.py — Bible-aware Trans-call prompt.

[Refactor] bible/ → context/, managers/ → context/, engine/ → core/.
"""
from __future__ import annotations

import re

from littrans.context.bible_store import BibleStore          # ← ĐỔI
from littrans.context.schemas import BibleCharacter           # ← ĐỔI


def _name_in_text(name: str, text_lower: str) -> bool:
    if not name or len(name) < 2: return False
    try:
        return bool(re.search(rf"(?<![^\W_]){re.escape(name.lower())}(?![^\W_])", text_lower, re.IGNORECASE|re.UNICODE))
    except re.error:
        return name.lower() in text_lower


def _section(title: str, body: str) -> str:
    BAR = "═" * 62
    return f"{BAR}\n {title}\n{BAR}\n{body.strip()}"


def _translation_output_requirements() -> str:
    return (
        "Trả về BẢN DỊCH HOÀN CHỈNH — plain text, không JSON, không markdown code block.\n\n"
        "Quy tắc:\n"
        "  • Giữ nguyên cấu trúc đoạn văn của bản gốc\n"
        "  • Mỗi đoạn văn gốc = một đoạn trong bản dịch\n"
        "  • Dòng trống giữa các đoạn thường — giữ nguyên như gốc\n"
        "  • Bảng hệ thống / System Box — KHÔNG có dòng trống giữa các dòng trong box\n"
        "  • KHÔNG thêm lời mở đầu, kết luận, hay chú thích vào bản dịch\n"
        "  • KHÔNG bọc bản dịch trong dấu ngoặc kép hay code block\n"
        "  • Áp dụng EPS (Phần 3) để điều chỉnh văn phong xưng hô\n"
        "  • Áp dụng Scene Plan (Phần 4) để hiểu mạch truyện trước khi dịch"
    )


def _fmt_bible_entities(entities: dict[str, list[dict]], chapter_text: str) -> str:
    parts = ["**Thực thể đã được xây dựng Bible (dùng CHÍNH XÁC tên đã chốt):**\n"]
    has_content = False
    chars = entities.get("character", [])
    if chars:
        parts.append(f"### Nhân vật ({len(chars)})\n")
        for c in chars:
            cname = c.get("canonical_name", c.get("en_name","?"))
            ename = c.get("en_name",""); role = c.get("role","?"); status = c.get("status","alive")
            realm = (c.get("cultivation") or {}).get("realm",""); pronoun = c.get("pronoun_self","")
            line = f"**{cname}** ({ename}) [{role}]"
            if status != "alive": line += f" ⚠️ {status}"
            if realm: line += f" | {realm}"
            if pronoun: line += f" | Tự xưng: **{pronoun}**"
            if c.get("personality_summary"): line += f"\n  → {c['personality_summary'][:100]}"
            parts.append(line)
        parts.append(""); has_content = True
    for etype, label in [("skill","Kỹ năng"),("location","Địa danh"),("item","Vật phẩm"),("faction","Tổ chức")]:
        items = entities.get(etype, [])
        if items:
            parts.append(f"### {label} ({len(items)})\n")
            for e in items:
                cname = e.get("canonical_name", e.get("en_name","?")); ename = e.get("en_name","")
                extra = e.get("skill_type") or e.get("location_type") or e.get("item_type") or ""
                parts.append(f"  {ename} → **{cname}**" + (f" [{extra}]" if extra else ""))
            parts.append(""); has_content = True
    if not has_content: return "Không có thực thể đã biết nào liên quan trong chương này."
    return "\n".join(parts).strip()


def _fmt_bible_character_profiles(chars: list[dict], chapter_text: str) -> str:
    if not chars: return "Không có nhân vật đã biết nào trong chương này."
    header = (
        "Nhân vật từ Bible — đã được xác nhận qua nhiều chương.\n\n"
        "QUY TẮC XƯNG HÔ:\n"
        "  1. relationships[X] strong dynamic → KHÔNG thay đổi\n"
        "  2. relationships[X] weak dynamic → tạm thời\n"
        "  3. pronoun_self fallback\n\n"
        "  ⛔ Chỉ đổi xưng hô khi: phản bội / tra khảo / lật mặt / đổi phe\n"
    )
    profiles = []
    for c in chars:
        cname = c.get("canonical_name", c.get("en_name","?"))
        ename = c.get("en_name",""); role = c.get("role","?"); archetype = c.get("archetype","")
        pronoun = c.get("pronoun_self","?"); realm = (c.get("cultivation") or {}).get("realm","—")
        goal = c.get("current_goal",""); psych = c.get("personality_summary","")
        block = [f"### {cname} ({ename})  [{role}] | {archetype}"]
        block.append(f"**Cảnh giới:** {realm}  **Tự xưng:** {pronoun}")
        if psych: block.append(f"\n**Tính cách:** {psych}")
        rels = c.get("relationships", [])
        if rels:
            text_lower_ch = chapter_text.lower()
            relevant = [r for r in rels if _name_in_text(r.get("target_name") or r.get("target_id",""), text_lower_ch)]
            display_rels = relevant[:4] if relevant else rels[:2]
            block.append("\n**Quan hệ:**")
            for rel in display_rels:
                target = rel.get("target_name") or rel.get("target_id","?")
                rtype = rel.get("rel_type",""); dynamic = rel.get("dynamic",""); eps = rel.get("eps_level",2)
                block.append(f"  - {cname} ↔ {target}: [{rtype}] dynamic={dynamic or '?'} | EPS={eps}/5")
        if goal: block.append(f"\n**Mục tiêu:** {goal}")
        skill_ids = c.get("skill_ids",[])
        if skill_ids: block.append(f"**Kỹ năng:** {', '.join(skill_ids[:5])}")
        profiles.append("\n".join(block))
    return header + "\n\n---\n\n".join(profiles)


def _fmt_bible_lore_context(store: BibleStore, n: int = 3) -> str:
    summaries = store.get_recent_lore(n)
    threads   = store.get_plot_threads("open")
    if not summaries and not threads: return ""
    lines = [f"**Bối cảnh từ Bible ({n} chương gần nhất):**\n"]
    for s in summaries:
        lines.append(f"**{s.chapter}** [{s.tone}]")
        lines.append(s.summary)
        if s.key_events: lines.extend(f"  - {e}" for e in s.key_events[:3])
        lines.append("")
    if threads:
        lines.append("**Plot threads đang mở:**")
        for t in threads[:5]:
            lines.append(f"  ⚠️ {t.name} (từ {t.opened_chapter}): {t.summary[:80]}")
    return "\n".join(lines)


def _eps_from_bible(chars: list[dict], chapter_text: str) -> str:
    from littrans.llm.schemas import EPS_LABELS, EPS_BAR
    eps_lines = []; seen: set[frozenset] = set()
    for c in chars:
        cname = c.get("canonical_name", c.get("en_name","?"))
        for rel in c.get("relationships",[])[:5]:
            target = rel.get("target_name") or rel.get("target_id","")
            pair   = frozenset([cname, target])
            if pair in seen or not target: continue
            seen.add(pair)
            eps = rel.get("eps_level",2)
            if not isinstance(eps, int) or not (1 <= eps <= 5): eps = 2
            label, hint = EPS_LABELS.get(eps, ("NEUTRAL",""))
            bar = EPS_BAR.get(eps, "██░░░")
            eps_lines.append(f"  {cname} ↔ {target}: {bar} {eps}/5 {label} → {hint}")
    if not eps_lines: return ""
    return "\n\n**EPS — Mức độ thân mật (điều chỉnh văn phong):**\n" + "\n".join(eps_lines)


def _apply_bible_budget(entities, all_chars, chapter_text, budget_limit):
    try:
        from littrans.llm.token_budget import estimate_tokens, SOFT_LIMIT_RATIO
        import re
        soft = int(budget_limit * SOFT_LIMIT_RATIO)
        entity_text = _fmt_bible_entities(entities, chapter_text)
        char_text   = _fmt_bible_character_profiles(all_chars, chapter_text)
        total_est   = estimate_tokens(entity_text) + estimate_tokens(char_text)
        if total_est <= soft * 0.6: return entities, all_chars
        if len(all_chars) > 5:
            text_lower = chapter_text.lower()
            scored = []
            for c in all_chars:
                name = c.get("en_name","") or c.get("canonical_name","")
                count = len(re.findall(rf"(?<![^\W_]){re.escape(name.lower())}(?![^\W_])", text_lower, re.UNICODE)) if name else 0
                scored.append((count, c))
            scored.sort(key=lambda x: x[0], reverse=True)
            all_chars = [c for _, c in scored[:5]]
            entities["character"] = all_chars
            print(f"  ✂️  [BibleBudget] Cắt chars → {len(all_chars)} relevant nhất")
    except Exception:
        pass
    return entities, all_chars


def build_bible_translation_prompt(
    instructions    : str,
    chapter_text    : str,
    chapter_filename: str,
    store           : BibleStore,
    chapter_map     = None,
    name_lock_table : dict[str, str] | None = None,
    budget_limit    : int = 0,
) -> str:
    entities     = store.get_entities_for_chapter(chapter_text)
    all_chars    = entities.get("character", [])
    wb_context   = store.get_relevant_worldbuilding(chapter_text)
    lore_context = _fmt_bible_lore_context(store, n=3)
    foreshadow_hints = store.get_active_foreshadows(chapter_filename)

    if budget_limit > 0:
        entities, all_chars = _apply_bible_budget(entities, all_chars, chapter_text, budget_limit)

    total_entities = sum(len(v) for v in entities.values())
    print(f"     Bible entities: {total_entities} ({len(all_chars)} chars) · WB: {'✓' if wb_context else '—'} · Lore: {'✓' if lore_context else '—'}")

    parts = [
        "Bạn là AI chuyên dịch truyện LitRPG / Tu Tiên từ tiếng Anh sang tiếng Việt.\n"
        "Nhiệm vụ DUY NHẤT: dịch chapter được cung cấp. "
        "KHÔNG điền JSON, KHÔNG phân tích, KHÔNG thêm chú thích.\n"
        "[BIBLE MODE] Dùng thông tin từ Bible — đã được verify qua nhiều chương.\n",
        _section("PHẦN 1 — HƯỚNG DẪN DỊCH", instructions),
        _section("PHẦN 2 — TỪ ĐIỂN & THỰC THỂ (từ Bible)", _fmt_bible_entities(entities, chapter_text)),
        _section("PHẦN 3 — PROFILE NHÂN VẬT (từ Bible)",
                 _fmt_bible_character_profiles(all_chars, chapter_text)
                 + (_eps_from_bible(all_chars, chapter_text) if all_chars else "")),
    ]

    if chapter_map and not chapter_map.is_empty():
        parts.append(_section("PHẦN 4 — CHAPTER MAP (đã phân tích trước — ưu tiên cao)", chapter_map.to_prompt_block()))
    else:
        hints_block = ""
        if foreshadow_hints:
            hints_block = "\n⚠️ Foreshadow đang active:\n" + "\n".join(foreshadow_hints)
        parts.append(_section("PHẦN 4 — GHI CHÚ CHAPTER",
                              "Không có chapter map.\nSuy luận xưng hô và tên từ các phần trên." + hints_block))

    parts.append(_section("PHẦN 5 — YÊU CẦU ĐẦU RA", _translation_output_requirements()))

    if lore_context:
        parts.append(_section("PHẦN 6 — BỐI CẢNH TỪ BIBLE (thay thế Arc Memory)", lore_context))

    if wb_context:
        parts.append(_section("PHẦN 7 — WORLDBUILDING (quy luật & hệ thống liên quan)", wb_context))

    from littrans.context.name_lock import format_for_prompt as fmt_lock   # ← ĐỔI
    parts.append(_section("PHẦN 8 — NAME LOCK TABLE (bảng tên đã chốt — BẮT BUỘC tuân theo)", fmt_lock(name_lock_table or {})))

    return "\n\n".join(parts)
