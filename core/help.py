# core/help.py
import streamlit as st

HELP_MD = """
# 📘 How this app works
...[SNIPPED FOR BREVITY – use the same long text I gave earlier]...
"""

def show_help_panel():
    if "show_help" not in st.session_state:
        st.session_state.show_help = False
    cols = st.columns([1,1,1,1,1])
    with cols[-1]:
        if st.button("📘 How this app works", use_container_width=True):
            st.session_state.show_help = not st.session_state.show_help
    if st.session_state.show_help:
        with st.expander("Close help", expanded=True):
            st.markdown(HELP_MD)
