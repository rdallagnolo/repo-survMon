from pathlib import Path

import streamlit as st


st.set_page_config(
    page_title="SurvMon — Release Version 1.0",
    page_icon=":eagle:",
    layout="centered",
    initial_sidebar_state="auto",
    menu_items=None,
)

readme_path = Path(__file__).resolve().with_name("README.md")

try:
    readme_text = readme_path.read_text(encoding="utf-8")
except (OSError, UnicodeError) as exc:
    st.error(f"Unable to read README.md: {exc}")
    st.stop()

st.markdown(readme_text)