"""Tests for `ui/_helpers.py`.

Streamlit decorated helpers (`@st.cache_resource`) are exercised by calling
the underlying functions directly. The sidebar selector + Streamlit-bound
warnings are exercised through `streamlit.testing.v1.AppTest`, which runs a
Streamlit script in-process without a server.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from trilex.persistence import db as db_mod
from trilex.persistence.db import sync_dsn
from trilex.persistence.models import Base, Project
from trilex.ui import _helpers as h

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _clear_streamlit_caches() -> None:
    """Drop @st.cache_resource memos so each test sees a fresh engine."""
    for fn in (h.get_session_maker, h.get_sync_session_factory):
        clear = getattr(fn, "clear", None)
        if clear is not None:
            clear()


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_file = tmp_path / "ui.db"
    monkeypatch.setattr(db_mod, "DEFAULT_DB_PATH", db_file)
    monkeypatch.setattr(h, "DEFAULT_DB_PATH", db_file)

    eng = create_engine(sync_dsn(db_file), future=True)
    Base.metadata.create_all(eng)
    eng.dispose()

    _clear_streamlit_caches()
    yield db_file
    _clear_streamlit_caches()


# --------------------------------------------------------------------------- #
# run_async                                                                    #
# --------------------------------------------------------------------------- #


def test_run_async_executes_coroutine() -> None:
    async def add(a: int, b: int) -> int:
        await asyncio.sleep(0)
        return a + b

    assert h.run_async(add(2, 3)) == 5


# --------------------------------------------------------------------------- #
# Session makers                                                              #
# --------------------------------------------------------------------------- #


def test_get_sync_session_factory_returns_callable(tmp_db: Path) -> None:
    factory = h.get_sync_session_factory()
    with factory() as s:
        s.add(Project(name="x", slug="x", source_lang="zh", target_lang="vn"))
        s.commit()
    with factory() as s:
        rows = s.query(Project).filter_by(slug="x").all()
        assert len(rows) == 1


def test_sync_session_commits(tmp_db: Path) -> None:
    with h.sync_session() as s:
        s.add(Project(name="a", slug="a", source_lang="zh", target_lang="vn"))
    with h.sync_session() as s:
        rows = s.query(Project).filter_by(slug="a").all()
        assert len(rows) == 1


def test_sync_session_rolls_back_on_exception(tmp_db: Path) -> None:
    with pytest.raises(RuntimeError, match="boom"), h.sync_session() as s:
        s.add(Project(name="b", slug="b", source_lang="zh", target_lang="vn"))
        raise RuntimeError("boom")
    with h.sync_session() as s:
        rows = s.query(Project).filter_by(slug="b").all()
        assert rows == []


# --------------------------------------------------------------------------- #
# list_projects + db_ready                                                    #
# --------------------------------------------------------------------------- #


def test_db_ready_true_after_init(tmp_db: Path) -> None:
    assert h.db_ready() is True


def test_db_ready_false_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(h, "DEFAULT_DB_PATH", tmp_path / "ghost.db")
    assert h.db_ready() is False


def test_list_projects_empty(tmp_db: Path) -> None:
    rows = h.list_projects()
    assert list(rows) == []


def test_list_projects_returns_rows(tmp_db: Path) -> None:
    with h.sync_session() as s:
        s.add(Project(name="N1", slug="s1", source_lang="zh", target_lang="vn"))
        s.add(Project(name="N2", slug="s2", source_lang="zh", target_lang="vn"))
    rows = list(h.list_projects())
    assert {p.slug for p in rows} == {"s1", "s2"}


# --------------------------------------------------------------------------- #
# sidebar_project_selector + gemini_provider_or_warn via AppTest              #
# --------------------------------------------------------------------------- #


def test_sidebar_selector_warns_when_db_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When DB does not exist, the selector renders a warning and returns None."""
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(db_mod, "DEFAULT_DB_PATH", tmp_path / "absent.db")

    script = """
import sys
sys.path.insert(0, "src")
from trilex.persistence import db as db_mod
db_mod.DEFAULT_DB_PATH = __import__("pathlib").Path(r"{absent}")
from trilex.ui import _helpers as h
h.DEFAULT_DB_PATH = db_mod.DEFAULT_DB_PATH
result = h.sidebar_project_selector()
import streamlit as st
st.session_state["__result__"] = result
""".format(absent=str(tmp_path / "absent.db").replace("\\", "\\\\"))

    at = AppTest.from_string(script).run()
    assert at.session_state["__result__"] is None
    assert any("DB chưa init" in w.value for w in at.sidebar.warning)


def test_sidebar_selector_info_when_no_projects(
    tmp_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DB exists but is empty — selector emits an info note + returns None."""
    from streamlit.testing.v1 import AppTest

    db_str = str(tmp_db).replace("\\", "\\\\")
    script = f"""
import sys
sys.path.insert(0, "src")
from pathlib import Path
from trilex.persistence import db as db_mod
db_mod.DEFAULT_DB_PATH = Path(r"{db_str}")
from trilex.ui import _helpers as h
h.DEFAULT_DB_PATH = db_mod.DEFAULT_DB_PATH
result = h.sidebar_project_selector()
import streamlit as st
st.session_state["__result__"] = result
"""
    at = AppTest.from_string(script).run()
    assert at.session_state["__result__"] is None
    assert any("Chưa có project" in i.value for i in at.sidebar.info)


def test_sidebar_selector_picks_project(
    tmp_db: Path,
) -> None:
    """DB has projects — selector returns the first by default."""
    from streamlit.testing.v1 import AppTest

    with h.sync_session() as s:
        s.add(Project(name="P1", slug="p1", source_lang="zh", target_lang="vn"))

    db_str = str(tmp_db).replace("\\", "\\\\")
    script = f"""
import sys
sys.path.insert(0, "src")
from pathlib import Path
from trilex.persistence import db as db_mod
db_mod.DEFAULT_DB_PATH = Path(r"{db_str}")
from trilex.ui import _helpers as h
h.DEFAULT_DB_PATH = db_mod.DEFAULT_DB_PATH
result = h.sidebar_project_selector()
import streamlit as st
st.session_state["__result_slug__"] = result.slug if result else None
"""
    at = AppTest.from_string(script).run()
    assert at.session_state["__result_slug__"] == "p1"


def test_gemini_provider_or_warn_missing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing GEMINI_API_KEY → renders error + returns None."""
    from streamlit.testing.v1 import AppTest

    from trilex import config as cfg_mod

    cfg_mod.get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "   ")

    script = """
import sys
sys.path.insert(0, "src")
from trilex import config as cfg_mod
cfg_mod.get_settings.cache_clear()
from trilex.ui import _helpers as h
out = h.gemini_provider_or_warn()
import streamlit as st
st.session_state["__provider__"] = out
"""
    at = AppTest.from_string(script).run()
    cfg_mod.get_settings.cache_clear()
    assert at.session_state["__provider__"] is None
    assert len(at.error) >= 1


def test_gemini_provider_or_warn_happy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Valid env → real GeminiProvider instance returned."""
    from streamlit.testing.v1 import AppTest

    from trilex import config as cfg_mod

    cfg_mod.get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTESTxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

    script = """
import sys
sys.path.insert(0, "src")
from trilex import config as cfg_mod
cfg_mod.get_settings.cache_clear()
from trilex.ui import _helpers as h
out = h.gemini_provider_or_warn()
import streamlit as st
st.session_state["__ok__"] = out is not None
"""
    at = AppTest.from_string(script).run()
    cfg_mod.get_settings.cache_clear()
    assert at.session_state["__ok__"] is True
