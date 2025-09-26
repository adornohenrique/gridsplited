# core/help.py
how_it_works_md = """
### How this app works
1) Load & normalize your time/price columns (auto-detected).
2) Align to 15-min cadence (edges expanded; gaps filled).
3) Dispatch: Pmax if price ≥ break-even, else Pmin or 0 (with ramp).
4) Economics: proxy profit and full MeOH EBITDA.
"""

def show_help_panel(location: str = "main"):
    import streamlit as st
    with (st.sidebar if location == "sidebar" else st.container()):
        with st.expander("How this app works"):
            st.markdown(how_it_works_md)
