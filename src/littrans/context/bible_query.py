"""
src/littrans/context/bible_query.py — BibleQuery.

[Refactor] bible/ → context/. Import: bible.bible_store → context.bible_store.
"""
from __future__ import annotations

import logging
from littrans.context.bible_store import BibleStore   # ← ĐỔI


class BibleQuery:
    def __init__(self, store: BibleStore) -> None:
        self._store = store

    def search(self, query: str, entity_type: str | None = None) -> list[dict]:
        return self._store.search_entities(query, entity_type)

    def get_entity(self, name: str, entity_type: str | None = None) -> dict | None:
        return self._store.get_entity(name, entity_type)

    def get_character_timeline(self, char_name: str) -> list[dict]:
        lore   = self._store._load_main_lore()
        name_l = char_name.lower()
        events = [
            {"chapter": ev.chapter, "type": ev.event_type, "title": ev.title,
             "description": ev.description, "consequence": ev.consequence}
            for ev in lore.events
            if any(p.lower() == name_l or name_l in p.lower() for p in ev.participants)
        ]
        return sorted(events, key=lambda e: e["chapter"])

    def get_chapter_entities(self, chapter: str) -> dict:
        lore    = self._store._load_main_lore()
        summary = next((s for s in lore.chapter_summaries if s.chapter == chapter), None)
        result  = {"chapter": chapter, "summary": None, "entities": {}}
        if summary:
            result["summary"] = {"text": summary.summary, "tone": summary.tone, "key_events": summary.key_events}
        chars_mentioned: set[str] = set()
        for ev in lore.events:
            if ev.chapter == chapter: chars_mentioned.update(ev.participants)
        if chars_mentioned:
            result["entities"]["characters"] = [
                self.get_entity(name, "character") for name in chars_mentioned
                if self.get_entity(name, "character")
            ]
        return result

    def get_relationship_arc(self, char_a: str, char_b: str) -> list[dict]:
        lore   = self._store._load_main_lore()
        a_l, b_l = char_a.lower(), char_b.lower()
        return [
            {"chapter": ev.chapter, "type": ev.event_type, "title": ev.title, "consequence": ev.consequence}
            for ev in sorted(lore.events, key=lambda e: e.chapter)
            if a_l in [p.lower() for p in ev.participants] and b_l in [p.lower() for p in ev.participants]
        ]

    def get_open_plot_threads(self) -> list[dict]:
        return [{"name": t.name, "opened": t.opened_chapter, "summary": t.summary}
                for t in self._store.get_plot_threads("open")]

    def ask(self, question: str) -> str:
        recent    = self._store.get_recent_lore(5)
        threads   = self._store.get_plot_threads("open")
        all_chars = self._store.get_all_entities("character")
        context   = "## Nhân vật\n"
        for c in all_chars[:20]:
            context += f"- {c.get('en_name','')} ({c.get('canonical_name','')}): {c.get('description','')} [{c.get('status','')}]\n"
        if recent:
            context += "\n## Tóm tắt gần nhất\n"
            for s in recent: context += f"- {s.chapter}: {s.summary}\n"
        if threads:
            context += "\n## Plot threads đang mở\n"
            for t in threads[:5]: context += f"- {t.name}: {t.summary}\n"
        system = (
            "Bạn là AI chuyên gia về nội dung truyện LitRPG / Tu Tiên này.\n"
            "Dựa trên Bible được cung cấp, trả lời câu hỏi chính xác và ngắn gọn.\n"
            "Nếu không có đủ thông tin, nói rõ điều đó.\n\n"
            f"## BIBLE CONTEXT\n{context}"
        )
        try:
            from littrans.llm.client import call_gemini_text
            return call_gemini_text(system, question)
        except Exception as e:
            logging.error(f"[BibleQuery.ask] {e}")
            return f"❌ Lỗi: {e}"
