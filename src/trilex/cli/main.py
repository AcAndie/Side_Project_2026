"""TriLex command-line interface (Typer)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from trilex.qt_dict.applier import QTApplier
from trilex.qt_dict.parser import parse_qt_dict

DEFAULT_DICT_DIR = Path("data/dictionaries")
DEFAULT_CACHE_DIR = Path("data/cache")

app = typer.Typer(
    name="trilex",
    help="TriLex — QT-style ZH→VN translation tool.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)

db_app = typer.Typer(
    name="db",
    help="Database lifecycle commands (init / status / upgrade / downgrade).",
    no_args_is_help=True,
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)
app.add_typer(db_app, name="db")


def _alembic_config() -> Any:
    from alembic.config import Config as AlembicConfig

    ini_path = Path("alembic.ini")
    if not ini_path.exists():
        raise typer.BadParameter(
            f"alembic.ini not found at {ini_path.resolve()}. Run from project root."
        )
    return AlembicConfig(str(ini_path))


_DATA_SUBDIRS = [
    Path("data/dictionaries"),
    Path("data/cache"),
    Path("data/vault"),
    Path("data/exports"),
    Path("data/logs"),
]


@db_app.command("init")
def db_init() -> None:
    """Create the SQLite file, run all migrations, and scaffold data directories."""
    from alembic import command

    from trilex.persistence.db import DEFAULT_DB_PATH

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    for d in _DATA_SUBDIRS:
        d.mkdir(parents=True, exist_ok=True)

    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    typer.echo(f"DB ready at {DEFAULT_DB_PATH.resolve()}")
    typer.echo("\nData directories created:")
    for d in _DATA_SUBDIRS:
        typer.echo(f"  {d.resolve()}")
    typer.echo("\nNext step: drop VietPhrase.txt + Names.txt into data/dictionaries/")


@db_app.command("status")
def db_status() -> None:
    """Show the current Alembic revision applied to the database."""
    from alembic import command

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = _alembic_config()
    command.current(cfg, verbose=True)


@db_app.command("upgrade")
def db_upgrade(
    target: Annotated[
        str,
        typer.Argument(help="Revision target (e.g. 'head', '+1', or a specific id)."),
    ] = "head",
) -> None:
    """Upgrade the database to `target`."""
    from alembic import command

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = _alembic_config()
    command.upgrade(cfg, target)


@db_app.command("downgrade")
def db_downgrade(
    target: Annotated[
        str,
        typer.Argument(help="Revision target (e.g. 'base', '-1', or a specific id)."),
    ],
) -> None:
    """Downgrade the database to `target`. Destructive — use with care."""
    from alembic import command

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = _alembic_config()
    command.downgrade(cfg, target)


@app.command()
def convert(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="ZH text file (UTF-8) to convert.",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write result to this file. Default: stdout."),
    ] = None,
    custom_dict: Annotated[
        Path | None,
        typer.Option(
            "--custom-dict",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Per-novel glossary (QT format). Highest priority tier.",
        ),
    ] = None,
    dict_dir: Annotated[
        Path,
        typer.Option("--dict-dir", help="Directory containing QT dictionary files."),
    ] = DEFAULT_DICT_DIR,
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir", help="Where to cache built automatons."),
    ] = DEFAULT_CACHE_DIR,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress stats printout."),
    ] = False,
) -> None:
    """Apply the QT dictionary chain to a ZH text file."""
    logging.basicConfig(level=logging.ERROR)

    text = input_file.read_text(encoding="utf-8")

    glossary: dict[str, str] | None = None
    if custom_dict is not None:
        gd = parse_qt_dict(custom_dict)
        glossary = {k: v[0] for k, v in gd.entries.items()}

    applier = QTApplier(dict_dir, cache_dir=cache_dir)
    result = applier.convert_detail(text, custom_glossary=glossary)

    if output is not None:
        output.write_text(result.text, encoding="utf-8")
        if not quiet:
            typer.echo(f"Wrote {len(result.text)} chars to {output}", err=True)
    else:
        typer.echo(result.text)

    if quiet:
        return

    s = result.stats
    typer.echo("", err=True)
    typer.echo("=== Stats ===", err=True)
    typer.echo(f"  input_chars : {s.input_chars:,}", err=True)
    typer.echo(f"  output_chars: {s.output_chars:,}", err=True)
    typer.echo(f"  elapsed     : {s.elapsed_seconds * 1000:.1f} ms", err=True)
    typer.echo(f"  luat_nhan   : {s.luat_nhan_substitutions} substitutions", err=True)
    for tier_name, count in s.tier_match_counts.items():
        typer.echo(f"  [{tier_name:<11}] {count:>6,} matches", err=True)


@app.command(name="dict-info")
def dict_info(
    dict_dir: Annotated[
        Path,
        typer.Option("--dict-dir", help="Directory containing QT dictionary files."),
    ] = DEFAULT_DICT_DIR,
) -> None:
    """List loaded dictionary files with size, entry count, and encoding."""
    logging.basicConfig(level=logging.ERROR)

    if not dict_dir.exists():
        typer.echo(f"Dict dir not found: {dict_dir}", err=True)
        raise typer.Exit(1)

    files = sorted(dict_dir.glob("*.txt"))
    if not files:
        typer.echo(f"No .txt files in {dict_dir}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Dict directory: {dict_dir.resolve()}")
    typer.echo("")
    typer.echo(f"{'File':<28} {'Size':>10}  {'Entries':>10}  {'Skipped':>8}  Encoding")
    typer.echo("-" * 78)

    total_entries = 0
    total_size = 0
    for f in files:
        size = f.stat().st_size
        total_size += size
        try:
            qt = parse_qt_dict(f)
            total_entries += qt.meta.count
            typer.echo(
                f"{f.name:<28} {_human_size(size):>10}  "
                f"{qt.meta.count:>10,}  {qt.meta.skipped_lines:>8,}  "
                f"{qt.meta.encoding}"
            )
        except Exception as e:  # noqa: BLE001
            typer.echo(f"{f.name:<28} ERROR: {e}", err=True)

    typer.echo("-" * 78)
    typer.echo(
        f"Total: {total_entries:,} entries  "
        f"{_human_size(total_size)}  across {len(files)} files"
    )


@app.command(name="check-config")
def check_config() -> None:
    """Print loaded settings; API keys are masked (first 6 + last 6 chars only)."""
    logging.basicConfig(level=logging.ERROR)

    from pydantic import ValidationError

    from trilex.config import ENV_FILE, get_settings, mask_key

    try:
        s = get_settings()
    except ValidationError as e:
        typer.echo(f"Config invalid: {e}", err=True)
        typer.echo(f"Edit: {ENV_FILE}", err=True)
        raise typer.Exit(1) from e

    typer.echo("=== TriLex Config ===")
    typer.echo(f"  env_file       : {ENV_FILE}")
    typer.echo(f"  GEMINI_API_KEY : {mask_key(s.gemini_api_key.get_secret_value())}")
    if s.fallback_key_1 is not None:
        typer.echo(f"  FALLBACK_KEY_1 : {mask_key(s.fallback_key_1.get_secret_value())}")
    else:
        typer.echo("  FALLBACK_KEY_1 : (not set)")
    if s.fallback_key_2 is not None:
        typer.echo(f"  FALLBACK_KEY_2 : {mask_key(s.fallback_key_2.get_secret_value())}")
    else:
        typer.echo("  FALLBACK_KEY_2 : (not set)")
    typer.echo(f"  gemini_model   : {s.gemini_model}")
    typer.echo(f"  request_timeout: {s.request_timeout}s")
    typer.echo(f"  max_retries    : {s.max_retries}")
    typer.echo(f"  total keys     : {len(s.all_keys())}")


@app.command(name="test-llm")
def test_llm(
    prompt: Annotated[
        str,
        typer.Argument(help="Prompt text to send to the LLM."),
    ],
    system: Annotated[
        str | None,
        typer.Option("--system", "-s", help="Optional system instruction."),
    ] = None,
    max_tokens: Annotated[
        int,
        typer.Option("--max-tokens", help="Generation cap."),
    ] = 1024,
) -> None:
    """Send one prompt to the configured Gemini provider and print the result."""
    import asyncio

    from pydantic import ValidationError

    from trilex.config import ENV_FILE
    from trilex.providers import GeminiProvider, ProviderError

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        provider = GeminiProvider.from_settings()
    except ValidationError as e:
        typer.echo(f"Config invalid: {e}", err=True)
        typer.echo(f"Edit: {ENV_FILE}", err=True)
        raise typer.Exit(1) from e

    try:
        response = asyncio.run(provider.complete(prompt, system=system, max_tokens=max_tokens))
    except ProviderError as e:
        typer.echo(f"Provider error: {type(e).__name__}: {e}", err=True)
        raise typer.Exit(2) from e

    typer.echo(response.text)
    typer.echo("", err=True)
    typer.echo("=== Stats ===", err=True)
    typer.echo(f"  model         : {response.model}", err=True)
    typer.echo(f"  tokens_used   : {response.tokens_used}", err=True)
    typer.echo(f"  latency_ms    : {response.latency_ms:.1f}", err=True)
    typer.echo(f"  finish_reason : {response.finish_reason}", err=True)


@app.command(name="ui")
def ui_cmd(
    port: Annotated[
        int,
        typer.Option("--port", help="Streamlit server port."),
    ] = 8501,
    headless: Annotated[
        bool,
        typer.Option("--headless/--browser", help="Skip opening a browser tab."),
    ] = False,
) -> None:
    """Launch the Streamlit UI (`streamlit run src/trilex/ui/app.py`)."""
    import subprocess

    app_path = Path(__file__).resolve().parents[1] / "ui" / "app.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(port),
        "--browser.gatherUsageStats",
        "false",
    ]
    if headless:
        cmd.extend(["--server.headless", "true"])
    typer.echo(f"Launching: {' '.join(cmd)}", err=True)
    raise typer.Exit(subprocess.call(cmd))


@app.command(name="translate")
def translate(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Source chapter file (UTF-8).",
        ),
    ],
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            "-m",
            help="Pipeline mode: convert | polish | side_by_side.",
        ),
    ] = "polish",
    source_lang: Annotated[
        str,
        typer.Option("--source-lang", help="Source language code."),
    ] = "zh",
    target_lang: Annotated[
        str,
        typer.Option("--target-lang", help="Target language code."),
    ] = "vn",
    style_pack: Annotated[
        str | None,
        typer.Option(
            "--style-pack",
            help="Style pack id 'genre.target_lang' (e.g. 'tu_tien.vn'). "
            "Default: derived from --genre + --target-lang.",
        ),
    ] = None,
    genre: Annotated[
        str,
        typer.Option("--genre", help="Genre for style pack lookup."),
    ] = "tu_tien",
    dict_dir: Annotated[
        Path,
        typer.Option("--dict-dir"),
    ] = DEFAULT_DICT_DIR,
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir"),
    ] = DEFAULT_CACHE_DIR,
    custom_dict: Annotated[
        Path | None,
        typer.Option(
            "--custom-dict",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Per-novel glossary (QT format) → injected as custom_glossary.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write final text to file (default: stdout)."),
    ] = None,
    log_path: Annotated[
        Path,
        typer.Option("--log-path", help="JSONL run log."),
    ] = Path("data/logs/translate.jsonl"),
    max_tokens: Annotated[
        int,
        typer.Option("--max-tokens"),
    ] = 4000,
    width: Annotated[
        int,
        typer.Option("--width", help="Column width for side_by_side view."),
    ] = 50,
) -> None:
    """Run the full pipeline (preprocess → QT → polish → postprocess) on one chapter."""
    import asyncio
    import json
    from datetime import UTC, datetime

    from pydantic import ValidationError

    from trilex.config import ENV_FILE
    from trilex.core.models.project import ProjectConfig
    from trilex.core.models.term import Term
    from trilex.core.pipeline import translate_chapter
    from trilex.providers import GeminiProvider, ProviderError

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if mode not in ("convert", "polish", "side_by_side"):
        typer.echo(f"Invalid --mode: {mode}", err=True)
        raise typer.Exit(1)
    if source_lang not in ("zh", "vn", "en") or target_lang not in ("zh", "vn", "en"):
        typer.echo("source/target lang must be one of: zh, vn, en", err=True)
        raise typer.Exit(1)

    source_text = input_file.read_text(encoding="utf-8")
    if not source_text.strip():
        typer.echo("Input file is empty.", err=True)
        raise typer.Exit(1)

    glossary: tuple[Term, ...] = ()
    if custom_dict is not None:
        gd = parse_qt_dict(custom_dict)
        glossary = tuple(Term(source=k, target=v[0]) for k, v in gd.entries.items() if v)

    cfg = ProjectConfig(
        source_lang=source_lang,  # type: ignore[arg-type]
        target_lang=target_lang,  # type: ignore[arg-type]
        genre=genre,
        style_pack=style_pack,
        custom_glossary=glossary,
        dict_dir=dict_dir,
        cache_dir=cache_dir,
        max_tokens=max_tokens,
    )

    provider = None
    if mode != "convert":
        try:
            provider = GeminiProvider.from_settings()
        except ValidationError as e:
            typer.echo(f"Config invalid: {e}", err=True)
            typer.echo(f"Edit: {ENV_FILE}", err=True)
            raise typer.Exit(1) from e

    try:
        result = asyncio.run(
            translate_chapter(
                source_text,
                cfg,
                mode=mode,  # type: ignore[arg-type]
                provider=provider,
            )
        )
    except ProviderError as e:
        typer.echo(f"Provider error: {type(e).__name__}: {e}", err=True)
        raise typer.Exit(2) from e

    # Output
    if mode == "side_by_side":
        _print_three_columns(
            result.source_text,
            result.convert_text or "(no QT pass)",
            result.final_text,
            width=width,
        )
    else:
        if output is not None:
            output.write_text(result.final_text, encoding="utf-8")
            typer.echo(f"Wrote {len(result.final_text)} chars to {output}", err=True)
        else:
            typer.echo(result.final_text)

    # Stats
    typer.echo("", err=True)
    typer.echo("=== Stats ===", err=True)
    typer.echo(f"  mode          : {result.mode}", err=True)
    typer.echo(f"  state         : {result.state}", err=True)
    typer.echo(f"  total_ms      : {result.total_elapsed_ms:.1f}", err=True)
    typer.echo(f"  tokens_used   : {result.tokens_used}", err=True)
    if result.model:
        typer.echo(f"  model         : {result.model}", err=True)
    for st in result.stage_stats:
        typer.echo(f"  [{st.name:<11}] {st.elapsed_ms:>8.1f} ms  {st.extra or ''}", err=True)
    if result.warnings:
        typer.echo(f"  warnings      : {len(result.warnings)}", err=True)
        for w in result.warnings:
            typer.echo(f"    - {w}", err=True)
    else:
        typer.echo("  warnings      : none", err=True)

    # JSONL log
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": datetime.now(UTC).isoformat(),
                        "input_file": str(input_file),
                        "mode": result.mode,
                        "state": result.state,
                        "source_lang": cfg.source_lang,
                        "target_lang": cfg.target_lang,
                        "genre": cfg.genre,
                        "input_chars": len(source_text),
                        "output_chars": len(result.final_text),
                        "tokens_used": result.tokens_used,
                        "model": result.model,
                        "total_elapsed_ms": round(result.total_elapsed_ms, 1),
                        "stages": [
                            {"name": s.name, "elapsed_ms": round(s.elapsed_ms, 1)}
                            for s in result.stage_stats
                        ],
                        "warning_count": len(result.warnings),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except OSError as e:
        typer.echo(f"Failed to write log: {e}", err=True)

    if result.state == "failed":
        raise typer.Exit(2)


@app.command(name="polish-demo")
def polish_demo(
    input_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="ZH chapter file (UTF-8).",
        ),
    ],
    genre: Annotated[
        str,
        typer.Option("--genre", help="Style pack genre."),
    ] = "tu_tien",
    target_lang: Annotated[
        str,
        typer.Option("--target-lang", help="Style pack target language."),
    ] = "vn",
    dict_dir: Annotated[
        Path,
        typer.Option("--dict-dir"),
    ] = DEFAULT_DICT_DIR,
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir"),
    ] = DEFAULT_CACHE_DIR,
    max_tokens: Annotated[
        int,
        typer.Option("--max-tokens"),
    ] = 4000,
    width: Annotated[
        int,
        typer.Option("--width", help="Column width (chars) for side-by-side view."),
    ] = 50,
) -> None:
    """Run QT convert + LLM polish on a ZH chapter and show source/convert/polish."""
    import asyncio

    from pydantic import ValidationError

    from trilex.config import ENV_FILE
    from trilex.core.pipeline.stages.polish import polish
    from trilex.core.style_pack import StylePackError, get_style_pack
    from trilex.providers import GeminiProvider, ProviderError

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    source_text = input_file.read_text(encoding="utf-8").strip()
    if not source_text:
        typer.echo("Input file is empty.", err=True)
        raise typer.Exit(1)

    try:
        pack = get_style_pack(genre, target_lang)
    except StylePackError as e:
        typer.echo(f"Style pack error: {e}", err=True)
        raise typer.Exit(1) from e

    applier = QTApplier(dict_dir, cache_dir=cache_dir)
    convert_result = applier.convert_detail(source_text)

    try:
        provider = GeminiProvider.from_settings()
    except ValidationError as e:
        typer.echo(f"Config invalid: {e}", err=True)
        typer.echo(f"Edit: {ENV_FILE}", err=True)
        raise typer.Exit(1) from e

    try:
        polish_result = asyncio.run(
            polish(
                original=source_text,
                converted=convert_result.text,
                style_pack=pack,
                provider=provider,
                max_tokens=max_tokens,
            )
        )
    except ProviderError as e:
        typer.echo(f"Provider error: {type(e).__name__}: {e}", err=True)
        raise typer.Exit(2) from e

    _print_three_columns(source_text, convert_result.text, polish_result.text, width=width)

    typer.echo("", err=True)
    typer.echo("=== Stats ===", err=True)
    typer.echo(f"  qt_elapsed_ms : {convert_result.stats.elapsed_seconds * 1000:.1f}", err=True)
    typer.echo(f"  qt_input      : {convert_result.stats.input_chars} chars", err=True)
    typer.echo(f"  qt_output     : {convert_result.stats.output_chars} chars", err=True)
    typer.echo(f"  llm_model     : {polish_result.model}", err=True)
    typer.echo(f"  llm_tokens    : {polish_result.tokens_used}", err=True)
    typer.echo(f"  llm_latency_ms: {polish_result.latency_ms:.1f}", err=True)
    typer.echo(f"  polish_chars  : {len(polish_result.text)}", err=True)
    if polish_result.warnings:
        typer.echo(f"  warnings      : {len(polish_result.warnings)}", err=True)
        for w in polish_result.warnings:
            typer.echo(f"    - {w}", err=True)
    else:
        typer.echo("  warnings      : none", err=True)


def _wcwidth(s: str) -> int:
    """Approximate East-Asian display width of `s` (counts CJK chars as 2)."""
    import unicodedata

    width = 0
    for ch in s:
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


def _wrap_visual(text: str, width: int) -> list[str]:
    """Wrap `text` to `width` display columns, respecting CJK double-width."""
    lines: list[str] = []
    for para in text.split("\n"):
        cur: list[str] = []
        cur_w = 0
        for ch in para:
            cw = 2 if _wcwidth(ch) == 2 else 1
            if cur_w + cw > width:
                lines.append("".join(cur))
                cur = [ch]
                cur_w = cw
            else:
                cur.append(ch)
                cur_w += cw
        lines.append("".join(cur))
    return lines


def _pad_visual(s: str, width: int) -> str:
    return s + " " * max(0, width - _wcwidth(s))


def _print_three_columns(left: str, mid: str, right: str, *, width: int) -> None:
    headers = ("SOURCE (ZH)", "CONVERT (QT)", "POLISH (LLM)")
    bar = "+" + "+".join(["-" * (width + 2)] * 3) + "+"
    typer.echo(bar)
    typer.echo("| " + " | ".join(_pad_visual(h, width) for h in headers) + " |")
    typer.echo(bar)

    left_lines = _wrap_visual(left, width)
    mid_lines = _wrap_visual(mid, width)
    right_lines = _wrap_visual(right, width)
    rows = max(len(left_lines), len(mid_lines), len(right_lines))
    left_lines += [""] * (rows - len(left_lines))
    mid_lines += [""] * (rows - len(mid_lines))
    right_lines += [""] * (rows - len(right_lines))
    for lline, mline, rline in zip(left_lines, mid_lines, right_lines, strict=False):
        typer.echo(
            f"| {_pad_visual(lline, width)} | {_pad_visual(mline, width)} | "
            f"{_pad_visual(rline, width)} |"
        )
    typer.echo(bar)


def _human_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def _ensure_utf8_console() -> None:
    """Enable UTF-8 + ANSI escapes on Windows so unicode help text renders.

    Why: rich's legacy-Windows renderer encodes through the active console code
    page (cp1252 by default), which crashes on `→` / `—`. Switching to code
    page 65001 *and* enabling VT processing makes rich pick its ANSI path.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    if sys.platform != "win32":
        return
    import ctypes

    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleOutputCP(65001)
    kernel32.SetConsoleCP(65001)
    # Enable VIRTUAL_TERMINAL_PROCESSING (0x0004) on stdout + stderr.
    for handle_id in (-11, -12):
        h = kernel32.GetStdHandle(handle_id)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
            kernel32.SetConsoleMode(h, mode.value | 0x0004)


def _entrypoint() -> None:
    """Console-script entrypoint. Exits with the Typer return code."""
    _ensure_utf8_console()

    from trilex.logging_config import setup_logging

    setup_logging(level=logging.INFO)
    sys.exit(app() or 0)


if __name__ == "__main__":
    _entrypoint()
