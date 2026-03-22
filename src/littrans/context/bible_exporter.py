"""
src/littrans/context/bible_exporter.py — BibleExporter.

[Refactor] bible/ → context/. Import: bible.bible_store → context.bible_store.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from littrans.context.bible_store import BibleStore          # ← ĐỔI
from littrans.utils.io_utils import atomic_write


class BibleExporter:
    def __init__(self, store: BibleStore) -> None:
        self._store = store

    def export_markdown(self, output_path: Path, scope: str = "full") -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        meta  = self._store.load_meta()
        lines = [
            "# Bible Report",
            f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Chapters scanned: {meta.scanned_chapters}/{meta.total_chapters}",
            f"> Health: see cross-reference report", "",
        ]
        if scope in ("full","characters"): lines += self._md_characters()
        if scope in ("full","worldbuilding"): lines += self._md_worldbuilding()
        if scope in ("full","lore"): lines += self._md_lore()
        atomic_write(output_path, "\n".join(lines))
        print(f"  ✅ Xuất Markdown: {output_path}")

    def _md_characters(self) -> list[str]:
        chars = self._store.get_all_entities("character")
        lines = ["---", "## Characters\n"]
        for c in sorted(chars, key=lambda x: x.get("role","z")):
            lines += [
                f"### {c.get('canonical_name', c.get('en_name','?'))} `[{c.get('role','?')}]`",
                f"**EN:** {c.get('en_name','')} · **Status:** {c.get('status','')} · **Cấp:** {(c.get('cultivation') or {}).get('realm','')}",
                f"**Faction:** {c.get('faction_id','')} · **Archetype:** {c.get('archetype','')}",
            ]
            if c.get("personality_summary"): lines.append(f"\n> {c['personality_summary']}")
            if c.get("current_goal"): lines.append(f"\n**Goal:** {c['current_goal']}")
            lines.append("")
        return lines

    def _md_worldbuilding(self) -> list[str]:
        wb    = self._store.get_worldbuilding()
        lines = ["---", "## WorldBuilding\n"]
        if wb.cultivation_systems:
            lines.append("### Cultivation Systems\n")
            for cs in wb.cultivation_systems:
                lines.append(f"**{cs.name}** ({cs.pathway_type})")
                for realm in cs.realms: lines.append(f"  {realm.order}. {realm.name_vn} ({realm.name_en})")
                lines.append("")
        if wb.confirmed_rules:
            lines.append("### Confirmed Rules\n")
            for rule in wb.confirmed_rules: lines.append(f"- [{rule.source_chapter}] {rule.description}")
            lines.append("")
        return lines

    def _md_lore(self) -> list[str]:
        lore  = self._store._load_main_lore()
        lines = ["---", "## Main Lore\n"]
        if lore.plot_threads:
            lines.append("### Plot Threads\n")
            open_t   = [t for t in lore.plot_threads if t.status == "open"]
            closed_t = [t for t in lore.plot_threads if t.status == "closed"]
            if open_t:
                lines.append("**🟢 Đang mở:**")
                for t in open_t: lines.append(f"- **{t.name}** (từ {t.opened_chapter}): {t.summary}")
            if closed_t:
                lines.append("\n**✅ Đã đóng:**")
                for t in closed_t: lines.append(f"- **{t.name}** ({t.opened_chapter}→{t.closed_chapter}): {t.resolution}")
            lines.append("")
        if lore.chapter_summaries:
            lines.append("### Chapter Summaries\n")
            for s in lore.chapter_summaries[-20:]: lines.append(f"**{s.chapter}** [{s.tone}]: {s.summary}")
            lines.append("")
        return lines

    def export_json(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._store.export_all_json(output_path)
        print(f"  ✅ Xuất JSON: {output_path}")

    def export_characters_sheet(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        chars = self._store.get_all_entities("character")
        lines = [
            "# Character Reference Sheet",
            f"> {len(chars)} nhân vật · {datetime.now().strftime('%Y-%m-%d')}", "",
            "| Tên VN | Tên EN | Role | Status | Cảnh giới | Tự xưng | Phe |",
            "|---|---|---|---|---|---|---|",
        ]
        for c in sorted(chars, key=lambda x: x.get("canonical_name","")):
            realm = (c.get("cultivation") or {}).get("realm","—")
            lines.append(f"| {c.get('canonical_name','?')} | {c.get('en_name','?')} | {c.get('role','?')} | {c.get('status','?')} | {realm} | {c.get('pronoun_self','—')} | {c.get('faction_id','—')} |")
        atomic_write(output_path, "\n".join(lines))
        print(f"  ✅ Xuất character sheet: {output_path}")

    def export_timeline(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lore   = self._store._load_main_lore()
        events = sorted(lore.events, key=lambda e: e.chapter)
        lines  = ["# Story Timeline", f"> {len(events)} events · {datetime.now().strftime('%Y-%m-%d')}", ""]
        last_chapter = ""
        for ev in events:
            if ev.chapter != last_chapter: lines += ["", f"## {ev.chapter}", ""]; last_chapter = ev.chapter
            parts_str = ", ".join(ev.participants[:4]) if ev.participants else "—"
            icon = {"battle":"⚔️","revelation":"💡","death":"💀","alliance":"🤝","betrayal":"🗡️","breakthrough":"⬆️"}.get(ev.event_type,"📌")
            lines.append(f"{icon} **{ev.title}** [{ev.event_type}]")
            lines.append(f"   {ev.description}")
            if parts_str != "—": lines.append(f"   *Tham gia: {parts_str}*")
            if ev.consequence: lines.append(f"   → {ev.consequence}")
            lines.append("")
        atomic_write(output_path, "\n".join(lines))
        print(f"  ✅ Xuất timeline: {output_path}")

    def export_consistency_report(self, output_path: Path, report) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Bible Consistency Report",
            f"> Generated: {report.generated_at} | Health: {report.health_score:.0%} | Chapters: {report.chapters_checked}", "",
            f"**Tổng:** {report.total_issues} issues ({len(report.errors)} errors · {len(report.warnings)} warnings · {len(report.infos)} infos)", "",
        ]
        for severity, items, icon in [("Errors",report.errors,"🔴"),("Warnings",report.warnings,"🟡"),("Info",report.infos,"🔵")]:
            if items:
                lines += [f"## {icon} {severity}\n"]
                for issue in items:
                    lines += [f"### [{issue.issue_type}] {issue.description}",
                               f"**Evidence:** {', '.join(issue.evidence[:5])}",
                               f"**Suggestion:** {issue.suggestion}", ""]
        atomic_write(output_path, "\n".join(lines))
        print(f"  ✅ Xuất consistency report: {output_path}")
