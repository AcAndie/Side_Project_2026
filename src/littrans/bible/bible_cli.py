"""
src/littrans/bible/bible_cli.py — CLI sub-commands cho Bible System.

Commands:
    bible scan          — Scan chương mới / toàn bộ
    bible stats         — Thống kê nhanh
    bible query         — Tìm kiếm entity
    bible export        — Xuất báo cáo
    bible consolidate   — Consolidate staging → database thủ công
    bible crossref      — Chạy cross-reference check

Được đăng ký vào app chính trong cli.py:
    app.add_typer(bible_app, name="bible")
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

bible_app = typer.Typer(
    name="bible",
    help="📖 Bible System — quản lý knowledge base truyện",
    add_completion=False,
)
console = Console()


# ── Helpers ───────────────────────────────────────────────────────

def _get_store():
    from littrans.config.settings import settings
    from littrans.bible.bible_store import BibleStore
    return BibleStore(settings.bible_dir)


def _check_bible_mode() -> bool:
    """Warn nếu BIBLE_MODE=false nhưng vẫn cho chạy."""
    from littrans.config.settings import settings
    if not settings.bible_mode:
        console.print(
            "[yellow]⚠️  BIBLE_MODE=false trong .env — "
            "Bible data sẽ không được dùng khi dịch.\n"
            "   Thêm BIBLE_MODE=true vào .env để bật.[/yellow]"
        )
    return True


# ═══════════════════════════════════════════════════════════════════
# SCAN
# ═══════════════════════════════════════════════════════════════════

@bible_app.command("scan")
def bible_scan(
    depth: str = typer.Option(
        "standard", "--depth", "-d",
        help="Depth: quick | standard | deep",
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Scan lại kể cả chương đã scan",
    ),
    new_only: bool = typer.Option(
        True, "--new-only/--all",
        help="Chỉ scan chương mới (mặc định: true)",
    ),
):
    """Scan chương trong inputs/ → xây dựng Bible knowledge base."""
    _check_bible_mode()

    if depth not in ("quick", "standard", "deep"):
        console.print(f"[red]❌ depth phải là: quick | standard | deep[/red]")
        raise typer.Exit(1)

    from littrans.config.settings import settings
    # Override depth tạm thời cho session này
    object.__setattr__(settings, "bible_scan_depth", depth)

    store   = _get_store()
    from littrans.bible.bible_scanner import BibleScanner
    scanner = BibleScanner(store)

    console.print(f"\n[bold]📖 Bible Scan[/bold] — depth=[cyan]{depth}[/cyan]  "
                  f"force=[cyan]{force}[/cyan]  new_only=[cyan]{new_only}[/cyan]\n")

    if new_only and not force:
        stats = scanner.scan_new_only()
    else:
        stats = scanner.scan_all(force=force)

    console.print(
        f"\n[green]✅ Xong:[/green] "
        f"scanned={stats['scanned']}  "
        f"skipped={stats['skipped']}  "
        f"failed={stats['failed']}"
    )


# ═══════════════════════════════════════════════════════════════════
# STATS
# ═══════════════════════════════════════════════════════════════════

@bible_app.command("stats")
def bible_stats():
    """Thống kê nhanh: entity counts, scan progress, staging."""
    store = _get_store()
    stats = store.get_stats()
    prog  = store.get_scan_progress()
    meta  = stats.get("meta", {})

    table = Table(title="📖 Bible System Stats", show_header=True)
    table.add_column("Mục", style="cyan")
    table.add_column("Giá trị", style="green")

    table.add_row("Story title",   meta.get("story_title", "—"))
    table.add_row("Schema version",meta.get("schema_version", "—"))
    table.add_section()

    total   = prog.get("total", 0)
    scanned = prog.get("scanned", 0)
    pct     = f"{prog.get('pct', 0):.1f}%"
    table.add_row("Scan progress",  f"{scanned}/{total} chương ({pct})")
    table.add_row("Last scanned",   prog.get("last_chapter", "—"))
    table.add_row("Scan depth",     prog.get("depth", "—"))
    table.add_row("Last cross-ref", prog.get("cross_ref", "—") or "Chưa chạy")
    table.add_section()

    by_type = stats.get("by_type", {})
    for etype in ("character", "item", "location", "skill", "faction", "concept"):
        n = by_type.get(etype, 0)
        if n:
            table.add_row(f"  {etype.capitalize()}s", str(n))

    table.add_section()
    table.add_row("Lore chapters",   str(stats.get("lore_chapters", 0)))
    table.add_row("Staging files",   str(stats.get("staging", 0)))

    console.print(table)


# ═══════════════════════════════════════════════════════════════════
# QUERY
# ═══════════════════════════════════════════════════════════════════

@bible_app.command("query")
def bible_query(
    name: str = typer.Argument(..., help="Tên entity cần tìm"),
    entity_type: Optional[str] = typer.Option(
        None, "--type", "-t",
        help="Lọc theo loại: character | item | location | skill | faction | concept",
    ),
):
    """Tìm kiếm entity trong Bible database."""
    store   = _get_store()
    results = store.search_entities(name, entity_type=entity_type)

    if not results:
        console.print(f"[yellow]Không tìm thấy '{name}'[/yellow]")
        raise typer.Exit(0)

    console.print(f"\n[bold]Kết quả cho '{name}':[/bold] {len(results)} entities\n")
    for e in results[:10]:
        etype  = e.get("type", "?")
        cname  = e.get("canonical_name", e.get("en_name", "?"))
        ename  = e.get("en_name", "")
        eid    = e.get("id", "?")
        desc   = (e.get("description") or e.get("personality_summary") or "")[:80]
        status = e.get("status", "")

        console.print(
            f"  [cyan]{eid}[/cyan]  [bold]{cname}[/bold]"
            + (f" ({ename})" if ename and ename != cname else "")
            + f"  [[dim]{etype}[/dim]]"
            + (f"  ⚠️ {status}" if status and status != "alive" else "")
        )
        if desc:
            console.print(f"       [dim]{desc}[/dim]")
    console.print()


@bible_app.command("ask")
def bible_ask(
    question: str = typer.Argument(..., help="Câu hỏi về nội dung truyện"),
):
    """Hỏi AI về nội dung truyện dựa trên Bible knowledge base."""
    from littrans.bible.bible_query import BibleQuery
    store = _get_store()
    q     = BibleQuery(store)

    console.print(f"\n[bold]❓ {question}[/bold]\n")
    answer = q.ask(question)
    console.print(answer)
    console.print()


# ═══════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════

@bible_app.command("export")
def bible_export(
    fmt: str = typer.Option(
        "markdown", "--format", "-f",
        help="Định dạng: markdown | json | timeline | characters | consistency",
    ),
    scope: str = typer.Option(
        "full", "--scope", "-s",
        help="Phạm vi (chỉ cho markdown): full | characters | worldbuilding | lore",
    ),
    out: Optional[str] = typer.Option(
        None, "--out", "-o",
        help="Đường dẫn output (mặc định: Reports/bible_<format>.<ext>)",
    ),
):
    """Xuất Bible sang file."""
    from littrans.bible.bible_exporter import BibleExporter

    store = _get_store()
    exp   = BibleExporter(store)

    out_dir = Path("Reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    fmt_map = {
        "markdown"    : ("bible_report.md",       "md"),
        "json"        : ("bible_full.json",        "json"),
        "timeline"    : ("bible_timeline.md",      "md"),
        "characters"  : ("bible_characters.md",    "md"),
        "consistency" : ("bible_consistency.md",   "md"),
    }

    if fmt not in fmt_map:
        console.print(
            f"[red]❌ format phải là: {' | '.join(fmt_map)}[/red]"
        )
        raise typer.Exit(1)

    default_name, _ = fmt_map[fmt]
    output_path     = Path(out) if out else out_dir / default_name

    if fmt == "markdown":
        exp.export_markdown(output_path, scope)
    elif fmt == "json":
        exp.export_json(output_path)
    elif fmt == "timeline":
        exp.export_timeline(output_path)
    elif fmt == "characters":
        exp.export_characters_sheet(output_path)
    elif fmt == "consistency":
        from littrans.bible.cross_reference import CrossReferenceEngine
        report = CrossReferenceEngine(store).run()
        exp.export_consistency_report(output_path, report)

    console.print(f"\n[green]✅ Xuất xong:[/green] {output_path}")


# ═══════════════════════════════════════════════════════════════════
# CONSOLIDATE
# ═══════════════════════════════════════════════════════════════════

@bible_app.command("consolidate")
def bible_consolidate():
    """Consolidate staging files → database thủ công (không cần scan)."""
    store   = _get_store()
    staging = store.load_all_staging()

    if not staging:
        console.print("[yellow]⚠️  Không có staging files nào.[/yellow]")
        raise typer.Exit(0)

    console.print(f"\n[bold]🔄 Consolidate {len(staging)} staging files...[/bold]\n")

    from littrans.bible.bible_consolidator import BibleConsolidator
    result = BibleConsolidator(store).run(staging)

    # Selective cleanup
    failed_chapters: set[str] = set()
    for err in result.errors:
        ch = err.split(":")[0].strip()
        if ch:
            failed_chapters.add(ch)

    successful = [
        s.source_chapter for s in staging
        if s.source_chapter not in failed_chapters
    ]
    if successful:
        store.clear_staging(successful)

    console.print(
        f"[green]✅ Consolidated:[/green]  "
        f"+{result.chars_added} nhân vật  "
        f"+{result.entities_added} entities  "
        f"+{result.lore_chapters} lore entries"
    )
    if result.errors:
        console.print(f"[yellow]⚠️  {len(result.errors)} lỗi:[/yellow]")
        for err in result.errors[:5]:
            console.print(f"   {err}")
    if failed_chapters:
        console.print(
            f"[yellow]   Staging giữ lại cho {len(failed_chapters)} chapter lỗi[/yellow]"
        )


# ═══════════════════════════════════════════════════════════════════
# CROSS-REFERENCE
# ═══════════════════════════════════════════════════════════════════

@bible_app.command("crossref")
def bible_crossref(
    export: bool = typer.Option(
        True, "--export/--no-export",
        help="Xuất báo cáo ra Reports/bible_consistency.md",
    ),
):
    """Chạy cross-reference check — phát hiện mâu thuẫn cốt truyện."""
    from littrans.bible.cross_reference import CrossReferenceEngine

    store  = _get_store()
    engine = CrossReferenceEngine(store)

    console.print("\n[bold]🔎 Chạy cross-reference...[/bold]\n")
    report = engine.run()

    health_color = (
        "green"  if report.health_score >= 0.9 else
        "yellow" if report.health_score >= 0.7 else
        "red"
    )

    console.print(
        f"[{health_color}]Health score: {report.health_score:.0%}[/{health_color}]  "
        f"Total issues: {report.total_issues}  "
        f"(🔴 {len(report.errors)} errors  "
        f"🟡 {len(report.warnings)} warnings  "
        f"🔵 {len(report.infos)} infos)"
    )

    for issue in report.errors[:3]:
        console.print(f"  🔴 [{issue.issue_type}] {issue.description}")
    for issue in report.warnings[:3]:
        console.print(f"  🟡 [{issue.issue_type}] {issue.description}")

    if export:
        from littrans.bible.bible_exporter import BibleExporter
        out = Path("Reports") / "bible_consistency.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        BibleExporter(store).export_consistency_report(out, report)
        console.print(f"\n[green]✅ Báo cáo:[/green] {out}")

    console.print()


# ═══════════════════════════════════════════════════════════════════
# REBUILD INDEX
# ═══════════════════════════════════════════════════════════════════

@bible_app.command("rebuild-index")
def bible_rebuild_index():
    """Rebuild search index từ database files (dùng khi index bị corrupt)."""
    store = _get_store()
    console.print("\n[bold]🔧 Rebuild index...[/bold]")
    n = store.rebuild_index()
    console.print(f"[green]✅ Xong:[/green] {n} entries trong index.\n")