"""CLI surface tests via Typer's CliRunner.

We exercise every subcommand at least once (happy + a few error paths),
mocking external boundaries (Alembic, the Gemini SDK) so nothing touches
the network or the real ``data/`` directory at test time.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from trilex.cli import main as cli_main
from trilex.providers.base import ProviderResponse, QuotaExceededError

runner = CliRunner()


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
def mini_dict_dir(tmp_path: Path) -> Path:
    """A tiny but parseable QT dict directory."""
    d = tmp_path / "dict"
    d.mkdir()
    (d / "Vietphrase.txt").write_text("李青=Lý Thanh\n张老=Trương lão\n", encoding="utf-8")
    (d / "Names.txt").write_text("李青=Lý Thanh\n", encoding="utf-8")
    (d / "LuatNhan.txt").write_text("青云=thanh vân\n", encoding="utf-8")
    return d


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "cache"


@pytest.fixture
def sample_zh_file(tmp_path: Path) -> Path:
    p = tmp_path / "ch.txt"
    p.write_text("李青走进青云宗，向张老行礼。", encoding="utf-8")
    return p


@pytest.fixture
def fake_provider() -> MagicMock:
    """A GeminiProvider stand-in whose `.complete()` returns a fixed response."""
    p = MagicMock()
    p.name = "fake"

    async def _complete(prompt: str, system: str | None = None, max_tokens: int = 2048):
        return ProviderResponse(
            text="Lý Thanh bước vào Thanh Vân tông, thi lễ với Trương lão.",
            tokens_used=42,
            model="fake-1",
            latency_ms=12.3,
            finish_reason="stop",
        )

    p.complete = _complete
    return p


# --------------------------------------------------------------------------- #
# convert                                                                     #
# --------------------------------------------------------------------------- #


def test_convert_stdout(mini_dict_dir: Path, cache_dir: Path, sample_zh_file: Path) -> None:
    result = runner.invoke(
        cli_main.app,
        [
            "convert",
            str(sample_zh_file),
            "--dict-dir",
            str(mini_dict_dir),
            "--cache-dir",
            str(cache_dir),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert "Lý Thanh" in result.stdout
    assert "Stats" in result.stderr


def test_convert_to_file_quiet(
    mini_dict_dir: Path, cache_dir: Path, sample_zh_file: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out.txt"
    result = runner.invoke(
        cli_main.app,
        [
            "convert",
            str(sample_zh_file),
            "-o",
            str(out),
            "--dict-dir",
            str(mini_dict_dir),
            "--cache-dir",
            str(cache_dir),
            "--quiet",
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert out.exists()
    assert "Lý Thanh" in out.read_text(encoding="utf-8")
    # quiet → no stats block
    assert "Stats" not in result.stderr


def test_convert_with_custom_dict(
    mini_dict_dir: Path,
    cache_dir: Path,
    sample_zh_file: Path,
    tmp_path: Path,
) -> None:
    custom = tmp_path / "custom.txt"
    custom.write_text("青云宗=Phái Thanh Vân\n", encoding="utf-8")
    result = runner.invoke(
        cli_main.app,
        [
            "convert",
            str(sample_zh_file),
            "--dict-dir",
            str(mini_dict_dir),
            "--cache-dir",
            str(cache_dir),
            "--custom-dict",
            str(custom),
        ],
    )
    assert result.exit_code == 0, result.stderr


# --------------------------------------------------------------------------- #
# dict-info                                                                   #
# --------------------------------------------------------------------------- #


def test_dict_info_happy(mini_dict_dir: Path) -> None:
    result = runner.invoke(cli_main.app, ["dict-info", "--dict-dir", str(mini_dict_dir)])
    assert result.exit_code == 0, result.stderr
    assert "Vietphrase.txt" in result.stdout
    assert "Total" in result.stdout


def test_dict_info_missing_dir(tmp_path: Path) -> None:
    result = runner.invoke(cli_main.app, ["dict-info", "--dict-dir", str(tmp_path / "nope")])
    assert result.exit_code == 1


def test_dict_info_empty_dir(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(cli_main.app, ["dict-info", "--dict-dir", str(empty)])
    assert result.exit_code == 1


# --------------------------------------------------------------------------- #
# check-config                                                                #
# --------------------------------------------------------------------------- #


def test_check_config_with_valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from trilex import config as cfg_mod

    cfg_mod.get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTESTKEYxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    monkeypatch.delenv("FALLBACK_KEY_1", raising=False)
    monkeypatch.delenv("FALLBACK_KEY_2", raising=False)

    result = runner.invoke(cli_main.app, ["check-config"])
    cfg_mod.get_settings.cache_clear()
    assert result.exit_code == 0, result.stderr
    assert "TriLex Config" in result.stdout
    assert "GEMINI_API_KEY" in result.stdout
    assert "AIzaSy" in result.stdout  # masked head visible


def test_check_config_with_fallback_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    from trilex import config as cfg_mod

    cfg_mod.get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyMAINxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    monkeypatch.setenv("FALLBACK_KEY_1", "AIzaSyFB1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    monkeypatch.setenv("FALLBACK_KEY_2", "AIzaSyFB2xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    result = runner.invoke(cli_main.app, ["check-config"])
    cfg_mod.get_settings.cache_clear()
    assert result.exit_code == 0, result.stderr
    assert "FALLBACK_KEY_1" in result.stdout
    assert "FALLBACK_KEY_2" in result.stdout


def test_check_config_invalid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from trilex import config as cfg_mod

    cfg_mod.get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "   ")  # empty after strip → invalid

    result = runner.invoke(cli_main.app, ["check-config"])
    cfg_mod.get_settings.cache_clear()
    assert result.exit_code == 1


# --------------------------------------------------------------------------- #
# test-llm                                                                    #
# --------------------------------------------------------------------------- #


def test_test_llm_happy(monkeypatch: pytest.MonkeyPatch, fake_provider: MagicMock) -> None:
    from trilex import config as cfg_mod

    cfg_mod.get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyMAINxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    import trilex.providers as providers_mod

    with patch.object(
        providers_mod.GeminiProvider,
        "from_settings",
        return_value=fake_provider,
    ):
        result = runner.invoke(cli_main.app, ["test-llm", "ping"])
    cfg_mod.get_settings.cache_clear()
    assert result.exit_code == 0, result.stderr
    assert "Lý Thanh" in result.stdout
    assert "Stats" in result.stderr


def test_test_llm_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trilex import config as cfg_mod

    cfg_mod.get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyMAINxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    failing = MagicMock()

    async def _boom(*a: object, **kw: object) -> ProviderResponse:
        raise QuotaExceededError("quota")

    failing.complete = _boom

    import trilex.providers as providers_mod

    with patch.object(
        providers_mod.GeminiProvider,
        "from_settings",
        return_value=failing,
    ):
        result = runner.invoke(cli_main.app, ["test-llm", "ping"])
    cfg_mod.get_settings.cache_clear()
    assert result.exit_code == 2


def test_test_llm_invalid_config(monkeypatch: pytest.MonkeyPatch) -> None:
    from trilex import config as cfg_mod

    cfg_mod.get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "   ")

    result = runner.invoke(cli_main.app, ["test-llm", "ping"])
    cfg_mod.get_settings.cache_clear()
    assert result.exit_code == 1


# --------------------------------------------------------------------------- #
# translate                                                                   #
# --------------------------------------------------------------------------- #


def test_translate_convert_mode(
    mini_dict_dir: Path, cache_dir: Path, sample_zh_file: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out.txt"
    log = tmp_path / "logs" / "translate.jsonl"
    result = runner.invoke(
        cli_main.app,
        [
            "translate",
            str(sample_zh_file),
            "--mode",
            "convert",
            "--dict-dir",
            str(mini_dict_dir),
            "--cache-dir",
            str(cache_dir),
            "--output",
            str(out),
            "--log-path",
            str(log),
        ],
    )
    assert result.exit_code == 0, result.stderr
    assert out.exists()
    assert log.exists()
    assert "Lý Thanh" in out.read_text(encoding="utf-8")


def test_translate_polish_mode(
    mini_dict_dir: Path,
    cache_dir: Path,
    sample_zh_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_provider: MagicMock,
) -> None:
    from trilex import config as cfg_mod

    cfg_mod.get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyMAINxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    log = tmp_path / "translate.jsonl"
    import trilex.providers as providers_mod

    with patch.object(
        providers_mod.GeminiProvider,
        "from_settings",
        return_value=fake_provider,
    ):
        result = runner.invoke(
            cli_main.app,
            [
                "translate",
                str(sample_zh_file),
                "--mode",
                "polish",
                "--dict-dir",
                str(mini_dict_dir),
                "--cache-dir",
                str(cache_dir),
                "--log-path",
                str(log),
            ],
        )
    cfg_mod.get_settings.cache_clear()
    assert result.exit_code == 0, result.stderr
    assert "Trương lão" in result.stdout or "Thanh Vân" in result.stdout


def test_translate_side_by_side(
    mini_dict_dir: Path,
    cache_dir: Path,
    sample_zh_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_provider: MagicMock,
) -> None:
    from trilex import config as cfg_mod

    cfg_mod.get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyMAINxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    log = tmp_path / "translate.jsonl"
    import trilex.providers as providers_mod

    with patch.object(
        providers_mod.GeminiProvider,
        "from_settings",
        return_value=fake_provider,
    ):
        result = runner.invoke(
            cli_main.app,
            [
                "translate",
                str(sample_zh_file),
                "--mode",
                "side_by_side",
                "--dict-dir",
                str(mini_dict_dir),
                "--cache-dir",
                str(cache_dir),
                "--log-path",
                str(log),
                "--width",
                "20",
            ],
        )
    cfg_mod.get_settings.cache_clear()
    assert result.exit_code == 0, result.stderr
    assert "SOURCE" in result.stdout
    assert "CONVERT" in result.stdout
    assert "POLISH" in result.stdout


def test_translate_invalid_mode(
    mini_dict_dir: Path, cache_dir: Path, sample_zh_file: Path, tmp_path: Path
) -> None:
    log = tmp_path / "translate.jsonl"
    result = runner.invoke(
        cli_main.app,
        [
            "translate",
            str(sample_zh_file),
            "--mode",
            "garbage",
            "--dict-dir",
            str(mini_dict_dir),
            "--cache-dir",
            str(cache_dir),
            "--log-path",
            str(log),
        ],
    )
    assert result.exit_code == 1
    assert "Invalid --mode" in result.stderr


def test_translate_invalid_lang(
    mini_dict_dir: Path, cache_dir: Path, sample_zh_file: Path, tmp_path: Path
) -> None:
    log = tmp_path / "translate.jsonl"
    result = runner.invoke(
        cli_main.app,
        [
            "translate",
            str(sample_zh_file),
            "--mode",
            "convert",
            "--source-lang",
            "jp",  # not in {zh,vn,en}
            "--dict-dir",
            str(mini_dict_dir),
            "--cache-dir",
            str(cache_dir),
            "--log-path",
            str(log),
        ],
    )
    assert result.exit_code == 1
    assert "source/target lang" in result.stderr


def test_translate_empty_input(tmp_path: Path, mini_dict_dir: Path, cache_dir: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_text("   \n", encoding="utf-8")
    log = tmp_path / "translate.jsonl"
    result = runner.invoke(
        cli_main.app,
        [
            "translate",
            str(empty),
            "--mode",
            "convert",
            "--dict-dir",
            str(mini_dict_dir),
            "--cache-dir",
            str(cache_dir),
            "--log-path",
            str(log),
        ],
    )
    assert result.exit_code == 1
    assert "empty" in result.stderr.lower()


def test_translate_with_custom_dict(
    mini_dict_dir: Path,
    cache_dir: Path,
    sample_zh_file: Path,
    tmp_path: Path,
) -> None:
    custom = tmp_path / "custom.txt"
    custom.write_text("青云宗=Phái Thanh Vân\n", encoding="utf-8")
    log = tmp_path / "translate.jsonl"
    result = runner.invoke(
        cli_main.app,
        [
            "translate",
            str(sample_zh_file),
            "--mode",
            "convert",
            "--dict-dir",
            str(mini_dict_dir),
            "--cache-dir",
            str(cache_dir),
            "--custom-dict",
            str(custom),
            "--log-path",
            str(log),
        ],
    )
    assert result.exit_code == 0, result.stderr


def test_translate_polish_invalid_config(
    mini_dict_dir: Path,
    cache_dir: Path,
    sample_zh_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trilex import config as cfg_mod

    cfg_mod.get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    log = tmp_path / "translate.jsonl"
    result = runner.invoke(
        cli_main.app,
        [
            "translate",
            str(sample_zh_file),
            "--mode",
            "polish",
            "--dict-dir",
            str(mini_dict_dir),
            "--cache-dir",
            str(cache_dir),
            "--log-path",
            str(log),
        ],
    )
    cfg_mod.get_settings.cache_clear()
    assert result.exit_code == 1


# --------------------------------------------------------------------------- #
# polish-demo                                                                 #
# --------------------------------------------------------------------------- #


def test_polish_demo_happy(
    mini_dict_dir: Path,
    cache_dir: Path,
    sample_zh_file: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_provider: MagicMock,
) -> None:
    from trilex import config as cfg_mod

    cfg_mod.get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyMAINxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    import trilex.providers as providers_mod

    with patch.object(
        providers_mod.GeminiProvider,
        "from_settings",
        return_value=fake_provider,
    ):
        result = runner.invoke(
            cli_main.app,
            [
                "polish-demo",
                str(sample_zh_file),
                "--dict-dir",
                str(mini_dict_dir),
                "--cache-dir",
                str(cache_dir),
                "--width",
                "30",
            ],
        )
    cfg_mod.get_settings.cache_clear()
    assert result.exit_code == 0, result.stderr
    assert "SOURCE" in result.stdout


def test_polish_demo_empty_input(
    tmp_path: Path,
    mini_dict_dir: Path,
    cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_text("\n", encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyMAINxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    result = runner.invoke(
        cli_main.app,
        [
            "polish-demo",
            str(empty),
            "--dict-dir",
            str(mini_dict_dir),
            "--cache-dir",
            str(cache_dir),
        ],
    )
    assert result.exit_code == 1


def test_polish_demo_unknown_style_pack(
    mini_dict_dir: Path,
    cache_dir: Path,
    sample_zh_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyMAINxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    result = runner.invoke(
        cli_main.app,
        [
            "polish-demo",
            str(sample_zh_file),
            "--genre",
            "definitely_not_a_real_genre_xyz",
            "--dict-dir",
            str(mini_dict_dir),
            "--cache-dir",
            str(cache_dir),
        ],
    )
    assert result.exit_code == 1


def test_polish_demo_invalid_config(
    mini_dict_dir: Path,
    cache_dir: Path,
    sample_zh_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from trilex import config as cfg_mod

    cfg_mod.get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    result = runner.invoke(
        cli_main.app,
        [
            "polish-demo",
            str(sample_zh_file),
            "--dict-dir",
            str(mini_dict_dir),
            "--cache-dir",
            str(cache_dir),
        ],
    )
    cfg_mod.get_settings.cache_clear()
    assert result.exit_code == 1


# --------------------------------------------------------------------------- #
# db subcommands                                                              #
# --------------------------------------------------------------------------- #


def test_db_init_missing_alembic_ini(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When alembic.ini is absent we exit with a BadParameter."""
    monkeypatch.chdir(tmp_path)  # No alembic.ini here.
    result = runner.invoke(cli_main.app, ["db", "init"])
    assert result.exit_code != 0


def test_db_init_invokes_alembic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """alembic.command.upgrade is called with the loaded Config + 'head'."""
    monkeypatch.chdir(Path(__file__).resolve().parents[2])  # project root w/ alembic.ini

    fake_cmd = MagicMock()
    with (
        patch("trilex.cli.main._alembic_config", return_value="CFG"),
        patch.dict(sys.modules, {}),
        patch("alembic.command", fake_cmd),
    ):
        # Patch DEFAULT_DB_PATH to tmp so the real file isn't touched.
        monkeypatch.setattr(
            "trilex.persistence.db.DEFAULT_DB_PATH",
            tmp_path / "tdb.sqlite",
        )
        result = runner.invoke(cli_main.app, ["db", "init"])
    assert result.exit_code == 0, result.stderr
    fake_cmd.upgrade.assert_called_once_with("CFG", "head")


def test_db_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(Path(__file__).resolve().parents[2])
    fake_cmd = MagicMock()
    with (
        patch("trilex.cli.main._alembic_config", return_value="CFG"),
        patch("alembic.command", fake_cmd),
    ):
        result = runner.invoke(cli_main.app, ["db", "status"])
    assert result.exit_code == 0, result.stderr
    fake_cmd.current.assert_called_once_with("CFG", verbose=True)


def test_db_upgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(Path(__file__).resolve().parents[2])
    fake_cmd = MagicMock()
    with (
        patch("trilex.cli.main._alembic_config", return_value="CFG"),
        patch("alembic.command", fake_cmd),
    ):
        result = runner.invoke(cli_main.app, ["db", "upgrade", "+1"])
    assert result.exit_code == 0, result.stderr
    fake_cmd.upgrade.assert_called_once_with("CFG", "+1")


def test_db_downgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(Path(__file__).resolve().parents[2])
    fake_cmd = MagicMock()
    with (
        patch("trilex.cli.main._alembic_config", return_value="CFG"),
        patch("alembic.command", fake_cmd),
    ):
        result = runner.invoke(cli_main.app, ["db", "downgrade", "--", "-1"])
    assert result.exit_code == 0, result.stderr
    fake_cmd.downgrade.assert_called_once_with("CFG", "-1")


# --------------------------------------------------------------------------- #
# UI launcher                                                                 #
# --------------------------------------------------------------------------- #


def test_ui_cmd_invokes_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """The `ui` command shells out to Streamlit. Stub subprocess.call to verify."""
    called: dict[str, list[str]] = {}

    def _fake_call(cmd: list[str], *args: object, **kw: object) -> int:
        called["cmd"] = list(cmd)
        return 0

    monkeypatch.setattr("subprocess.call", _fake_call)
    result = runner.invoke(cli_main.app, ["ui", "--port", "9999", "--headless"])
    assert result.exit_code == 0, result.stderr
    assert called["cmd"][:3] == [sys.executable, "-m", "streamlit"]
    assert "9999" in called["cmd"]
    assert "true" in called["cmd"]  # --server.headless true


def test_ui_cmd_propagates_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("subprocess.call", lambda *a, **kw: 3)
    result = runner.invoke(cli_main.app, ["ui"])
    assert result.exit_code == 3


# --------------------------------------------------------------------------- #
# Helper smoke tests                                                          #
# --------------------------------------------------------------------------- #


def test_human_size_units() -> None:
    assert cli_main._human_size(10) == "10 B"
    assert cli_main._human_size(2048).endswith("KB")
    assert cli_main._human_size(5 * 1024 * 1024).endswith("MB")


def test_wcwidth_handles_cjk() -> None:
    assert cli_main._wcwidth("a") == 1
    assert cli_main._wcwidth("青") == 2
    assert cli_main._wcwidth("ab青") == 4


def test_wrap_visual_respects_double_width() -> None:
    lines = cli_main._wrap_visual("青青青青青", 4)
    # 5 chars × width 2 = 10 cols; each line holds 2 chars (4 cols). 3 lines.
    assert len(lines) == 3


def test_pad_visual_pads_to_width() -> None:
    assert len(cli_main._pad_visual("ab", 5)) == 5
    # CJK occupies 2 cols → "青a" already 3 cols, pad 2 more
    assert cli_main._pad_visual("青a", 5).endswith("  ")


def test_ensure_utf8_console_no_op_on_non_win(monkeypatch: pytest.MonkeyPatch) -> None:
    """Smoke: function must not raise even on a stubbed non-win32 platform."""
    monkeypatch.setattr("sys.platform", "linux")
    cli_main._ensure_utf8_console()  # should return early
