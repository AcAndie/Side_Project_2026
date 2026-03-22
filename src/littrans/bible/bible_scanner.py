"""
src/littrans/bible/bible_scanner.py — BibleScanner: scan engine chính.

Workflow per chapter:
  1. normalize_text() — tái dụng từ text_normalizer
  2. Kiểm tra đã scan chưa (store.is_chapter_scanned)
  3. Build scan prompt: inject existing entities để AI tránh trùng lặp
  4. call_gemini_json() → raw JSON
  5. Parse → ScanOutput, lưu staging
  6. Mỗi BIBLE_SCAN_BATCH chương → consolidation
  7. Cuối cùng → cross-reference (nếu BIBLE_CROSS_REF=true)

[v1.0] Initial implementation — Bible System Sprint 2
[v1.1 FIX] _run_consolidation: auto-backup trước khi modify, chỉ xóa staging
           của chapters KHÔNG có lỗi (selective cleanup).
           Nếu exception toàn cục → staging giữ nguyên để recover sau.
"""
from __future__ import annotations

import re
import time
import logging
from datetime import datetime
from pathlib import Path

from littrans.bible.bible_store import BibleStore
from littrans.bible.schemas import (
    ScanOutput, ScanCandidate, ScanWorldBuildingClue,
    ScanLoreEntry, BibleChapterSummary,
)
from littrans.utils.io_utils import load_text


# ── Lazy imports ──────────────────────────────────────────────────

def _get_settings():
    from littrans.config.settings import settings
    return settings


def _normalize(text: str) -> str:
    try:
        from littrans.utils.text_normalizer import normalize
        return normalize(text)
    except ImportError:
        return text.replace("\r\n", "\n").strip()


def _call_json(system: str, user: str) -> dict:
    from littrans.llm.client import call_gemini_json
    return call_gemini_json(system, user)


# ═══════════════════════════════════════════════════════════════════
# SYSTEM PROMPT BUILDER
# ═══════════════════════════════════════════════════════════════════

def _load_scan_system_prompt(depth: str) -> str:
    cfg  = _get_settings()
    path = cfg.prompts_dir / "bible_scan.md"
    raw  = load_text(path)
    if not raw:
        return _fallback_system_prompt(depth)

    role       = _extract_xml(raw, "ROLE")
    principles = _extract_xml(raw, "PRINCIPLES")
    depth_txt  = _extract_xml_attr(raw, "DEPTH", "id", depth)
    schemas    = _extract_xml(raw, "RAW_DATA_SCHEMAS") if depth != "quick" else ""
    naming     = _extract_xml(raw, "NAMING")

    return "\n\n".join(filter(None, [
        role, principles,
        f"OUTPUT FORMAT ({depth.upper()}):\n{depth_txt}",
        schemas, naming,
    ]))


def _extract_xml(text: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def _extract_xml_attr(text: str, tag: str, attr: str, val: str) -> str:
    m = re.search(
        rf'<{tag}\s+{attr}="{val}"[^>]*>(.*?)</{tag}>',
        text, re.DOTALL
    )
    return m.group(1).strip() if m else ""


def _fallback_system_prompt(depth: str) -> str:
    base = (
        "Bạn là AI phân tích truyện LitRPG / Tu Tiên. "
        "Đọc chương được cung cấp, trích xuất thông tin CÓ CẤU TRÚC. "
        "CHỈ ghi những gì RÕ RÀNG trong văn bản. KHÔNG suy luận. "
        "Trả về JSON. KHÔNG thêm text ngoài JSON.\n\n"
    )
    if depth == "quick":
        return base + (
            '{"database_candidates": [{entity_type, en_name, canonical_name, '
            'existing_id, is_new, description, confidence, context_snippet}], '
            '"worldbuilding_clues": [], "lore_entry": {}}'
        )
    return base + (
        '{"database_candidates": [...], '
        '"worldbuilding_clues": [{category, description, raw_text, confidence}], '
        '"lore_entry": {chapter_summary, tone, pov_char, location, key_events, '
        'plot_threads_opened, plot_threads_closed, revelations, relationship_changes}}'
    )


# ═══════════════════════════════════════════════════════════════════
# USER MESSAGE BUILDER
# ═══════════════════════════════════════════════════════════════════

def _build_user_message(
    chapter_text    : str,
    chapter_filename: str,
    known_entities  : dict[str, dict],
    depth           : str,
) -> str:
    parts = []

    if known_entities:
        known_lines = []
        for etype, entities in known_entities.items():
            for e in entities[:20]:
                eid   = e.get("id", "?")
                cname = e.get("canonical_name", "")
                ename = e.get("en_name", "")
                known_lines.append(f"  [{eid}] {ename} → {cname} ({etype})")
        if known_lines:
            parts.append(
                "## ENTITIES ĐÃ BIẾT — KHÔNG TẠO MỚI, CHỈ DÙNG existing_id\n"
                + "\n".join(known_lines[:100])
            )

    max_chars = {"quick": 4_000, "standard": 12_000, "deep": 15_000}.get(depth, 12_000)
    preview = chapter_text[:max_chars]
    if len(chapter_text) > max_chars:
        preview += f"\n\n[... {len(chapter_text) - max_chars:,} ký tự còn lại bị cắt ...]"

    parts.append(f"## CHƯƠNG: {chapter_filename}\n\n{preview}")
    return "\n\n---\n\n".join(parts)


# ═══════════════════════════════════════════════════════════════════
# RESPONSE PARSER
# ═══════════════════════════════════════════════════════════════════

def _parse_scan_response(
    raw_data       : dict,
    source_chapter : str,
    chapter_index  : int,
    depth          : str,
    model_used     : str,
) -> ScanOutput:
    candidates = []
    for c in raw_data.get("database_candidates", []):
        if not isinstance(c, dict):
            continue
        en = c.get("en_name", "").strip()
        if not en:
            continue
        try:
            conf = float(c.get("confidence", 0.9))
        except (ValueError, TypeError):
            conf = 0.9
        candidates.append(ScanCandidate(
            entity_type    = c.get("entity_type", "concept"),
            en_name        = en,
            canonical_name = c.get("canonical_name", "").strip(),
            existing_id    = c.get("existing_id", "").strip(),
            is_new         = bool(c.get("is_new", True)),
            description    = c.get("description", "").strip(),
            raw_data       = c.get("raw_data", {}),
            confidence     = min(1.0, max(0.0, conf)),
            context_snippet = c.get("context_snippet", "").strip()[:200],
        ))

    clues = []
    for w in raw_data.get("worldbuilding_clues", []):
        if not isinstance(w, dict):
            continue
        try:
            conf = float(w.get("confidence", 0.8))
        except (ValueError, TypeError):
            conf = 0.8
        clues.append(ScanWorldBuildingClue(
            category    = w.get("category", "other"),
            description = w.get("description", "").strip(),
            raw_text    = w.get("raw_text", "").strip()[:300],
            confidence  = min(1.0, max(0.0, conf)),
        ))

    lr = raw_data.get("lore_entry", {})
    if not isinstance(lr, dict):
        lr = {}
    lore = ScanLoreEntry(
        chapter_summary      = lr.get("chapter_summary", "").strip(),
        tone                 = lr.get("tone", "").strip(),
        pov_char             = lr.get("pov_char", "").strip(),
        location             = lr.get("location", "").strip(),
        key_events           = _safe_list(lr.get("key_events")),
        plot_threads_opened  = _safe_list(lr.get("plot_threads_opened")),
        plot_threads_closed  = _safe_list(lr.get("plot_threads_closed")),
        revelations          = _safe_list(lr.get("revelations")),
        relationship_changes = _safe_list(lr.get("relationship_changes")),
    )

    return ScanOutput(
        source_chapter       = source_chapter,
        chapter_index        = chapter_index,
        scan_depth           = depth,
        database_candidates  = candidates,
        worldbuilding_clues  = clues,
        lore_entry           = lore,
        scanned_at           = datetime.now().strftime("%Y-%m-%d %H:%M"),
        model_used           = model_used,
        raw_response         = raw_data,
    )


def _safe_list(v) -> list:
    return v if isinstance(v, list) else []


# ═══════════════════════════════════════════════════════════════════
# BIBLE SCANNER
# ═══════════════════════════════════════════════════════════════════

class BibleScanner:
    """
    Scan engine chính — đọc inputs/ → gọi AI → lưu staging → consolidation.

    Usage:
        scanner = BibleScanner(store)
        scanner.scan_all()
        scanner.scan_new_only()
    """

    def __init__(self, store: BibleStore | None = None) -> None:
        cfg          = _get_settings()
        self._store  = store or BibleStore(cfg.bible_dir)
        self._depth  = getattr(cfg, "bible_scan_depth", "standard")
        self._batch  = getattr(cfg, "bible_scan_batch", 5)
        self._sleep  = getattr(cfg, "bible_scan_sleep", 10)

    # ── Public entry points ───────────────────────────────────────

    def scan_all(self, force: bool = False) -> dict[str, int]:
        cfg       = _get_settings()
        all_files = self._sorted_inputs(cfg.input_dir)

        if not all_files:
            print(f"❌ Không có file nào trong '{cfg.input_dir}'.")
            return {"scanned": 0, "skipped": 0, "failed": 0}

        self._store.update_meta(total_chapters=len(all_files))

        print(f"\n{'═'*62}")
        print(f"  📖 BIBLE SCAN — {len(all_files)} chương")
        print(f"  Depth: {self._depth} · Batch: {self._batch} · Sleep: {self._sleep}s")
        print(f"{'═'*62}\n")

        return self._scan_loop(all_files, force=force)

    def scan_new_only(self) -> dict[str, int]:
        return self.scan_all(force=False)

    def scan_one(
        self,
        filename    : str,
        chapter_text: str,
        chapter_index: int = 0,
        force       : bool = False,
    ) -> bool:
        cfg = _get_settings()

        if not force and self._store.is_chapter_scanned(filename):
            print(f"  ⏭️  Đã scan: {filename}")
            return True

        text = _normalize(chapter_text)
        if not text.strip():
            print(f"  ⚠️  File rỗng: {filename}")
            return False

        if len(text) < 200:
            print(f"  ⚠️  Chương quá ngắn ({len(text)} ký tự): {filename}")

        known       = self._store.get_entities_for_chapter(text)
        known_count = sum(len(v) for v in known.values())

        print(f"  🔍 Scan [{self._depth}]: {filename} "
              f"({len(text):,} ký tự · {known_count} entities đã biết)")

        system_prompt = _load_scan_system_prompt(self._depth)
        user_message  = _build_user_message(text, filename, known, self._depth)

        try:
            raw_data  = _call_json(system_prompt, user_message)
            model_str = self._current_model()
            output    = _parse_scan_response(
                raw_data, filename, chapter_index, self._depth, model_str
            )
        except Exception as e:
            logging.error(f"[BibleScanner] {filename}: {e}")
            print(f"  ❌ Scan lỗi: {e}")
            return False

        if self._depth == "deep" and output.database_candidates:
            output = self._verification_call(output, text, filename)

        self._store.save_staging(filename, output)

        n_cands  = len(output.database_candidates)
        n_clues  = len(output.worldbuilding_clues)
        has_lore = bool(output.lore_entry.chapter_summary)
        print(f"  ✅ Staged: {n_cands} entities · {n_clues} WB clues · "
              f"lore: {'✓' if has_lore else '—'}")

        return True

    # ── Internal scan loop ────────────────────────────────────────

    def _scan_loop(self, all_files: list[str], force: bool) -> dict[str, int]:
        cfg     = _get_settings()
        stats   = {"scanned": 0, "skipped": 0, "failed": 0}
        batch_n = 0

        for i, filename in enumerate(all_files):
            print(f"\n[{i+1}/{len(all_files)}] {filename}")

            fp   = cfg.input_dir / filename
            text = load_text(fp)
            if not text.strip():
                print(f"  ⚠️  File rỗng — bỏ qua.")
                stats["skipped"] += 1
                continue

            ok = self.scan_one(filename, text, chapter_index=i, force=force)
            if ok:
                stats["scanned"] += 1
                batch_n += 1
            else:
                stats["failed"] += 1

            if batch_n >= self._batch:
                self._run_consolidation(f"batch_{i+1}")
                batch_n = 0

            if i < len(all_files) - 1:
                time.sleep(self._sleep)

        if self._store.has_staging():
            self._run_consolidation("final")

        cfg_xref = getattr(cfg, "bible_cross_ref", True)
        if cfg_xref and stats["scanned"] > 0:
            self._run_cross_reference()

        self._print_final_stats(stats, len(all_files))
        return stats

    # ── Consolidation ─────────────────────────────────────────────

    def _run_consolidation(self, batch_label: str) -> None:
        """
        [v1.1 FIX] Auto-backup trước khi modify.
        Chỉ xóa staging của chapters đã consolidate THÀNH CÔNG.
        Nếu exception toàn cục → staging giữ nguyên để recover sau.
        """
        staging = self._store.load_all_staging()
        if not staging:
            return

        print(f"\n  🔄 Consolidation [{batch_label}]: {len(staging)} chapters...")

        # ── Backup trước khi modify ───────────────────────────────
        try:
            from littrans.utils.data_versioning import backup, prune_old_backups
            for db_file in self._store._db_dir.glob("*.json"):
                if db_file.name != "index.json":   # index tự rebuild được, không cần backup
                    backup(db_file)
                    prune_old_backups(db_file, keep=3)
            wb_path = self._store._dir / "worldbuilding.json"
            if wb_path.exists():
                backup(wb_path)
                prune_old_backups(wb_path, keep=3)
        except Exception as e:
            logging.warning(f"[BibleScanner] Backup lỗi (không block consolidation): {e}")
            print(f"  ⚠️  Backup lỗi: {e} — tiếp tục consolidation")

        # ── Consolidation ─────────────────────────────────────────
        try:
            from littrans.bible.bible_consolidator import BibleConsolidator
            consolidator = BibleConsolidator(self._store)
            result       = consolidator.run(staging)

            print(f"  ✅ Consolidated: +{result.chars_added} nhân vật "
                  f"· +{result.entities_added} entities · "
                  f"+{result.lore_chapters} lore entries")

            if result.errors:
                print(f"  ⚠️  {len(result.errors)} lỗi:")
                for err in result.errors[:5]:
                    print(f"     {err}")

            # ── Selective cleanup: chỉ xóa chapter KHÔNG có lỗi ──
            failed_chapters: set[str] = set()
            for err in result.errors:
                # Format lỗi: "chapter_001.txt: <message>"
                chapter_part = err.split(":")[0].strip()
                if chapter_part:
                    failed_chapters.add(chapter_part)

            successful = [
                s.source_chapter for s in staging
                if s.source_chapter not in failed_chapters
            ]

            if successful:
                self._store.clear_staging(successful)
                if failed_chapters:
                    print(f"  ⚠️  Giữ lại staging của {len(failed_chapters)} chapter lỗi để retry sau:")
                    for ch in sorted(failed_chapters):
                        print(f"     • {ch}")
            else:
                print(f"  ⚠️  Tất cả chapters đều lỗi — staging giữ nguyên toàn bộ")

        except Exception as e:
            logging.error(f"[BibleScanner] Consolidation lỗi nghiêm trọng: {e}")
            print(f"  ⚠️  Consolidation lỗi: {e} → staging giữ nguyên TOÀN BỘ để recover sau")
            # Không xóa bất kỳ staging file nào khi exception toàn cục

    # ── Cross-reference ───────────────────────────────────────────

    def _run_cross_reference(self) -> None:
        print(f"\n  🔎 Cross-reference đang chạy...")
        try:
            from littrans.bible.cross_reference import CrossReferenceEngine
            engine = CrossReferenceEngine(self._store)
            report = engine.run()
            health = f"{report.health_score:.0%}"
            print(f"  📊 Cross-reference xong: health={health} · "
                  f"{report.total_issues} issues "
                  f"({len(report.errors)} errors, {len(report.warnings)} warnings)")
        except Exception as e:
            logging.error(f"[BibleScanner] Cross-reference lỗi: {e}")
            print(f"  ⚠️  Cross-reference lỗi: {e}")

    # ── Deep mode: verification ───────────────────────────────────

    def _verification_call(
        self, output: ScanOutput, chapter_text: str, filename: str
    ) -> ScanOutput:
        verify_system = (
            "Bạn là AI kiểm tra chất lượng dữ liệu. "
            "Đọc danh sách entities vừa extract từ 1 chương truyện. "
            "Kiểm tra: entity nào CÓ VẺ là cùng một nhân vật/địa điểm/vật phẩm được gọi khác tên? "
            "Trả về JSON: {\"duplicates\": [{\"idx_a\": 0, \"idx_b\": 1, \"reason\": \"...\"}]}"
        )
        if len(output.database_candidates) < 2:
            return output

        cand_summary = "\n".join(
            f"{i}. [{c.entity_type}] {c.en_name} → {c.canonical_name}: {c.description}"
            for i, c in enumerate(output.database_candidates[:30])
        )
        try:
            result = _call_json(verify_system, f"Entities từ {filename}:\n\n{cand_summary}")
            dups   = result.get("duplicates", [])
            if dups:
                skip_idxs = {d["idx_b"] for d in dups if isinstance(d, dict)}
                output.database_candidates = [
                    c for i, c in enumerate(output.database_candidates)
                    if i not in skip_idxs
                ]
                print(f"    🔧 Verification: bỏ {len(skip_idxs)} duplicates")
        except Exception as e:
            logging.warning(f"[BibleScanner] Verification call lỗi: {e}")

        return output

    # ── Helpers ───────────────────────────────────────────────────

    def _sorted_inputs(self, input_dir: Path) -> list[str]:
        if not input_dir.exists():
            return []
        files = [f.name for f in input_dir.iterdir()
                 if f.suffix in (".txt", ".md")]
        return sorted(files, key=lambda s: [
            int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", s)
        ])

    def _current_model(self) -> str:
        try:
            cfg = _get_settings()
            return cfg.gemini_model
        except Exception:
            return "unknown"

    def _print_final_stats(self, stats: dict[str, int], total: int) -> None:
        print(f"\n{'═'*62}")
        print(f"  📖 BIBLE SCAN — Hoàn tất")
        print(f"  Tổng   : {total} chương")
        print(f"  Scanned: {stats['scanned']}")
        print(f"  Skipped: {stats['skipped']} (đã scan trước)")
        print(f"  Failed : {stats['failed']}")
        db_stats = self._store.get_stats()
        by_type  = db_stats.get("by_type", {})
        if by_type:
            type_str = " · ".join(f"{k}:{v}" for k, v in sorted(by_type.items()))
            print(f"  Database: {type_str}")
        print(f"{'═'*62}\n")