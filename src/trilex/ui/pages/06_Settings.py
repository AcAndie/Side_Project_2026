"""Settings page — read-only display of `.env` config (masked) + diagnostics."""

from __future__ import annotations

import platform
import sys

import streamlit as st

from trilex.config import ENV_FILE, get_settings, mask_key
from trilex.persistence.db import DEFAULT_DB_PATH
from trilex.ui._helpers import db_ready, sidebar_project_selector

st.set_page_config(page_title="Settings — TriLex", page_icon="⚙️", layout="wide")

sidebar_project_selector()

st.title("⚙️ Settings")

# --------------------------------------------------------------------------- #
# Config                                                                      #
# --------------------------------------------------------------------------- #

st.subheader("API keys & model")
st.caption(f"Source: `{ENV_FILE}` (file là source of truth — chỉnh tay rồi reload)")

try:
    s = get_settings()
except Exception as e:  # noqa: BLE001
    st.error(f"Config invalid: {e}")
    st.stop()

cols = st.columns(2)
cols[0].metric("GEMINI_API_KEY", mask_key(s.gemini_api_key.get_secret_value()))
cols[1].metric("gemini_model", s.gemini_model)

with st.expander("Fallback keys"):
    if s.fallback_key_1:
        st.write(f"FALLBACK_KEY_1: `{mask_key(s.fallback_key_1.get_secret_value())}`")
    else:
        st.write("FALLBACK_KEY_1: (not set)")
    if s.fallback_key_2:
        st.write(f"FALLBACK_KEY_2: `{mask_key(s.fallback_key_2.get_secret_value())}`")
    else:
        st.write("FALLBACK_KEY_2: (not set)")
    st.caption(f"Total active keys: {len(s.all_keys())}")

st.write("**request_timeout**:", f"{s.request_timeout}s")
st.write("**max_retries**:", s.max_retries)

st.divider()

# --------------------------------------------------------------------------- #
# DB                                                                          #
# --------------------------------------------------------------------------- #

st.subheader("Database")
st.write(f"**Path**: `{DEFAULT_DB_PATH.resolve()}`")
st.write(f"**Status**: {'✅ ready' if db_ready() else '❌ not initialized'}")
if not db_ready():
    st.code("trilex db init", language="bash")

st.divider()

# --------------------------------------------------------------------------- #
# Diagnostics                                                                 #
# --------------------------------------------------------------------------- #

st.subheader("Diagnostics")

st.write("**Python**:", platform.python_version(), f"({sys.executable})")

try:
    import streamlit as _st

    st.write("**Streamlit**:", _st.__version__)
except Exception:  # noqa: BLE001
    pass

st.info("Để chỉnh API key: mở file `.env`, sửa giá trị `GEMINI_API_KEY=...`, sau đó reload tab.")
